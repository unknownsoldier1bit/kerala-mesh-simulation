"""Tables, figures and statistical tests for the Chalakudy experiment.

Usage, from the repo root:
    python3 experiments/analyze_chalakudy.py
Outputs go to results/analysis_chalakudy/ (tables/*.csv, figures/*.png and *.pdf, FINDINGS.md).
It reads only results/chalakudy*/ and data/chalakudy/, so the analysis of the other experiments
(results/analysis/) is untouched.

Statistics as in analyze.py: every protocol ran on the same devices, traffic, failures and batteries
for a given seed, so protocols are compared with paired tests across seeds (Friedman over the three
protocols, then two-sided Wilcoxon signed-rank tests per pair with Holm correction). Flood vs
uniform-random failures are compared the same way for each protocol (paired by seed, Holm over the
three protocols).
"""

import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze as A  # noqa: E402  (shared style, statistics and plotting helpers)
import chalakudy as C  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

plt = A.plt
OUT = os.path.join(A.RES, "analysis_chalakudy")
TAB = os.path.join(OUT, "tables")
FIG = os.path.join(OUT, "figures")
A.FIG = FIG  # A.savefig writes here

EXPS = ["chalakudy", "chalakudy_prop", "chalakudy_share", "chalakudy_battery", "chalakudy_traffic"]
PROTOCOLS = A.PROTOCOLS
MUTED = "#898781"
WATER, RIVER = "#9ec5f4", "#256abf"  # blue sequential steps 200 and 500 (dataviz reference palette)
FAILED = "#e34948"  # categorical slot 8 (never a protocol colour here)

RUN_RE = re.compile(r"^(?P<protocol>aodv|olsr|dsdv)_(?P<tag>control|flood\d+|uniform\d+)_on(?P<onset>\d+)_"
                    r"(?P<battery>nobatt|batt\d+)_g(?P<gap>[\d.]+)_n(?P<nodes>\d+)_s(?P<seed>\d+)$")
WINDOWS = {"before_onset": "Before onset (14 Aug - onset)", "acute": "Acute (onset - 18 Aug)",
           "sustained": "Sustained (18 - 27 Aug)"}
MODEL_LABEL = {"control": "No flooding", "flood": "Flood (real data)", "uniform": "Uniform random"}
REAL_VS_ASSUMED = ("Real data: building positions, ground height, Sentinel-1 water, event dates. Assumed: devices "
                   "per building, flooded share, power cut, batteries, traffic, 150 m range, 1 day = 30 s.")

METRICS = (["within_1s_pct", "connected_within_1s_pct", "pdr_pct", "connected_pdr_pct", "within_0.5s_pct",
            "within_2s_pct", "within_5s_pct", "delay_mean_ms", "delay_median_ms", "control_pkts_per_node_s",
            "nodes_depleted", "sent_while_connected", "packets_sent", "energy_mean_per_node_J",
            "route_validity_mean_pct", "route_validity_at_traffic_start"]
           + [f"{w}_{m}" for w in WINDOWS for m in ("within_1s_pct", "connected_within_1s_pct", "pdr_pct",
                                                    "connected_pdr_pct", "delay_mean_ms",
                                                    "ctrl_pkts_per_node_s")])
CONFIG = ["experiment", "model", "share", "onset", "battery", "gap", "nodes"]


def ensure_dirs():
    for d in (OUT, TAB, FIG):
        os.makedirs(d, exist_ok=True)


def load_all():
    frames = []
    for exp in EXPS:
        p = os.path.join(A.RES, exp, "summary.csv")
        if not os.path.exists(p):
            continue
        df = pd.read_csv(p)
        parts = df.run_id.str.extract(RUN_RE)
        assert parts.notna().all().all(), f"unparsed run ids in {exp}"
        df = df.drop(columns=[c for c in ("protocol", "nodes", "seed") if c in df]).join(parts)
        df["experiment"] = exp
        df["model"] = df.tag.str.extract(r"^([a-z]+)")[0]
        df["share"] = pd.to_numeric(df.tag.str.extract(r"(\d+)$")[0]).fillna(0).astype(int)
        df["onset"] = df.onset.astype(int)
        df["gap"] = df.gap.astype(float)
        df["nodes"] = df.nodes.astype(int)
        df["seed"] = df.seed.astype(int)
        frames.append(df)
    if not frames:
        return None
    df = pd.concat(frames, ignore_index=True)
    n = df.groupby(CONFIG + ["protocol"]).seed.transform("count")
    return df[n >= A.MIN_SEEDS].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Tables and tests
# ---------------------------------------------------------------------------


def model_tests(df, metrics):
    """Flood vs uniform-random, flood vs control and uniform vs control, per protocol, paired by seed."""
    rows = []
    keys = ["experiment", "onset", "battery", "gap", "nodes"]
    for k, g in df.groupby(keys):
        for share in sorted(set(g.share) - {0}):
            for a, b in (("flood", "uniform"), ("flood", "control"), ("uniform", "control")):
                ga = g[(g.model == a) & (g.share == share)]
                gb = g[(g.model == b) & (g.share == (share if b != "control" else 0))]
                if ga.empty or gb.empty:
                    continue
                for m in metrics:
                    res = []
                    for p in PROTOCOLS:
                        x = ga[ga.protocol == p].set_index("seed")[m]
                        y = gb[gb.protocol == p].set_index("seed")[m]
                        d = (x - y).dropna().round(9)
                        if len(d) < 5:
                            continue
                        pval = 1.0 if (d == 0).all() else stats.wilcoxon(d, zero_method="wilcox").pvalue
                        res.append(dict(zip(keys, k), share=share, comparison=f"{a}_minus_{b}", metric=m,
                                        protocol=p, n_seeds=len(d), mean_a=float(x.mean()), mean_b=float(y.mean()),
                                        median_diff=float(d.median()), wilcoxon_p=pval))
                    order = np.argsort([r["wilcoxon_p"] for r in res])
                    running = 0.0
                    for rank, i in enumerate(order):
                        running = max(running, min(1.0, (len(res) - rank) * res[i]["wilcoxon_p"]))
                        res[i]["holm_p"] = running
                    rows += res
    return pd.DataFrame(rows)


def scenario_table():
    rows = []
    for f in sorted(glob.glob(os.path.join(A.RES, "chalakudy*", "inputs", "*", "scenario_*.json"))):
        exp = f.split(os.sep)[-4]
        if exp not in EXPS:
            continue
        m = json.load(open(f))
        n, seed = map(int, re.search(r"n(\d+)_s(\d+)", f).groups())
        net = json.load(open(os.path.join(os.path.dirname(f), "network.json")))
        rows.append(dict(experiment=exp, nodes=n, seed=seed, scenario=m["scenario"], onset_day=m["onset_day"],
                         n_failed_nodes=m["n_failed_nodes"], pct_failed_nodes=m["pct_failed_nodes"],
                         n_observed_flooded_in_sample=m["n_observed_flooded_in_sample"],
                         components_at_peak=m["components_at_peak"], mean_degree=net["mean_degree"],
                         largest_component_share=net["largest_component_share"],
                         diameter=net["diameter_largest_component"]))
    d = pd.DataFrame(rows)
    d.to_csv(os.path.join(TAB, "scenario_properties.csv"), index=False)
    return d


def checks(df):
    lines = []
    # failed runs and error output
    rows = []
    for exp in EXPS + ["chalakudy_check"]:
        f = os.path.join(A.RES, exp, "failed_runs.csv")
        if os.path.exists(f):
            d = pd.read_csv(f)
            rows += [dict(experiment=exp, **r) for r in d.to_dict("records")]
    pd.DataFrame(rows, columns=["experiment", "run_id", "reason"]).to_csv(
        os.path.join(TAB, "check_failed_runs.csv"), index=False)
    nonempty = sorted(os.path.relpath(p, A.REPO) for exp in EXPS + ["chalakudy_check"]
                      for p in glob.glob(os.path.join(A.RES, exp, "runs", "*", "stderr.log"))
                      if os.path.getsize(p) > 0)
    pd.DataFrame(dict(stderr_file=nonempty)).to_csv(os.path.join(TAB, "check_nonempty_stderr.csv"), index=False)
    lines.append(f"failed runs: {len(rows)}; runs with non-empty stderr: {len(nonempty)}")

    # routing packets sent as IP fragments (see docs/ns3-defaults.md)
    frag = []
    for exp in EXPS:
        for p in glob.glob(os.path.join(A.RES, exp, "runs", "*", "stdout.log")):
            m = re.search(r"fragmented_routing_packets=(\d+)", open(p).read())
            frag.append(dict(experiment=exp, run_id=os.path.basename(os.path.dirname(p)),
                             fragmented_routing_packets=int(m.group(1)) if m else np.nan))
    fr = pd.DataFrame(frag).sort_values(["experiment", "run_id"])
    fr.to_csv(os.path.join(TAB, "check_fragmented_routing_packets.csv"), index=False)
    if len(fr):
        g = fr.assign(protocol=fr.run_id.str.split("_").str[0]).groupby("protocol").fragmented_routing_packets
        lines.append("fragmented routing packets per run (mean, max): " + ", ".join(
            f"{p} {v.mean():.1f}, {v.max():.0f}" for p, v in g))

    # routing tables at traffic start and in steady state, no-flood control (warm-up rule)
    c = df[(df.model == "control") & df.protocol.isin(["olsr", "dsdv"])]
    if len(c):
        conv = c.groupby(["experiment", "battery", "protocol"]).agg(
            runs=("seed", "size"), validity_at_traffic_start_mean=("route_validity_at_traffic_start", "mean"),
            validity_at_traffic_start_min=("route_validity_at_traffic_start", "min"),
            validity_mean_pct=("route_validity_mean_pct", "mean")).reset_index()
        conv.to_csv(os.path.join(TAB, "check_routing_tables_control.csv"), index=False)
        main = conv[(conv.experiment == "chalakudy") & (conv.battery == "nobatt")]
        lines.append("route validity at traffic start (no flooding, no battery limit): " + ", ".join(
            f"{r.protocol} mean {r.validity_at_traffic_start_mean:.3f} (min {r.validity_at_traffic_start_min:.3f}), "
            f"whole-run mean {r.validity_mean_pct:.1f}%" for r in main.itertuples()))

    # FlowMonitor vs packet tracker, ns-3 energy framework vs state-based count (chalakudy_check)
    fm, en = [], []
    for rd in sorted(glob.glob(os.path.join(A.RES, "chalakudy_check", "runs", "*"))):
        sj = os.path.join(rd, "summary.json")
        if not os.path.exists(sj):
            continue
        s = json.load(open(sj))
        xml = os.path.join(rd, "flowmon.xml.gz")
        if os.path.exists(xml):
            import gzip
            import xml.etree.ElementTree as ET
            root = ET.fromstring(gzip.open(xml).read())
            cls = {f.get("flowId"): f for f in root.iter("Flow") if f.get("destinationPort")}
            tx = rx = 0
            for f in root.find("FlowStats").iter("Flow"):
                cf = cls.get(f.get("flowId"))
                if cf is None or int(cf.get("destinationPort")) < 10000:
                    continue
                tx += int(f.get("txPackets"))
                rx += int(f.get("rxPackets"))
            pk = pd.read_csv(os.path.join(rd, "packets.csv.gz"), usecols=["tx_s", "rx_s"])
            fm.append(dict(run_id=os.path.basename(rd), tracker_sent=s["packets_sent"],
                           tracker_refused_at_source=s["lost_no_route_at_source"],
                           tracker_received=s["packets_received"],
                           tracker_received_within_10s=int(((pk.rx_s - pk.tx_s) <= 10.0).sum()),
                           flowmon_tx=tx, flowmon_rx=rx))
        e = pd.read_csv(os.path.join(rd, "energy.csv"))
        if e.consumed_ns3_J.notna().all():
            rel = ((e.consumed_J - e.consumed_ns3_J).abs() / e.consumed_ns3_J.replace(0, np.nan)).max()
            dep = e[e.depleted_s.notna()]
            en.append(dict(run_id=os.path.basename(rd), state_based_total_J=e.consumed_J.sum(),
                           ns3_energy_model_total_J=e.consumed_ns3_J.sum(), max_relative_difference=rel,
                           nodes_depleted=len(dep)))
    if fm:
        d = pd.DataFrame(fm)
        d.to_csv(os.path.join(TAB, "check_tracker_vs_flowmonitor.csv"), index=False)
        lines.append(f"FlowMonitor check ({len(d)} runs, 50 devices): max |received - FlowMonitor rx| "
                     f"{(d.tracker_received - d.flowmon_rx).abs().max()}, counting only packets delivered within "
                     f"10 s {(d.tracker_received_within_10s - d.flowmon_rx).abs().max()}; max |sent - refused at "
                     f"source - FlowMonitor tx| {(d.tracker_sent - d.tracker_refused_at_source - d.flowmon_tx).abs().max()}")
    if en:
        d = pd.DataFrame(en)
        d.to_csv(os.path.join(TAB, "check_energy_vs_ns3_model.csv"), index=False)
        lines.append(f"energy check ({len(d)} runs, 50 devices): max relative difference per device "
                     f"{d.max_relative_difference.max():.2e}")
    return lines


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def fig_study_area():
    """Map of the study square: buildings, the devices of seed 1, which of them fail, and radar water."""
    import rasterio.transform
    area = json.load(open(os.path.join(C.DATA, "study_area.json")))
    x0, y0 = area["x0"], area["y0"]
    transform, perm, flood = C.flood_masks()
    b = pd.read_csv(os.path.join(C.DATA, "buildings.csv"))
    m = 600.0
    view = b[(b.x > x0 - m) & (b.x < x0 + 1000 + m) & (b.y > y0 - m) & (b.y < y0 + 1000 + m)]
    rows, cols = perm.shape
    xs, ys = rasterio.transform.xy(transform, [0, rows - 1], [0, cols - 1])
    extent = (xs[0] - 5, xs[1] + 5, ys[1] - 5, ys[0] + 5)
    idir = os.path.join(A.RES, "chalakudy", "inputs", "n100_s1")
    nodes = pd.read_csv(os.path.join(idir, "nodes.csv"))
    sc = json.load(open(os.path.join(idir, "scenario_flood25_on15.json")))
    failed = {f["node"] for f in sc["failed_nodes"]}
    fig, ax = plt.subplots(figsize=(6.4, 6.4))
    water = np.zeros(perm.shape + (4,))
    fl = flood["2018-08-21T0040_des"] | flood["2018-08-21T1306_asc"]
    for mask, col in ((fl, WATER), (perm, RIVER)):
        rgb = matplotlib_rgba(col)
        water[mask] = rgb
    ax.imshow(water, extent=extent, origin="upper", interpolation="nearest", zorder=1)
    ax.scatter(view.x, view.y, s=1.5, color=MUTED, alpha=0.5, lw=0, zorder=2)
    alive = nodes[~nodes.node.isin(failed)]
    dead = nodes[nodes.node.isin(failed)]
    ax.scatter(alive.utm_x, alive.utm_y, s=22, facecolor=A.SURFACE, edgecolor=A.INK, lw=1.2, zorder=4)
    ax.scatter(dead.utm_x, dead.utm_y, s=26, color=FAILED, edgecolor=A.SURFACE, lw=1.0, zorder=5)
    ax.plot([x0, x0 + 1000, x0 + 1000, x0, x0], [y0, y0, y0 + 1000, y0 + 1000, y0], color=A.INK, lw=1.2, zorder=3)
    ax.set_xlim(x0 - m, x0 + 1000 + m)
    ax.set_ylim(y0 - m, y0 + 1000 + m)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    handles = [plt.Line2D([], [], ls="", marker="s", color=RIVER, ms=8, label="Permanent water (Sentinel-1, Jan-May)"),
               plt.Line2D([], [], ls="", marker="s", color=WATER, ms=8, label="Flood water still visible 21 Aug (Sentinel-1)"),
               plt.Line2D([], [], ls="", marker="o", color=MUTED, ms=3, label="Building (Overture)"),
               plt.Line2D([], [], ls="", marker="o", mfc=A.SURFACE, mec=A.INK, ms=6, label="Device that stays up"),
               plt.Line2D([], [], ls="", marker="o", color=FAILED, ms=6, label="Device lost to flooding (lowest ground first)")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=2, fontsize=7.5)
    ax.set_title("Study square (1 km, black outline): 100 devices of seed 1, flood scenario with 25% lost")
    A.savefig(fig, "chalakudy_study_area",
              "Real: buildings, radar water, ground-height order. Assumed: which buildings have devices, 25% lost.")


def matplotlib_rgba(hexcol):
    import matplotlib.colors
    return matplotlib.colors.to_rgba(hexcol)


def fig_network_density():
    p = os.path.join(C.DATA, "network_structure.csv")
    if not os.path.exists(p):
        return
    d = pd.read_csv(p)
    d = d[d.placement.isin(["uniform", "uniform random in a 500 m square, redrawn until connected"])]
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.2))
    for ax, col, lab in ((axes[0], "mean_degree", "Mean neighbours per device"),
                         (axes[1], "largest_component_share", "Largest connected group (share of devices)")):
        for rng, style in ((150.0, dict(color=A.INK, ls="-", marker="o")),
                           (C.P("effective_range_m"), dict(color=MUTED, ls="--", marker="o"))):
            # Chalakudy: devices in the 1 km2 square
            q = d[(d.source.str.startswith("chalakudy")) & (d.range_m == rng)].groupby("nodes")[col].mean()
            ax.plot(q.index, q.values, ms=5, label=f"Chalakudy buildings, {rng:g} m", **style)
        # main grid: 25/50/100 nodes in a 500 m square = 100/200/400 per km2
        g = d[d.source == "main_grid"].groupby("nodes")[col].mean()
        ax.plot(g.index / 0.25, g.values, ls="", marker="s", ms=6, mfc=A.SURFACE, mec=A.INK,
                label="Main grid, 150 m (25/50/100 nodes)")
        ax.set_xscale("log")
        ax.set_xlabel("Devices per km² (log scale)")
        ax.set_ylabel(lab)
    axes[1].set_ylim(0, 1.05)
    axes[0].legend(fontsize=7.5)
    A.savefig(fig, "chalakudy_network_density",
              "Graph structure only (no simulation). 62.8 m = range under the cited 3GPP NLOS model; mean of seeds "
              "1-10. Real data: building positions.")


def bars_by_window(agg, sel, metric_suffix, fname, title, onsets):
    protos = [p for p in PROTOCOLS if p in set(agg.protocol)]
    models = [m for m in ("control", "flood", "uniform") if m in set(agg.model)]
    fig, axes = plt.subplots(len(onsets), 3, figsize=(9.6, 3.0 * len(onsets)), sharey=True, squeeze=False)
    for i, onset in enumerate(onsets):
        a = agg[sel(agg) & (agg.onset == onset)]
        for j, w in enumerate(WINDOWS):
            ax = axes[i, j]
            A.grouped_bars(ax, a, models, "model", f"{w}_{metric_suffix}", protos, MODEL_LABEL)
            ax.set_title(f"{WINDOWS[w]}; onset {onset} Aug")
            ax.set_ylim(0, 100)
        axes[i, 0].set_ylabel("Delivered within T = 1 s (%)")
    A.legend_protocols(fig, protos)
    A.savefig(fig, fname, title + " " + REAL_VS_ASSUMED)


def fig_over_time(df):
    ts_path = os.path.join(A.RES, "chalakudy", "timeseries.csv")
    if not os.path.exists(ts_path):
        return
    ts = pd.read_csv(ts_path).merge(df[df.experiment == "chalakudy"][["run_id", "protocol", "model", "onset",
                                                                      "battery"]], on="run_id")
    for battery in sorted(set(ts.battery)):
        sub = ts[(ts.onset == 15) & (ts.battery == battery)]
        models = [m for m in ("control", "flood", "uniform") if m in set(sub.model)]
        if not models:
            continue
        fig, axes = plt.subplots(2, len(models), figsize=(3.3 * len(models), 5.2), sharex=True, sharey="row",
                                 squeeze=False)
        for j, m in enumerate(models):
            q0 = sub[sub.model == m]
            for p in PROTOCOLS:
                q = q0[q0.protocol == p]
                if q.empty:
                    continue
                g = q.groupby("t_start_s")
                axes[0, j].plot(g.alive_nodes.mean().index, g.alive_nodes.mean().values, color=A.COLOR[p])
                tot = g[["sent", "delivered_within_1s"]].sum()
                share = 100 * tot.delivered_within_1s / tot.sent.replace(0, np.nan)
                axes[1, j].plot(share.index, share.values, color=A.COLOR[p], marker=A.MARKER[p], ms=3, lw=1.5)
            axes[0, j].set_title(MODEL_LABEL[m])
            for ax in axes[:, j]:
                ax.axvline(C.day(15), color=MUTED, lw=1, ls="--")
                ax.axvline(C.day(18), color=A.INK2, lw=1)
            axes[1, j].set_xlabel("Simulated time (s); dashed = 15 Aug, solid = 18 Aug")
            axes[1, j].set_ylim(0, 100)
        axes[0, 0].set_ylabel("Devices still running")
        axes[1, 0].set_ylabel("Delivered within 1 s (%), all seeds")
        A.legend_protocols(fig, PROTOCOLS)
        A.savefig(fig, f"chalakudy_over_time_on15_{battery}",
                  "Onset 15 Aug; 10 s bins pooled over seeds 1-10. " + REAL_VS_ASSUMED)


def fig_sensitivity(df):
    """Acute-phase delivery within T for the flood and uniform models across the swept parameters."""
    panels = []
    main = df[(df.experiment == "chalakudy") & (df.onset == 15) & (df.battery == "nobatt")]
    share = pd.concat([main, df[df.experiment == "chalakudy_share"]])
    if share.share.nunique() > 1:
        panels.append(("share", share[share.model != "control"], "Devices lost to flooding at the peak (%)",
                       sorted(set(share.share) - {0})))
    traffic = pd.concat([main, df[df.experiment == "chalakudy_traffic"]])
    if traffic.gap.nunique() > 1:
        panels.append(("gap", traffic[traffic.model != "control"], "Mean gap between message bursts (s)",
                       sorted(set(traffic.gap))))
    batt = df[(df.battery != "nobatt") & (df.onset == 15) & df.experiment.isin(["chalakudy", "chalakudy_battery"])]
    if batt.battery.nunique() > 1:
        batt = batt.assign(radio_share=batt.battery.str[4:].astype(int))
        panels.append(("radio_share", batt[batt.model != "control"], "Battery share left for the radio (%)",
                       sorted(set(batt.radio_share))))
    if not panels:
        return
    metric = "acute_within_1s_pct"
    fig, axes = plt.subplots(2, len(panels), figsize=(3.4 * len(panels), 5.6), sharey=True, squeeze=False)
    for j, (col, d, xlabel, xs) in enumerate(panels):
        for i, model in enumerate(("flood", "uniform")):
            ax = axes[i, j]
            for k, p in enumerate(PROTOCOLS):
                q = d[(d.model == model) & (d.protocol == p)]
                mean = [q[q[col] == x][metric].mean() for x in xs]
                err = [A.ci95(q[q[col] == x][metric]) for x in xs]
                pos = np.arange(len(xs)) + (k - 1) * 0.12
                ax.errorbar(pos, mean, yerr=A.clip_err(mean, err, 100), color=A.COLOR[p], marker=A.MARKER[p],
                            ms=5, capsize=2)
            ax.set_xticks(np.arange(len(xs)))
            ax.set_xticklabels([f"{x:g}" for x in xs])
            ax.set_title(MODEL_LABEL[model])
            ax.set_ylim(0, 100)
            if i == 1:
                ax.set_xlabel(xlabel)
        axes[0, j].set_ylabel("Acute phase: within T = 1 s (%)")
        axes[1, j].set_ylabel("Acute phase: within T = 1 s (%)")
    A.legend_protocols(fig, PROTOCOLS)
    A.savefig(fig, "chalakudy_sensitivity_acute",
              "One parameter changed at a time from the main setting (25%, 15 s, 50%); onset 15 Aug. All swept "
              "values are assumptions. Error bars: 95% CI over seeds, clipped to 0-100%.")


# ---------------------------------------------------------------------------
# Digest
# ---------------------------------------------------------------------------


def findings_md(agg, ptests, mtests, check_lines, scen):
    def cell(r, m):
        mean, ci = r.get(f"{m}_mean", np.nan), r.get(f"{m}_ci95", np.nan)
        if pd.isna(mean):
            return "-"
        return f"{mean:.1f} ± {ci:.1f}" if not pd.isna(ci) else f"{mean:.1f}"

    lines = ["# Chalakudy results digest", "",
             "Generated by `experiments/analyze_chalakudy.py` from `results/chalakudy*/summary.csv`. Mean ± 95% CI "
             "over seeds 1-10 (paired: same devices, flows, failures and batteries for every protocol). Numbers "
             "only; read `data/chalakudy/PROVENANCE.md` for what is real data and what is assumed.", "",
             "Window names: before onset = 14 Aug to the onset day; acute = onset to 18 Aug; sustained = 18 to 27 "
             "Aug. 'connected' = only packets sent while the unit-disk graph of working devices had a path.", ""]
    lines += ["## Checks", ""] + [f"- {x}" for x in check_lines] + [""]
    if scen is not None and len(scen):
        s = scen[scen.experiment == "chalakudy"].groupby(["nodes", "scenario", "onset_day"]).agg(
            seeds=("seed", "size"), failed=("n_failed_nodes", "mean"), observed=("n_observed_flooded_in_sample", "mean"),
            components_at_peak=("components_at_peak", "mean"), mean_degree=("mean_degree", "mean"),
            largest_component=("largest_component_share", "mean")).reset_index()
        lines += ["## Scenario properties (main experiment)", "", A.md_table(s), ""]
    for exp, title in (("chalakudy", "Main experiment"), ("chalakudy_prop", "Propagation sensitivity (log-distance)"),
                       ("chalakudy_share", "Peak flooded share"), ("chalakudy_battery", "Battery share for the radio"),
                       ("chalakudy_traffic", "Traffic (mean gap between bursts)")):
        a = agg[agg.experiment == exp]
        if a.empty:
            continue
        lines += [f"## {title} (`{exp}`)", ""]
        cols = ["model", "share", "onset", "battery", "gap", "protocol"]
        out = []
        for _, r in a.sort_values(cols).iterrows():
            row = {c: r[c] for c in cols}
            for m, lab in (("before_onset_within_1s_pct", "before onset"), ("acute_within_1s_pct", "acute"),
                           ("sustained_within_1s_pct", "sustained"),
                           ("acute_connected_within_1s_pct", "acute, connected"),
                           ("sustained_connected_within_1s_pct", "sustained, connected"),
                           ("pdr_pct", "PDR whole run"), ("control_pkts_per_node_s", "control pkts/node/s")):
                row[lab] = cell(r, m)
            out.append(row)
        lines += ["Delivered within T = 1 s (%), by window:", "", A.md_table(pd.DataFrame(out)), ""]
        pt = ptests[(ptests.experiment == exp) & ptests.metric.isin(["acute_within_1s_pct", "sustained_within_1s_pct"])]
        sig = []
        for _, r in pt.iterrows():
            for a_, b_ in (("aodv", "olsr"), ("aodv", "dsdv"), ("olsr", "dsdv")):
                hp = r.get(f"holm_p_{a_}_{b_}", np.nan)
                if not pd.isna(hp) and hp < 0.05:
                    sig.append(dict(model=r.model, share=r.share, onset=r.onset, battery=r.battery, gap=r.gap,
                                    metric=r.metric, pair=f"{a_} - {b_}",
                                    median_diff=round(r[f"median_diff_{a_}_minus_{b_}"], 2), holm_p=f"{hp:.3g}"))
        lines += ["Protocol differences with Holm-corrected p < 0.05 (paired Wilcoxon over seeds):", "",
                  A.md_table(pd.DataFrame(sig)) if sig else "none", ""]
        mt = mtests[(mtests.experiment == exp) & (mtests.comparison == "flood_minus_uniform")
                    & mtests.metric.isin(["acute_within_1s_pct", "sustained_within_1s_pct",
                                          "acute_connected_within_1s_pct"])] if len(mtests) else mtests
        if len(mt):
            t = mt[["share", "onset", "battery", "gap", "metric", "protocol", "mean_a", "mean_b", "median_diff",
                    "holm_p"]].rename(columns={"mean_a": "flood_mean", "mean_b": "uniform_mean"})
            lines += ["Flood (real-data order) minus uniform-random failures, same counts and times, paired by seed "
                      "(Holm over the three protocols):", "", A.md_table(t.round(4)), ""]
    with open(os.path.join(OUT, "FINDINGS.md"), "w") as fh:
        fh.write("\n".join(lines))


def main():
    ensure_dirs()
    df = load_all()
    if df is None:
        print("no Chalakudy results yet")
        return
    keys = CONFIG + ["protocol"]
    agg = A.aggregate(df, keys, METRICS)
    agg.to_csv(os.path.join(TAB, "chalakudy_by_config.csv"), index=False)
    ptests = A.paired_tests(df, CONFIG, METRICS)
    ptests.to_csv(os.path.join(TAB, "chalakudy_protocol_tests.csv"), index=False)
    mtests = model_tests(df, [m for m in METRICS if "within" in m or "pdr" in m])
    mtests.to_csv(os.path.join(TAB, "chalakudy_flood_vs_uniform_tests.csv"), index=False)
    scen = scenario_table()
    check_lines = checks(df)
    main_ = lambda a: (a.experiment == "chalakudy") & (a.battery == "nobatt")  # noqa: E731
    onsets = sorted(set(agg[agg.experiment == "chalakudy"].onset))
    if onsets:
        bars_by_window(agg, main_, "within_1s_pct", "chalakudy_within_T_by_window",
                       "All packets sent; no battery limit.", onsets)
        bars_by_window(agg, main_, "connected_within_1s_pct", "chalakudy_connected_within_T_by_window",
                       "Only packets sent while a path existed; no battery limit.", onsets)
        batt = lambda a: (a.experiment == "chalakudy") & (a.battery == "batt50")  # noqa: E731
        if batt(agg).any():
            bars_by_window(agg, batt, "within_1s_pct", "chalakudy_within_T_by_window_battery",
                           "All packets sent; batteries limited (50% for the radio).", onsets)
    prop = lambda a: a.experiment == "chalakudy_prop"  # noqa: E731
    if prop(agg).any():
        bars_by_window(agg, prop, "within_1s_pct", "chalakudy_prop_within_T_by_window",
                       "Log-distance radio (3GPP TR 37.885 NLOS, 62.8 m); same devices and flows as the main runs.",
                       sorted(set(agg[prop(agg)].onset)))
    fig_over_time(df)
    fig_sensitivity(df)
    fig_network_density()
    fig_study_area()
    findings_md(agg, ptests, mtests, check_lines, scen)
    print(f"{len(df)} runs analysed;", "; ".join(check_lines))


if __name__ == "__main__":
    main()
