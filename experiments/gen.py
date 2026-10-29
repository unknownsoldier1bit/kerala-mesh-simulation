"""Builds the inputs of one simulation run: topology, traffic and failure schedule.

Every input is generated from a seed, so a run can be rebuilt exactly. For a given
node count and seed, the topology and traffic are the same for every protocol and
every scenario; only the failure schedule changes between scenarios. That keeps
all non-target variables fixed when protocols or scenarios are compared.
"""

import itertools
import json
import math
import zlib

import networkx as nx
import numpy as np

# ---- Fixed network settings (see experiments/README.md for the reasons) ----
AREA_M = 500.0  # square side; the area stays the same for every node count
RANGE_M = 150.0  # radio range (unit disk)
PAYLOAD_B = 512  # UDP payload per data packet
INTERVAL_S = 0.25  # 4 packets/s per flow
TRAFFIC_START_S = 60.0
TRAFFIC_STOP_S = 290.0
SIM_TIME_S = 300.0
FAIL_TIME_S = 120.0
RESTORE_TIME_S = 210.0


def topo_seed(n, seed):
    return 100_000 + 1_000 * n + seed


def unit_disk_graph(xy, rng_m=RANGE_M):
    g = nx.Graph()
    g.add_nodes_from(range(len(xy)))
    for i, j in itertools.combinations(range(len(xy)), 2):
        if math.dist(xy[i], xy[j]) <= rng_m:
            g.add_edge(i, j)
    return g


def make_topology(n, seed, area=AREA_M, rng_m=RANGE_M):
    """Uniform random placement, redrawn until the network is connected.

    Returns positions, the graph and how many draws were needed.
    """
    rng = np.random.default_rng(topo_seed(n, seed))
    for attempt in range(1, 100_000):
        xy = rng.uniform(0, area, size=(n, 2))
        g = unit_disk_graph(xy, rng_m)
        if nx.is_connected(g):
            return xy, g, attempt
    raise RuntimeError("no connected topology found")


def make_flows(g, n_flows, seed, min_hops=2):
    """Random source-destination pairs at least `min_hops` apart.

    A node may take part in several flows. Each flow starts at a random offset
    within one packet interval so that sources don't transmit in lockstep.
    """
    rng = np.random.default_rng(topo_seed(len(g), seed) + 7_000 + n_flows)
    hops = dict(nx.all_pairs_shortest_path_length(g))
    pairs = [(s, d) for s in g for d in g if s != d and hops[s][d] >= min_hops]
    order = rng.permutation(len(pairs))
    flows = []
    used = set()
    for k in order:
        s, d = pairs[k]
        if (s, d) in used or (d, s) in used:
            continue
        used.add((s, d))
        flows.append({"flow": len(flows), "src": int(s), "dst": int(d), "hops": int(hops[s][d])})
        if len(flows) == n_flows:
            break
    offsets = rng.uniform(0, INTERVAL_S, size=len(flows))
    for f, off in zip(flows, offsets):
        f["segments"] = [(TRAFFIC_START_S + float(off), TRAFFIC_STOP_S, INTERVAL_S)]
    return flows


def endpoints(flows):
    return {f["src"] for f in flows} | {f["dst"] for f in flows}


def flow_load(g, flows):
    """How much each node and link lies on the flows' shortest paths.

    For each flow, every shortest path counts with weight 1 / (number of shortest paths).
    """
    node_load = {v: 0.0 for v in g}
    edge_load = {tuple(sorted(e)): 0.0 for e in g.edges}
    for f in flows:
        paths = list(nx.all_shortest_paths(g, f["src"], f["dst"]))
        w = 1.0 / len(paths)
        for p in paths:
            for v in p[1:-1]:
                node_load[v] += w
            for a, b in zip(p, p[1:]):
                edge_load[tuple(sorted((a, b)))] += w
    return node_load, edge_load


def failed_graph(g, nodes=(), links=()):
    h = g.copy()
    h.remove_edges_from(links)
    h.remove_nodes_from(nodes)
    return h


def route_status(g, flows, nodes=(), links=()):
    """For each flow: does any path between its endpoints survive the failures?"""
    h = failed_graph(g, nodes, links)
    out = []
    for f in flows:
        s, d = f["src"], f["dst"]
        if s not in h or d not in h:
            ok = False
        else:
            ok = nx.has_path(h, s, d)
        out.append({"flow": f["flow"], "alternative_route_exists": bool(ok)})
    return out


# ---------------------------------------------------------------------------
# Scenarios. Each returns (events, metadata). Events are tuples
# (time_s, action, kind, a, b, group).
# ---------------------------------------------------------------------------

ASSUMPTIONS = {
    "baseline": "No failures. Reference for every other scenario.",
    "link_fail": (
        "Individual radio links stop working while both devices keep running, as when "
        "floodwater, debris or a collapsed structure blocks the path between two devices. "
        "Modelled as the two nodes no longer hearing each other. The links chosen are the "
        "ones carrying the most traffic on shortest paths (a targeted, worst-case choice)."
    ),
    "node_fail": (
        "Relay devices stop working (submerged, destroyed, or battery dead) and stay down. "
        "Modelled by switching the radio off. The nodes chosen are the relays carrying the "
        "most traffic on shortest paths (targeted, worst-case). Senders and receivers are "
        "never failed, so every lost packet is due to routing, not to a missing endpoint."
    ),
    "multi_fail": (
        "Damage spreads over time: three waves of randomly chosen relay failures and link "
        "failures, 15 s apart, as more devices and paths are lost while water rises. Random "
        "selection (seeded), so it is not aimed at the busiest paths."
    ),
    "partition": (
        "The area is split in two: every link crossing the vertical midline stops working, "
        "then all come back. This abstracts losing every device or path that bridged two "
        "neighbourhoods (for example both sides of a flooded channel). It is not a physical "
        "propagation model; it guarantees a clean partition so protocol behaviour during and "
        "after a split can be measured."
    ),
    "recovery": (
        "Same relay failures as node_fail, but the devices come back later (power or "
        "equipment restored). Measures how each protocol recovers when connectivity returns."
    ),
}


def scenario_events(name, xy, g, flows, seed, severity=None):
    n = len(g)
    ends = endpoints(flows)
    relays = [v for v in g if v not in ends]
    node_load, edge_load = flow_load(g, flows)
    rng = np.random.default_rng(topo_seed(n, seed) + 50_000 + zlib.crc32(f"{name}:{severity}".encode()) % 10_000)
    events = []
    failed_nodes = []
    failed_links = []
    restore_time = None
    selection = "deterministic"

    if name == "baseline":
        pass
    elif name == "link_fail":
        k = severity or 5
        ranked = sorted(edge_load, key=lambda e: (-edge_load[e], e))
        failed_links = [e for e in ranked if edge_load[e] > 0][:k]
        events = [(FAIL_TIME_S, "fail", "link", a, b, "links") for a, b in failed_links]
    elif name in ("node_fail", "recovery"):
        k = severity or max(1, round(0.10 * n))
        ranked = sorted(relays, key=lambda v: (-node_load[v], v))
        failed_nodes = ranked[:k]
        events = [(FAIL_TIME_S, "fail", "node", v, -1, "relays") for v in failed_nodes]
        if name == "recovery":
            restore_time = RESTORE_TIME_S
            events += [(RESTORE_TIME_S, "restore", "node", v, -1, "relays") for v in failed_nodes]
    elif name == "multi_fail":
        selection = "random"
        frac = severity or 0.05  # per wave, of all nodes and of all links
        alive = list(relays)
        links = sorted(tuple(sorted(e)) for e in g.edges)
        for w, t in enumerate((FAIL_TIME_S, FAIL_TIME_S + 15, FAIL_TIME_S + 30)):
            kn = min(len(alive), max(1, round(frac * n)))
            pick = sorted(rng.choice(alive, size=kn, replace=False).tolist())
            alive = [v for v in alive if v not in pick]
            failed_nodes += pick
            events += [(t, "fail", "node", v, -1, f"wave{w + 1}") for v in pick]
            cand = [e for e in links if e not in failed_links]
            kl = max(1, round(frac * len(links)))
            idx = rng.choice(len(cand), size=min(kl, len(cand)), replace=False)
            pickl = sorted(cand[i] for i in idx)
            failed_links += pickl
            events += [(t, "fail", "link", a, b, f"wave{w + 1}") for a, b in pickl]
    elif name == "partition":
        mid = AREA_M / 2
        failed_links = sorted(
            tuple(sorted((a, b))) for a, b in g.edges if (xy[a][0] < mid) != (xy[b][0] < mid)
        )
        restore_time = RESTORE_TIME_S
        events = [(FAIL_TIME_S, "fail", "link", a, b, "cut") for a, b in failed_links]
        events += [(RESTORE_TIME_S, "restore", "link", a, b, "cut") for a, b in failed_links]
    elif name == "random_nodes":  # severity sweep: random relays, fraction of all nodes
        selection = "random"
        k = min(len(relays), max(1, round(severity * n)))
        failed_nodes = sorted(rng.choice(relays, size=k, replace=False).tolist())
        events = [(FAIL_TIME_S, "fail", "node", v, -1, "random") for v in failed_nodes]
    elif name == "random_links":  # severity sweep: random links, fraction of all links
        selection = "random"
        links = sorted(tuple(sorted(e)) for e in g.edges)
        k = max(1, round(severity * len(links)))
        idx = rng.choice(len(links), size=k, replace=False)
        failed_links = sorted(links[i] for i in idx)
        events = [(FAIL_TIME_S, "fail", "link", a, b, "random") for a, b in failed_links]
    else:
        raise ValueError(name)

    events.sort(key=lambda e: (e[0], e[1], e[2], e[3], e[4]))
    status = route_status(g, flows, failed_nodes, failed_links)
    h = failed_graph(g, failed_nodes, failed_links)
    meta = {
        "scenario": name,
        "severity_param": severity,
        "selection": selection,
        "assumption": ASSUMPTIONS.get(name, ASSUMPTIONS.get(name.replace("random_", "") + "_fail", "")),
        "failure_start_s": min((e[0] for e in events if e[1] == "fail"), default=None),
        "failure_end_s": restore_time,  # None = failures last until the end of the run
        "failed_nodes": [
            {"node": int(v), "x": round(float(xy[v][0]), 2), "y": round(float(xy[v][1]), 2)}
            for v in failed_nodes
        ],
        "failed_links": [
            {
                "a": int(a),
                "b": int(b),
                "mid_x": round(float((xy[a][0] + xy[b][0]) / 2), 2),
                "mid_y": round(float((xy[a][1] + xy[b][1]) / 2), 2),
            }
            for a, b in failed_links
        ],
        "n_failed_nodes": len(failed_nodes),
        "pct_failed_nodes": round(100 * len(failed_nodes) / n, 2),
        "n_failed_links": len(failed_links),
        "pct_failed_links": round(100 * len(failed_links) / g.number_of_edges(), 2),
        "components_after_failure": nx.number_connected_components(h) if len(h) else 0,
        "flows_with_alternative_route": sum(s["alternative_route_exists"] for s in status),
        "flows_total": len(flows),
        "per_flow": status,
    }
    return events, meta


# ---------------------------------------------------------------------------
# File writers
# ---------------------------------------------------------------------------


def write_topology(path, xy):
    with open(path, "w") as f:
        f.write("node_id,x,y\n")
        for i, (x, y) in enumerate(xy):
            f.write(f"{i},{x:.3f},{y:.3f}\n")


def write_flows(path, flows, payload=PAYLOAD_B):
    with open(path, "w") as f:
        f.write("flow_id,src,dst,start_s,stop_s,interval_s,payload_bytes\n")
        for fl in flows:
            for start, stop, interval in fl["segments"]:
                f.write(f"{fl['flow']},{fl['src']},{fl['dst']},{start:.6f},{stop:.6f},{interval},{payload}\n")


def write_events(path, events):
    with open(path, "w") as f:
        f.write("time_s,action,kind,a,b,group\n")
        for t, action, kind, a, b, group in events:
            f.write(f"{t},{action},{kind},{a},{b},{group}\n")


def write_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=1)
