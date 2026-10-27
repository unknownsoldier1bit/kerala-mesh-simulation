"""Turns the raw output of one run into the metrics requested in docs/deliverables.md.

Definitions (also in experiments/README.md):

- PDR: data packets received / data packets sent x 100. "Sent" counts packets the
  source application generated while its radio was on.
- Delay: receive time - send time of each delivered packet, in ms.
- Throughput: UDP payload bits delivered / length of the traffic period (or window).
- Control packets/bytes: routing packets handed to the network interface by working
  nodes, counting every rebroadcast; bytes are IP-layer bytes (IP + UDP + routing message).
- Normalised routing load (NRL): control packets sent during the traffic period /
  data packets delivered. Control-byte ratio: control bytes / delivered payload bytes.
- Recovery time (per failure event and affected flow): time from the event until the
  destination first receives a packet that the source sent at or after the event.
  A flow is affected by a failure if the last packet it delivered before the failure
  went through a node or link that failed. After a restore event, a flow is affected
  if it delivered nothing in the 5 s before the restore.
- Within-T: share of sent packets delivered with delay <= T.
"""

import json
import math
import os

import numpy as np
import pandas as pd

DROP_NAMES = {
    0: "no_drop_event",  # lost without any drop trace: still queued at the end, or lost on the air
    1: "no_route_at_source",
    11: "ip_ttl_expired",
    12: "ip_no_route",
    13: "ip_bad_checksum",
    14: "ip_interface_down",
    15: "ip_route_error",  # routing protocol gave up (e.g. AODV/DSDV queue timeout, no route at relay)
    16: "ip_fragment_timeout",
    17: "ip_duplicate",
    20: "mac_queue_full",
    21: "mac_lifetime_expired",
    22: "mac_retry_limit",  # next hop never acknowledged: link broken or collisions
    23: "mac_old_packet",
}

AODV_TYPES = ["rreq_originated", "rreq_forwarded", "rrep", "rerr", "hello", "rrep_ack"]
OLSR_TYPES = ["hello_msgs", "tc_msgs", "mid_msgs", "hna_msgs", "unused4", "unused5"]

DEADLINES_S = (0.5, 1.0, 2.0, 5.0)


def _read(run_dir, name):
    for fname in (name, name + ".gz"):
        p = os.path.join(run_dir, fname)
        if os.path.exists(p):
            return pd.read_csv(p)
    return None


def _path_nodes(path):
    if isinstance(path, str) and path:
        return [int(x) for x in path.split("-")]
    return []


def _stats(x):
    if len(x) == 0:
        return dict(mean=np.nan, median=np.nan, std=np.nan, p95=np.nan)
    return dict(
        mean=float(np.mean(x)),
        median=float(np.median(x)),
        std=float(np.std(x, ddof=1)) if len(x) > 1 else 0.0,
        p95=float(np.percentile(x, 95)),
    )


def failure_points(events):
    """Groups the logged events by time and action.

    Returns [(time, action, nodes, links, failed_nodes_after, failed_links_after)], where
    the last two are everything that is down once the event has been applied.
    Battery depletions count as node failures.
    """
    out = []
    if events is None or events.empty:
        return out
    down_nodes, down_links = set(), set()
    ev = events.assign(action=events.action.replace({"deplete": "fail"}))
    for (t, action), grp in ev.groupby(["time_s", "action"], sort=True):
        nodes = set(grp.loc[grp.kind == "node", "a"].astype(int))
        links = {tuple(sorted((int(a), int(b)))) for a, b in grp.loc[grp.kind == "link", ["a", "b"]].values}
        if action == "fail":
            down_nodes |= nodes
            down_links |= links
        else:
            down_nodes -= nodes
            down_links -= links
        out.append((float(t), action, nodes, links, set(down_nodes), set(down_links)))
    return out


def topology_graph(cfg):
    import gen

    xy = pd.read_csv(cfg["topo"])[["x", "y"]].values
    return gen.unit_disk_graph(xy, cfg["range_m"])


def has_route(g, src, dst, down_nodes, down_links):
    import networkx as nx

    if src in down_nodes or dst in down_nodes:
        return False
    h = g.copy()
    h.remove_nodes_from(down_nodes)
    h.remove_edges_from(down_links)
    return nx.has_path(h, src, dst)


def recovery_analysis(pk, cfg, events, traffic_stop, window_s=10.0):
    """Per (event, affected flow): whether a route still existed, recovery time, and
    delivery in the 10 s after the event."""
    rows = []
    pts = failure_points(events)
    if not pts:
        return pd.DataFrame(rows)
    g = topology_graph(cfg)
    by_flow = {f: grp.sort_values("seq") for f, grp in pk.groupby("flow")}
    for t, action, nodes, links, down_nodes, down_links in pts:
        if t >= traffic_stop:
            continue
        for fl in cfg["flows"]:
            grp = by_flow.get(fl["flow"])
            if grp is None:
                continue
            if fl["src"] in down_nodes or fl["dst"] in down_nodes:
                continue  # an endpoint is gone: nothing to recover
            delivered = grp[grp.rx_s.notna()]
            if action == "fail":
                before = delivered[delivered.tx_s < t]
                if before.empty:
                    continue
                last = before.iloc[-1]
                hops = [fl["src"]] + _path_nodes(last.path) + [fl["dst"]]
                hit_node = any(v in nodes for v in hops)
                hit_link = any(tuple(sorted((a, b))) in links for a, b in zip(hops, hops[1:]))
                if not (hit_node or hit_link):
                    continue
            else:  # restore
                if grp[(grp.tx_s >= t - 5.0) & (grp.tx_s < t)].empty:
                    continue  # flow wasn't sending, so it can't have been cut off
                recent = delivered[(delivered.rx_s >= t - 5.0) & (delivered.rx_s < t)]
                if not recent.empty:
                    continue
            route = has_route(g, fl["src"], fl["dst"], down_nodes, down_links)
            # Recovery is measured until the next event that changes the network, so a
            # later restore doesn't get credited to rerouting around this failure.
            next_t = min((p[0] for p in pts if p[0] > t), default=traffic_stop)
            after = delivered[(delivered.tx_s >= t) & (delivered.rx_s < next_t)]
            rec = float(after.rx_s.min() - t) if (route and not after.empty) else math.nan
            win = grp[(grp.tx_s >= t) & (grp.tx_s < t + window_s)]
            rows.append(
                dict(
                    event_time_s=t,
                    event=action,
                    flow=fl["flow"],
                    route_available=route,
                    recovered=not math.isnan(rec),
                    recovery_s=rec,
                    # time without delivery after the event (censored at the next event)
                    outage_s=rec if not math.isnan(rec) else next_t - t,
                    censored_at_s=next_t,
                    sent_in_window=len(win),
                    delivered_in_window=int(win.rx_s.notna().sum()),
                )
            )
    return pd.DataFrame(rows)


def window_bounds(cfg):
    """Analysis windows: before failure, during failure, after restore (if any)."""
    t0, t1 = cfg["traffic_start_s"], cfg["traffic_stop_s"]
    tf = cfg.get("fail_time_s") or t1
    tr = cfg.get("restore_time_s")
    w = {"pre": (t0, min(tf, t1)), "during": (min(tf, t1), tr if tr else t1)}
    if tr:
        w["post"] = (tr, t1)
    return {k: v for k, v in w.items() if v[1] > v[0]}


def compute(run_dir, cfg):
    """Returns (summary dict, per-flow DataFrame, recovery DataFrame)."""
    pk = _read(run_dir, "packets.csv")
    ctrl = _read(run_dir, "control.csv")
    events = _read(run_dir, "events.csv")
    energy = _read(run_dir, "energy.csv")
    routes = _read(run_dir, "routes.csv")
    disc = _read(run_dir, "discoveries.csv")
    stats = _read(run_dir, "stats.csv")
    proto = cfg["protocol"]
    n = cfg["nodes"]
    t0, t1 = cfg["traffic_start_s"], cfg["traffic_stop_s"]
    period = t1 - t0
    payload_bits = 8 * cfg["payload_bytes"]

    s = {}
    for k in ("experiment", "run_id", "protocol", "scenario", "nodes", "seed", "rng_run", "n_flows",
              "severity", "fail_time_s", "restore_time_s", "deadline_s"):
        s[k] = cfg.get(k)
    s["failure_severity"] = cfg.get("severity_label", "")

    # ---- Delivery and delay ----
    sent = len(pk)
    got = pk[pk.rx_s.notna()]
    recv = len(got)
    delay_ms = (got.rx_s - got.tx_s).values * 1000
    s.update(packets_sent=sent, packets_received=recv)
    s["pdr_pct"] = 100 * recv / sent if sent else np.nan
    s["packets_lost"] = sent - recv
    s["loss_pct"] = 100 * (sent - recv) / sent if sent else np.nan
    d = _stats(delay_ms)
    s.update(delay_mean_ms=d["mean"], delay_median_ms=d["median"], delay_std_ms=d["std"], delay_p95_ms=d["p95"])
    s["delay_max_ms"] = float(delay_ms.max()) if recv else np.nan
    for T in DEADLINES_S:
        s[f"within_{T:g}s_pct"] = 100 * float((delay_ms <= 1000 * T).sum()) / sent if sent else np.nan
    s["mean_hops"] = float(got.path.fillna("").map(lambda p: len(_path_nodes(p)) + 1).mean()) if recv else np.nan
    s["throughput_kbps"] = recv * payload_bits / period / 1000
    s["throughput_interval_s"] = f"{t0:g}-{t1:g}"
    s["suppressed_sends"] = int(stats.suppressed_sends.iloc[0]) if stats is not None else np.nan

    # ---- Loss reasons ----
    lost = pk[pk.rx_s.isna()]
    reasons = lost.drop_code.map(lambda c: DROP_NAMES.get(int(c), f"code_{int(c)}")).value_counts()
    for name in DROP_NAMES.values():
        s[f"lost_{name}"] = int(reasons.get(name, 0))

    # ---- Routing overhead ----
    in_period = ctrl[(ctrl.t_s >= math.floor(t0)) & (ctrl.t_s < math.ceil(t1))]
    s["control_pkts"] = int(ctrl.pkts.sum())
    s["control_bytes"] = int(ctrl.bytes.sum())
    s["control_pkts_traffic_period"] = int(in_period.pkts.sum())
    s["control_bytes_traffic_period"] = int(in_period.bytes.sum())
    s["control_pkts_per_node_s"] = s["control_pkts"] / (n * cfg["sim_time_s"])
    s["nrl_ctrl_per_delivered"] = s["control_pkts_traffic_period"] / recv if recv else np.nan
    s["ctrl_bytes_per_payload_byte"] = (
        s["control_bytes_traffic_period"] / (recv * cfg["payload_bytes"]) if recv else np.nan
    )
    names = AODV_TYPES if proto == "aodv" else OLSR_TYPES if proto == "olsr" else None
    for i in range(6):
        col = f"type{i}"
        if names and not names[i].startswith("unused"):
            s[f"ctrl_{proto}_{names[i]}"] = int(ctrl[col].sum())
    s["mac_link_break_detections"] = int(ctrl.mac_retry_drops.sum())

    # AODV-only metrics; left empty (not zero) for protocols that don't have them.
    s["route_errors_rerr_tx"] = int(ctrl.type3.sum()) if proto == "aodv" else np.nan
    if proto == "aodv" and disc is not None:
        dd = disc[(disc.start_s >= t0) & (disc.start_s < t1)]
        done = dd[dd.end_s.notna()]
        s["route_discoveries"] = len(dd)
        s["route_discoveries_completed"] = len(done)
        s["route_discovery_attempts"] = int(dd.attempts.sum())
        dt = (done.end_s - done.start_s).values * 1000
        s["route_discovery_mean_ms"] = float(dt.mean()) if len(dt) else np.nan
        s["route_discovery_median_ms"] = float(np.median(dt)) if len(dt) else np.nan
        s["route_discovery_p95_ms"] = float(np.percentile(dt, 95)) if len(dt) else np.nan
    else:
        for k in ("route_discoveries", "route_discoveries_completed", "route_discovery_attempts",
                  "route_discovery_mean_ms", "route_discovery_median_ms", "route_discovery_p95_ms"):
            s[k] = np.nan

    # ---- Windows: before / during / after failure ----
    for wname, (a, b) in window_bounds(cfg).items():
        wp = pk[(pk.tx_s >= a) & (pk.tx_s < b)]
        wg = wp[wp.rx_s.notna()]
        s[f"{wname}_window_s"] = f"{a:g}-{b:g}"
        s[f"{wname}_pdr_pct"] = 100 * len(wg) / len(wp) if len(wp) else np.nan
        s[f"{wname}_within_1s_pct"] = (
            100 * float(((wg.rx_s - wg.tx_s) <= 1.0).sum()) / len(wp) if len(wp) else np.nan
        )
        s[f"{wname}_delay_mean_ms"] = float(((wg.rx_s - wg.tx_s) * 1000).mean()) if len(wg) else np.nan
        s[f"{wname}_throughput_kbps"] = len(wg) * payload_bits / (b - a) / 1000
        wc = ctrl[(ctrl.t_s >= math.floor(a)) & (ctrl.t_s < math.floor(b))]
        s[f"{wname}_ctrl_pkts_per_node_s"] = wc.pkts.sum() / (n * max(1, len(wc)))

    # ---- Recovery ----
    rec = recovery_analysis(pk, cfg, events, t1)
    for ev in ("fail", "restore"):
        r = rec[rec.event == ev] if not rec.empty else rec
        tag = "recovery" if ev == "fail" else "restore_recovery"
        s[f"{tag}_affected_flows"] = len(r)
        if len(r):
            rr = r[r.route_available]
            ok = rr[rr.recovered]
            s[f"{tag}_affected_no_route"] = int((~r.route_available).sum())
            s[f"{tag}_recovered_flows"] = len(ok)
            s[f"{tag}_not_recovered_flows"] = len(rr) - len(ok)
            s[f"{tag}_mean_s"] = float(ok.recovery_s.mean()) if len(ok) else np.nan
            s[f"{tag}_median_s"] = float(ok.recovery_s.median()) if len(ok) else np.nan
            s[f"{tag}_max_s"] = float(ok.recovery_s.max()) if len(ok) else np.nan
            s[f"{tag}_outage_mean_s"] = float(r.outage_s.mean())
            s[f"{tag}_window_delivered"] = int(r.delivered_in_window.sum())
            s[f"{tag}_window_pdr_pct"] = (
                100 * r.delivered_in_window.sum() / r.sent_in_window.sum() if r.sent_in_window.sum() else np.nan
            )
        else:
            for k in ("affected_no_route", "recovered_flows", "not_recovered_flows", "mean_s", "median_s",
                      "max_s", "outage_mean_s", "window_delivered", "window_pdr_pct"):
                s[f"{tag}_{k}"] = np.nan
    s["recovery_time_s"] = s["recovery_mean_s"]

    # ---- Routing-table validity / convergence (OLSR, DSDV) ----
    if routes is not None and len(routes):
        v = routes.assign(valid=np.where(routes.reachable_pairs > 0, routes.valid_pairs / routes.reachable_pairs, np.nan))
        first_ok = v[v.valid >= 0.999]
        s["initial_convergence_s"] = float(first_ok.t_s.iloc[0]) if len(first_ok) else np.nan
        s["route_validity_at_traffic_start"] = float(v.loc[(v.t_s - t0).abs().idxmin(), "valid"])
        conv = []
        for t, action, *_ in failure_points(events):
            after = v[v.t_s >= t]
            okk = after[after.valid >= 0.999]
            conv.append(float(okk.t_s.iloc[0] - t) if len(okk) else np.nan)
        s["convergence_after_events_s"] = json.dumps([None if math.isnan(c) else round(c, 3) for c in conv])
        s["convergence_mean_s"] = float(np.nanmean(conv)) if conv and not all(math.isnan(c) for c in conv) else np.nan
        s["route_validity_mean_pct"] = 100 * float(v[(v.t_s >= t0) & (v.t_s < t1)].valid.mean())
    else:
        for k in ("initial_convergence_s", "route_validity_at_traffic_start", "convergence_after_events_s",
                  "convergence_mean_s", "route_validity_mean_pct"):
            s[k] = np.nan

    # ---- Energy ----
    if energy is not None:
        s["energy_total_J"] = float(energy.consumed_J.sum())
        s["energy_mean_per_node_J"] = float(energy.consumed_J.mean())
        s["energy_max_node_J"] = float(energy.consumed_J.max())
        if energy.consumed_ns3_J.notna().any():
            s["energy_total_ns3_model_J"] = float(energy.consumed_ns3_J.sum())
        s["radio_tx_time_mean_s"] = float(energy.t_tx_s.mean())
        s["radio_rx_time_mean_s"] = float(energy.t_rx_s.mean())
        dep = energy.depleted_s.dropna().sort_values().values
        s["nodes_depleted"] = len(dep)
        s["first_depletion_s"] = float(dep[0]) if len(dep) else np.nan
        k10 = math.ceil(0.1 * n)
        k50 = math.ceil(0.5 * n)
        s["depletion_10pct_s"] = float(dep[k10 - 1]) if len(dep) >= k10 else np.nan
        s["depletion_50pct_s"] = float(dep[k50 - 1]) if len(dep) >= k50 else np.nan
    s["wall_s"] = float(stats.wall_s.iloc[0]) if stats is not None else np.nan

    # ---- Per flow ----
    fl_rows = []
    for fl in cfg["flows"]:
        g = pk[pk.flow == fl["flow"]]
        gg = g[g.rx_s.notna()]
        dl = (gg.rx_s - gg.tx_s).values * 1000
        st = _stats(dl)
        times = np.sort(gg.rx_s.values)
        gaps = np.diff(np.concatenate(([t0], times))) if len(times) else np.array([t1 - t0])
        fl_rows.append(
            dict(
                run_id=cfg["run_id"], flow=fl["flow"], src=fl["src"], dst=fl["dst"], shortest_hops=fl["hops"],
                alternative_route_exists=fl.get("alternative_route_exists"),
                sent=len(g), received=len(gg), pdr_pct=100 * len(gg) / len(g) if len(g) else np.nan,
                delay_mean_ms=st["mean"], delay_median_ms=st["median"], delay_p95_ms=st["p95"],
                longest_delivery_gap_s=float(gaps.max()),
            )
        )
    per_flow = pd.DataFrame(fl_rows)
    if not rec.empty:
        rec.insert(0, "run_id", cfg["run_id"])
    return s, per_flow, rec
