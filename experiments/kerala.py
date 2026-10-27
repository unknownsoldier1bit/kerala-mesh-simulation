"""Energy-depletion experiment and the Kerala-anchored time-evolving failure experiment.

Nothing here is a measurement from Kerala. The Kerala experiment uses the dated events
in data/sources.md (rain, dam releases, flooding, power cuts and restoration) to set
the ORDER and RELATIVE TIMING of failures in a compressed, hypothetical scenario. Every
number that is an assumption is listed in KERALA_ASSUMPTIONS and written next to the
inputs of every run.
"""

import os

import networkx as nx
import numpy as np

import gen

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

IDLE_W = 0.273 * 3.0  # ns-3 WifiRadioEnergyModel idle current x BasicEnergySource voltage
LOW_BATTERY = 0.10  # radio switches off when 10% of the initial energy is left

# ---------------------------------------------------------------------------
# Energy depletion
# ---------------------------------------------------------------------------

ENERGY_SIM_S = 600.0
ENERGY_PROFILES = {
    # ns-3 default currents: the radio draws 0.273 A whenever it is on (idle listening).
    "default_radio": {"idle_a": 0.273},
    # Hypothetical radio that draws almost nothing when idle (0.033 A, the ns-3 sleep
    # current), so energy depends mostly on sending and receiving. Shows the most that
    # routing traffic could matter for battery life.
    "low_idle_radio": {"idle_a": 0.033},
}


def battery_for_idle_life(idle_life_s, idle_a):
    """Initial energy (J) that lasts `idle_life_s` of pure idling before cut-off."""
    return idle_a * 3.0 * idle_life_s / (1 - LOW_BATTERY)


def energy_runs(exp, protocols, seeds):
    """Batteries with random initial charge, no other failures. Nodes die one by one.

    Each node's initial energy is set so that, idling only, it would last a random time
    between 200 s and 600 s (uniform). Sending and receiving shorten that.
    """
    n, nf = 50, 10
    runs = []
    for seed in seeds:
        xy, g, _ = gen.make_topology(n, seed)
        idir = os.path.join("results", exp, "inputs", f"n{n}_s{seed}")
        os.makedirs(os.path.join(REPO, idir), exist_ok=True)
        topo = os.path.join(idir, "topology.csv")
        gen.write_topology(os.path.join(REPO, topo), xy)
        fl = gen.make_flows(g, nf, seed)
        for f in fl:
            f["segments"] = [(s0, ENERGY_SIM_S - 5, iv) for s0, _, iv in f["segments"]]
        ffile = os.path.join(idir, f"flows_f{nf}.csv")
        gen.write_flows(os.path.join(REPO, ffile), fl)
        rng = np.random.default_rng(gen.topo_seed(n, seed) + 90_000)
        idle_life = rng.uniform(200, 600, size=n)
        for prof, p in ENERGY_PROFILES.items():
            efile = os.path.join(idir, f"battery_{prof}.csv")
            with open(os.path.join(REPO, efile), "w") as f:
                f.write("node,initial_J\n")
                for i, life in enumerate(idle_life):
                    f.write(f"{i},{battery_for_idle_life(life, p['idle_a']):.4f}\n")
            for proto in protocols:
                runs.append(dict(
                    experiment=exp, run_id=f"{proto}_{prof}_n{n}_f{nf}_s{seed}", protocol=proto,
                    scenario=prof, nodes=n, seed=seed, rng_run=seed, n_flows=nf, severity=None,
                    severity_label="battery depletion only", topo=topo, flows_file=ffile, events_file="",
                    energy_file=efile, idle_current_a=p["idle_a"], energy_j=0, energy_model="states",
                    fail_time_s=None, restore_time_s=None,
                    traffic_start_s=gen.TRAFFIC_START_S, traffic_stop_s=ENERGY_SIM_S - 5,
                    sim_time_s=ENERGY_SIM_S, payload_bytes=gen.PAYLOAD_B, range_m=gen.RANGE_M, deadline_s=1.0,
                    windows={"first_100s": [60, 160], "160_300s": [160, 300], "300_450s": [300, 450],
                             "450_595s": [450, 595]},
                    timeseries=True, connectivity=True, flows=fl,
                ))
    return runs


# ---------------------------------------------------------------------------
# Kerala-anchored time-evolving failures
# ---------------------------------------------------------------------------

DAY_S = 30.0  # simulated seconds per day (time compression)
DAY0_S = 60.0  # simulated time of 14 Aug 2018 00:00; 0-60 s is network warm-up
KERALA_SIM_S = DAY0_S + 13 * DAY_S  # until 27 Aug 00:00 (last Thrissur substation back)


def day(d):
    """Simulated time of August day d (e.g. day(15) = 15 Aug 00:00)."""
    return DAY0_S + (d - 14) * DAY_S


# Share of the eventual flood failures that has happened by each date. ASSUMPTION built
# from the anchors: releases start 14 Aug; heavy rain 15-17 Aug; Chalakudy floods early
# 15 Aug; releases end 18 Aug. Linear between the points.
FLOOD_CURVE = [(day(14), 0.0), (day(15), 0.15), (day(16), 0.60), (day(17), 0.90), (day(18), 1.0)]

KERALA_ASSUMPTIONS = {
    "time_compression": f"1 day = {DAY_S:g} simulated s; 14 Aug 2018 00:00 = {DAY0_S:g} s; run ends at 27 Aug "
                        "00:00. Only the failure process is compressed: routing timers and traffic run "
                        "at real speed.",
    "phases": "acute phase = 14-18 Aug (flood failures); sustained phase = 18-27 Aug (no new flooding, no "
              "grid power, batteries run down). Dates from data/sources.md: dam releases 14-18 Aug, "
              "IMD red rain 15-17 Aug, Chalakudy flooded early 15 Aug (one source says 17 Aug), power "
              "for the last Thrissur substation back on 27 Aug.",
    "flood_curve": "share of eventual flood failures by date: 14 Aug 0%, 15 Aug 15%, 16 Aug 60%, "
                   "17 Aug 90%, 18 Aug 100% (assumed shape; steepest during the red-alert rain)",
    "peak_failure_share": "share of mesh nodes lost to flooding by 18 Aug: 27% or 50%. 27% matches the "
                          "statewide share of base stations down (press report, data/sources.md) and is "
                          "used as a floor; 50% is a harsher hypothetical. The CAG report's 'total failure' "
                          "in Chalakudy taluk is a ceiling no mesh can route through, so it isn't simulated.",
    "spatial_pattern": "a river runs along the west edge (x = 0). Ground height = x / 500 m + Gaussian noise "
                       "(sd 0.1). Nodes flood in order of height, lowest first. Flooded nodes stay down "
                       "(submerged, abandoned or evacuated).",
    "uniform_random_baseline": "same number of node failures at the same times, but nodes picked uniformly at "
                               "random instead of lowest first",
    "no_failure_control": "no flood failures; batteries still run down",
    "batteries": "no recharging during the whole run (power cut from flood onset). Each node's initial "
                 "charge would last, idling only, until a random date between 19 Aug and 6 Sep (uniform), "
                 "so devices die one by one through the sustained phase and about half of the devices "
                 "that escaped flooding are still running on 27 Aug. Real device battery life under continuous ad-hoc "
                 "Wi-Fi is not documented in data/sources.md; this is a modelling choice.",
    "traffic": "20 flows of short message bursts: each burst is 5 packets of 512 B, 0.2 s apart; bursts "
               "start at random times, on average every 15 s per flow (exponential gaps). Disaster "
               "message traffic is not documented (data/sources.md lists it as missing).",
    "connectivity_control": "for every packet, whether a path existed between source and destination at "
                            "the moment it was sent (computed from the topology and the failures). "
                            "'connected PDR' = delivered / sent while a path existed, which separates "
                            "routing performance from packets no protocol could have delivered.",
}

BURST_PKTS = 5
BURST_SPACING_S = 0.2
BURST_MEAN_GAP_S = 15.0


def kerala_elevation(xy, seed):
    rng = np.random.default_rng(gen.topo_seed(len(xy), seed) + 70_000)
    return xy[:, 0] / gen.AREA_M + rng.normal(0, 0.1, size=len(xy))


def flood_schedule(order, n, peak_share):
    """Failure times for the first k nodes of `order`, following FLOOD_CURVE."""
    k_peak = round(peak_share * n)
    events = []
    for i, v in enumerate(order[:k_peak]):
        share = (i + 0.5) / k_peak  # this node fails when the curve passes its quantile
        for (t0, s0), (t1, s1) in zip(FLOOD_CURVE, FLOOD_CURVE[1:]):
            if s0 <= share <= s1:
                t = t0 + (share - s0) / (s1 - s0) * (t1 - t0)
                events.append((round(t, 3), "fail", "node", int(v), -1, "flood"))
                break
    return sorted(events)


def burst_flows(g, n_flows, seed, t_start, t_stop):
    fl = gen.make_flows(g, n_flows, seed)
    rng = np.random.default_rng(gen.topo_seed(len(g), seed) + 80_000)
    for f in fl:
        segs = []
        t = t_start + rng.exponential(BURST_MEAN_GAP_S)
        while t + BURST_PKTS * BURST_SPACING_S < t_stop:
            segs.append((t, t + BURST_PKTS * BURST_SPACING_S - 1e-6, BURST_SPACING_S))
            t += BURST_PKTS * BURST_SPACING_S + rng.exponential(BURST_MEAN_GAP_S)
        f["segments"] = segs
    return fl


def kerala_runs(exp, protocols, seeds, nodes=(50,)):
    runs = []
    windows = {"acute_14_18aug": [day(14), day(18)], "sustained_18_27aug": [day(18), KERALA_SIM_S - 2]}
    for n in nodes:
        for seed in seeds:
            xy, g, _ = gen.make_topology(n, seed)
            idir = os.path.join("results", exp, "inputs", f"n{n}_s{seed}")
            os.makedirs(os.path.join(REPO, idir), exist_ok=True)
            topo = os.path.join(idir, "topology.csv")
            gen.write_topology(os.path.join(REPO, topo), xy)
            fl = burst_flows(g, 20, seed, DAY0_S, KERALA_SIM_S - 2)
            ffile = os.path.join(idir, "flows_bursts.csv")
            gen.write_flows(os.path.join(REPO, ffile), fl)

            rng = np.random.default_rng(gen.topo_seed(n, seed) + 91_000)
            death_day = rng.uniform(19, 37, size=n)
            idle_life = day(death_day) - 0  # radios are on from t = 0
            bfile = os.path.join(idir, "battery.csv")
            with open(os.path.join(REPO, bfile), "w") as f:
                f.write("node,initial_J\n")
                for i, life in enumerate(idle_life):
                    f.write(f"{i},{battery_for_idle_life(life, 0.273):.4f}\n")

            elev = kerala_elevation(xy, seed)
            gen.write_json(os.path.join(REPO, idir, "kerala_assumptions.json"), KERALA_ASSUMPTIONS)
            with open(os.path.join(REPO, idir, "elevation.csv"), "w") as f:
                f.write("node,x,y,relative_height\n")
                for i in range(n):
                    f.write(f"{i},{xy[i][0]:.3f},{xy[i][1]:.3f},{elev[i]:.4f}\n")

            models = [("control", None, None)]
            for peak in (0.27, 0.50):
                low_first = list(np.argsort(elev, kind="stable"))
                rnd = list(np.random.default_rng(gen.topo_seed(n, seed) + 92_000 + int(peak * 100)).permutation(n))
                models.append(("kerala", peak, low_first))
                models.append(("uniform", peak, rnd))
            for model, peak, order in models:
                tag = model if peak is None else f"{model}_{int(round(peak * 100))}"
                events = [] if order is None else flood_schedule(order, n, peak)
                efile = os.path.join(idir, f"events_{tag}.csv")
                gen.write_events(os.path.join(REPO, efile), events)
                failed = [e[3] for e in events]
                h = g.copy()
                h.remove_nodes_from(failed)
                meta = {
                    "scenario": tag, "selection": {"kerala": "spatially correlated (lowest ground first)",
                                                   "uniform": "uniformly random (seeded)",
                                                   "control": "none"}[model],
                    "assumption": KERALA_ASSUMPTIONS.get(
                        {"kerala": "spatial_pattern", "uniform": "uniform_random_baseline",
                         "control": "no_failure_control"}[model]),
                    "failure_start_s": events[0][0] if events else None, "failure_end_s": None,
                    "failed_nodes": [{"node": int(e[3]), "time_s": e[0], "x": round(float(xy[e[3]][0]), 2),
                                      "y": round(float(xy[e[3]][1]), 2)} for e in events],
                    "n_failed_nodes": len(failed), "pct_failed_nodes": round(100 * len(failed) / n, 2),
                    "n_failed_links": 0, "pct_failed_links": 0.0,
                    "components_at_peak_flood": nx.number_connected_components(h) if len(h) else 0,
                    "battery_depletion": "yes (see battery.csv; no recharging)",
                }
                gen.write_json(os.path.join(REPO, idir, f"scenario_{tag}.json"), meta)
                for proto in protocols:
                    runs.append(dict(
                        experiment=exp, run_id=f"{proto}_{tag}_n{n}_s{seed}", protocol=proto, scenario=model,
                        nodes=n, seed=seed, rng_run=seed, n_flows=len(fl), severity=peak,
                        severity_label=("battery depletion only" if peak is None else
                                        f"{len(failed)} nodes flooded ({meta['pct_failed_nodes']}%) + batteries"),
                        topo=topo, flows_file=ffile, events_file=efile, energy_file=bfile,
                        energy_j=0, energy_model="states",
                        fail_time_s=meta["failure_start_s"], restore_time_s=None,
                        traffic_start_s=DAY0_S, traffic_stop_s=KERALA_SIM_S - 2, sim_time_s=KERALA_SIM_S,
                        payload_bytes=gen.PAYLOAD_B, range_m=gen.RANGE_M, deadline_s=1.0,
                        windows=windows, timeseries=True, connectivity=True, flows=fl,
                    ))
    return runs
