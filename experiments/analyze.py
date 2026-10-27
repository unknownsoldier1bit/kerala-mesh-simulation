"""Tables, figures and statistical tests from the experiment results.

Usage, from the repo root:
    python3 experiments/analyze.py            # everything that has results so far
Outputs go to results/analysis/ (tables/*.csv, figures/*.png and *.pdf, README.md).

Statistics: for a given configuration, every protocol ran on the same topology,
traffic and failure schedule for each seed, so protocols are compared with paired
tests across seeds: a Friedman test over the three protocols, then two-sided
Wilcoxon signed-rank tests for each pair, with Holm correction over the three pairs.
"""

import glob
import gzip
import json
import math
import os
import re
import xml.etree.ElementTree as ET

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from kerala import day  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(REPO, "results")
OUT = os.path.join(RES, "analysis")
TAB = os.path.join(OUT, "tables")
FIG = os.path.join(OUT, "figures")

PROTOCOLS = ["aodv", "olsr", "dsdv"]
LABEL = {"aodv": "AODV", "olsr": "OLSR", "dsdv": "DSDV"}
# Categorical slots 1-3 of the reference palette (validated all-pairs, light mode).
COLOR = {"aodv": "#2a78d6", "olsr": "#eb6834", "dsdv": "#1baf7a"}
MARKER = {"aodv": "o", "olsr": "s", "dsdv": "^"}
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SCEN_ORDER = ["baseline", "link_fail", "node_fail", "multi_fail", "partition", "recovery"]
SCEN_LABEL = {"baseline": "Baseline", "link_fail": "Link failure", "node_fail": "Node failure",
              "multi_fail": "Multiple failures", "partition": "Partition", "recovery": "Recovery"}

KEY_METRICS = {
    "pdr_pct": "PDR (%)",
    "within_1s_pct": "Delivered within T = 1 s (%)",
    "delay_mean_ms": "Mean delay (ms)",
    "delay_median_ms": "Median delay (ms)",
    "delay_p95_ms": "95th-percentile delay (ms)",
    "throughput_kbps": "Throughput (kbps)",
    "control_pkts": "Control packets",
    "control_bytes": "Control bytes",
    "control_pkts_per_node_s": "Control packets per node per second",
    "nrl_ctrl_per_delivered": "Control packets per delivered data packet",
    "loss_pct": "Packet loss (%)",
    "recovery_time_s": "Recovery time (s)",
    "restore_recovery_mean_s": "Recovery after restore (s)",
    "energy_mean_per_node_J": "Energy per node (J)",
}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 9, "axes.titlesize": 10,
    "axes.titlecolor": INK, "legend.frameon": False, "lines.linewidth": 2,
})


def ensure_dirs():
    for d in (OUT, TAB, FIG):
        os.makedirs(d, exist_ok=True)


def load(exp):
    p = os.path.join(RES, exp, "summary.csv")
    return pd.read_csv(p) if os.path.exists(p) else None


def ci95(x):
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) < 2:
        return np.nan
    return stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x))


def aggregate(df, keys, metrics):
    rows = []
    for k, g in df.groupby(keys, dropna=False):
        k = k if isinstance(k, tuple) else (k,)
        row = dict(zip(keys, k))
        row["runs"] = len(g)
        for m in metrics:
            if m not in g:
                continue
            v = g[m].astype(float)
            row[f"{m}_n"] = int(v.notna().sum())
            row[f"{m}_mean"] = v.mean()
            row[f"{m}_std"] = v.std(ddof=1)
            row[f"{m}_ci95"] = ci95(v)
        rows.append(row)
    return pd.DataFrame(rows)


def paired_tests(df, keys, metrics):
    """Friedman over protocols + pairwise Wilcoxon (Holm), paired by seed."""
    rows = []
    for k, g in df.groupby(keys, dropna=False):
        k = k if isinstance(k, tuple) else (k,)
        for m in metrics:
            if m not in g:
                continue
            wide = g.pivot_table(index="seed", columns="protocol", values=m, aggfunc="first")
            protos = [p for p in PROTOCOLS if p in wide]
            wide = wide[protos].dropna()
            base = dict(zip(keys, k), metric=m, n_seeds=len(wide))
            if len(wide) < 5 or len(protos) < 2:
                continue
            if len(protos) >= 3 and (wide.nunique() > 1).any():
                try:
                    fr = stats.friedmanchisquare(*[wide[p] for p in protos])
                    base["friedman_p"] = fr.pvalue
                except ValueError:
                    base["friedman_p"] = np.nan
            pairs = [(a, b) for i, a in enumerate(protos) for b in protos[i + 1:]]
            ps = []
            for a, b in pairs:
                d = wide[a] - wide[b]
                if (d == 0).all():
                    p = 1.0
                else:
                    p = stats.wilcoxon(wide[a], wide[b], zero_method="wilcox", alternative="two-sided").pvalue
                ps.append(p)
                base[f"median_diff_{a}_minus_{b}"] = float(d.median())
                base[f"wilcoxon_p_{a}_{b}"] = p
            order = np.argsort(ps)
            adj = [0.0] * len(ps)
            running = 0.0
            for rank, i in enumerate(order):
                running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
                adj[i] = running
            for (a, b), p in zip(pairs, adj):
                base[f"holm_p_{a}_{b}"] = p
            rows.append(base)
    return pd.DataFrame(rows)


def clip_err(mean, err):
    """Error bars as (lower, upper), with the lower bar stopping at zero."""
    mean = np.asarray(mean, dtype=float)
    err = np.asarray(err, dtype=float)
    return np.vstack([np.minimum(err, np.where(mean > 0, mean, 0)), err])


def savefig(fig, name, note=None):
    fig.tight_layout()
    if note:
        fig.text(0.5, 0, note, ha="center", va="top", color=INK2)
    fig.savefig(os.path.join(FIG, name + ".png"), dpi=200, bbox_inches="tight")
    fig.savefig(os.path.join(FIG, name + ".pdf"), bbox_inches="tight")
    plt.close(fig)


def legend_protocols(fig, protos):
    handles = [plt.Line2D([], [], color=COLOR[p], marker=MARKER[p], lw=2, ms=6, label=LABEL[p]) for p in protos]
    fig.legend(handles=handles, loc="lower center", ncol=len(protos), bbox_to_anchor=(0.5, 1.0))


def grouped_bars(ax, agg, cats, cat_key, metric, protos, cat_labels=None):
    width = min(0.8 / len(protos), 0.26)
    x = np.arange(len(cats))
    for i, p in enumerate(protos):
        sub = agg[agg.protocol == p].set_index(cat_key)
        mean = np.array([sub[f"{metric}_mean"].get(c, np.nan) for c in cats], dtype=float)
        err = np.array([sub[f"{metric}_ci95"].get(c, np.nan) for c in cats], dtype=float)
        ax.bar(x + (i - (len(protos) - 1) / 2) * width, mean, width * 0.9, yerr=clip_err(mean, err), color=COLOR[p],
               error_kw=dict(ecolor=INK2, elinewidth=1, capsize=2), label=LABEL[p])
    ax.set_xticks(x)
    ax.set_xticklabels([(cat_labels or {}).get(c, c) for c in cats], rotation=25, ha="right")


def table_deliverable(df):
    """The per-run summary table in the format of docs/deliverables.md section 7."""

    def rec(v):
        return "unavailable" if pd.isna(v) else round(v, 3)

    return pd.DataFrame({
        "Protocol": df.protocol.str.upper(),
        "Scenario": df.scenario,
        "Node count": df.nodes,
        "Seed / run ID": df.seed.astype(str) + " / " + df.run_id,
        "Failure time (s)": df.fail_time_s,
        "Failure severity": df.failure_severity,
        "Packets sent": df.packets_sent,
        "Packets received": df.packets_received,
        "PDR (%)": df.pdr_pct.round(3),
        "Mean delay (ms)": df.delay_mean_ms.round(3),
        "95th-percentile delay (ms)": df.delay_p95_ms.round(3),
        "Throughput (kbps)": df.throughput_kbps.round(3),
        "Control packets": df.control_pkts,
        "Control bytes": df.control_bytes,
        "Packet loss (count)": df.packets_lost,
        "Packet loss (%)": df.loss_pct.round(3),
        "Recovery time (s)": df.recovery_time_s.map(rec),
        "Energy consumed (J)": df.energy_total_J.round(2) if "energy_total_J" in df else np.nan,
    })


# ---------------------------------------------------------------------------
# Main grid
# ---------------------------------------------------------------------------


def main_grid():
    df = load("main")
    if df is None:
        return []
    notes = []
    metrics = list(KEY_METRICS)
    agg = aggregate(df, ["scenario", "nodes", "protocol"], metrics)
    agg.to_csv(os.path.join(TAB, "main_by_config.csv"), index=False)
    paired_tests(df, ["scenario", "nodes"], metrics).to_csv(os.path.join(TAB, "main_stats_tests.csv"), index=False)
    table_deliverable(df).to_csv(os.path.join(TAB, "summary_table_main.csv"), index=False)
    protos = [p for p in PROTOCOLS if p in set(df.protocol)]
    scens = [s for s in SCEN_ORDER if s in set(df.scenario)]
    nodes = sorted(df.nodes.unique())

    for metric, fname in [("pdr_pct", "main_pdr"), ("within_1s_pct", "main_within_1s"),
                          ("delay_mean_ms", "main_delay_mean"), ("delay_p95_ms", "main_delay_p95"),
                          ("throughput_kbps", "main_throughput"),
                          ("control_pkts_per_node_s", "main_control_per_node_s"),
                          ("nrl_ctrl_per_delivered", "main_nrl"), ("control_bytes", "main_control_bytes"),
                          ("loss_pct", "main_loss"), ("energy_mean_per_node_J", "main_energy_per_node")]:
        fig, axes = plt.subplots(1, len(nodes), figsize=(3.6 * len(nodes), 3.2), sharey=True)
        axes = np.atleast_1d(axes)
        for ax, n in zip(axes, nodes):
            grouped_bars(ax, agg[agg.nodes == n], scens, "scenario", metric, protos, SCEN_LABEL)
            ax.set_title(f"{n} nodes")
        axes[0].set_ylabel(KEY_METRICS[metric])
        legend_protocols(fig, protos)
        savefig(fig, fname, "Bars: mean over seeds; error bars: 95% confidence interval")

    # Recovery: after failure (rerouting) and after restore
    rec_scens = [s for s in ["link_fail", "node_fail", "multi_fail", "recovery"] if s in scens]
    fig, axes = plt.subplots(1, len(nodes), figsize=(3.6 * len(nodes), 3.2), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, n in zip(axes, nodes):
        grouped_bars(ax, agg[agg.nodes == n], rec_scens, "scenario", "recovery_time_s", protos, SCEN_LABEL)
        ax.set_title(f"{n} nodes")
    axes[0].set_ylabel("Recovery time after failure (s)")
    legend_protocols(fig, protos)
    savefig(fig, "main_recovery_after_failure",
            "Mean over affected flows that still had a route; error bars: 95% CI over seeds")

    rs = [s for s in ["partition", "recovery"] if s in scens]
    if rs:
        fig, axes = plt.subplots(1, len(nodes), figsize=(3.6 * len(nodes), 3.0), sharey=True)
        axes = np.atleast_1d(axes)
        for ax, n in zip(axes, nodes):
            grouped_bars(ax, agg[agg.nodes == n], rs, "scenario", "restore_recovery_mean_s", protos, SCEN_LABEL)
            ax.set_title(f"{n} nodes")
        axes[0].set_ylabel("Time to deliver again after restore (s)")
        legend_protocols(fig, protos)
        savefig(fig, "main_recovery_after_restore")

    # Performance vs node density
    for metric, fname in [("pdr_pct", "density_pdr"), ("delay_mean_ms", "density_delay_mean"),
                          ("control_pkts_per_node_s", "density_control_per_node_s"),
                          ("within_1s_pct", "density_within_1s")]:
        fig, axes = plt.subplots(2, 3, figsize=(10, 5.6), sharex=True)
        for ax, sc in zip(axes.flat, scens):
            sub = agg[agg.scenario == sc]
            for p in protos:
                q = sub[sub.protocol == p].sort_values("nodes")
                ax.errorbar(q.nodes, q[f"{metric}_mean"], yerr=clip_err(q[f"{metric}_mean"], q[f"{metric}_ci95"]), color=COLOR[p],
                            marker=MARKER[p], ms=5, capsize=2, label=LABEL[p])
            ax.set_title(SCEN_LABEL[sc])
            ax.set_xticks(nodes)
        for ax in axes[:, 0]:
            ax.set_ylabel(KEY_METRICS[metric])
        for ax in axes[1]:
            ax.set_xlabel("Number of nodes (area fixed at 500 m × 500 m)")
        legend_protocols(fig, protos)
        savefig(fig, fname)

    # Delay distribution and control traffic over time (50 nodes, node failure)
    delay_cdf("main", "node_fail", 50, protos)
    control_over_time("main", "node_fail", 50, protos)
    control_over_time("main", "partition", 50, protos)
    notes.append(f"main: {len(df)} runs")
    return notes


def run_dirs(exp, scenario, n):
    out = {}
    for p in PROTOCOLS:
        out[p] = sorted(glob.glob(os.path.join(RES, exp, "runs", f"{p}_{scenario}_n{n}_f10_s*")))
    return out


def delay_cdf(exp, scenario, n, protos):
    fig, ax = plt.subplots(figsize=(5, 3.4))
    for p, dirs in run_dirs(exp, scenario, n).items():
        if p not in protos or not dirs:
            continue
        d = []
        for rd in dirs:
            f = os.path.join(rd, "packets.csv.gz")
            if os.path.exists(f):
                pk = pd.read_csv(f, usecols=["tx_s", "rx_s"])
                d.append(((pk.rx_s - pk.tx_s) * 1000).dropna().values)
        if not d:
            continue
        x = np.sort(np.concatenate(d))
        ax.plot(x, np.arange(1, len(x) + 1) / len(x), color=COLOR[p], label=LABEL[p])
    ax.set_xscale("log")
    ax.set_xlabel("End-to-end delay of delivered packets (ms, log scale)")
    ax.set_ylabel("Share of delivered packets")
    ax.set_title(f"Delay distribution: {SCEN_LABEL.get(scenario, scenario)}, {n} nodes, all seeds")
    ax.legend(loc="lower right")
    savefig(fig, f"delay_cdf_{scenario}_n{n}")


def control_over_time(exp, scenario, n, protos):
    fig, ax = plt.subplots(figsize=(6, 3.2))
    for p, dirs in run_dirs(exp, scenario, n).items():
        if p not in protos or not dirs:
            continue
        series = []
        for rd in dirs:
            f = os.path.join(rd, "control.csv.gz")
            if os.path.exists(f):
                c = pd.read_csv(f)
                series.append(c.set_index("t_s").pkts / n)
        if not series:
            continue
        m = pd.concat(series, axis=1).mean(axis=1).rolling(5, center=True, min_periods=1).mean()
        ax.plot(m.index, m.values, color=COLOR[p], label=LABEL[p])
    cfg_file = glob.glob(os.path.join(RES, exp, "runs", f"aodv_{scenario}_n{n}_f10_s1", "run_config.json"))
    if cfg_file:
        cfg = json.load(open(cfg_file[0]))
        for t, lab in [(cfg.get("fail_time_s"), "failure"), (cfg.get("restore_time_s"), "restore")]:
            if t:
                ax.axvline(t, color=INK2, lw=1)
                ax.text(t + 2, ax.get_ylim()[1] * 0.95, lab, color=INK2, va="top")
    ax.set_xlabel("Simulation time (s)")
    ax.set_ylabel("Control packets per node per second")
    ax.set_title(f"Routing control traffic over time: {SCEN_LABEL.get(scenario, scenario)}, {n} nodes "
                 "(mean of seeds, 5 s smoothing)")
    ax.legend(loc="upper left", ncol=3)
    savefig(fig, f"control_over_time_{scenario}_n{n}")


# ---------------------------------------------------------------------------
# Severity and load sweeps
# ---------------------------------------------------------------------------


def severity():
    df = load("severity")
    if df is None:
        return []
    metrics = list(KEY_METRICS)
    agg = aggregate(df, ["scenario", "severity", "protocol"], metrics)
    agg.to_csv(os.path.join(TAB, "severity_by_config.csv"), index=False)
    paired_tests(df, ["scenario", "severity"], metrics).to_csv(os.path.join(TAB, "severity_stats_tests.csv"),
                                                              index=False)
    table_deliverable(df).to_csv(os.path.join(TAB, "summary_table_severity.csv"), index=False)
    protos = [p for p in PROTOCOLS if p in set(df.protocol)]
    for metric, fname in [("pdr_pct", "severity_pdr"), ("within_1s_pct", "severity_within_1s"),
                          ("delay_mean_ms", "severity_delay_mean"), ("recovery_time_s", "severity_recovery"),
                          ("control_pkts_per_node_s", "severity_control_per_node_s")]:
        fig, axes = plt.subplots(1, 2, figsize=(8, 3.2), sharey=True)
        for ax, sc, title in zip(axes, ["random_nodes", "random_links"],
                                 ["Random relay-node failures", "Random link failures"]):
            sub = agg[agg.scenario == sc]
            for p in protos:
                q = sub[sub.protocol == p].sort_values("severity")
                ax.errorbar(100 * q.severity, q[f"{metric}_mean"], yerr=clip_err(q[f"{metric}_mean"], q[f"{metric}_ci95"]), color=COLOR[p],
                            marker=MARKER[p], ms=5, capsize=2, label=LABEL[p])
            ax.set_title(title)
            ax.set_xlabel("Failed share (% of all nodes / all links)")
        axes[0].set_ylabel(KEY_METRICS[metric])
        legend_protocols(fig, protos)
        savefig(fig, fname)
    return [f"severity: {len(df)} runs"]


def load_sweep():
    df = load("load")
    if df is None:
        return []
    metrics = list(KEY_METRICS)
    agg = aggregate(df, ["scenario", "n_flows", "protocol"], metrics)
    agg.to_csv(os.path.join(TAB, "load_by_config.csv"), index=False)
    paired_tests(df, ["scenario", "n_flows"], metrics).to_csv(os.path.join(TAB, "load_stats_tests.csv"), index=False)
    table_deliverable(df).to_csv(os.path.join(TAB, "summary_table_load.csv"), index=False)
    protos = [p for p in PROTOCOLS if p in set(df.protocol)]
    for metric, fname in [("pdr_pct", "load_pdr"), ("delay_mean_ms", "load_delay_mean"),
                          ("delay_p95_ms", "load_delay_p95"), ("throughput_kbps", "load_throughput"),
                          ("nrl_ctrl_per_delivered", "load_nrl")]:
        fig, axes = plt.subplots(1, 2, figsize=(8, 3.2), sharey=True)
        for ax, sc in zip(axes, ["baseline", "node_fail"]):
            sub = agg[agg.scenario == sc]
            for p in protos:
                q = sub[sub.protocol == p].sort_values("n_flows")
                ax.errorbar(q.n_flows * 16.384, q[f"{metric}_mean"], yerr=clip_err(q[f"{metric}_mean"], q[f"{metric}_ci95"]), color=COLOR[p],
                            marker=MARKER[p], ms=5, capsize=2, label=LABEL[p])
            ax.set_title(SCEN_LABEL[sc] + ", 50 nodes")
            ax.set_xlabel("Offered load (kbps): 5, 10, 20 flows × 16.4 kbps")
        axes[0].set_ylabel(KEY_METRICS[metric])
        legend_protocols(fig, protos)
        savefig(fig, fname)
    return [f"load: {len(df)} runs"]


# ---------------------------------------------------------------------------
# Energy and Kerala
# ---------------------------------------------------------------------------


def alive_curves(exp, group_col, groups, title_of, fname, t_max):
    ts_path = os.path.join(RES, exp, "timeseries.csv")
    df = load(exp)
    if df is None or not os.path.exists(ts_path):
        return
    ts = pd.read_csv(ts_path).merge(df[["run_id", "protocol", group_col]], on="run_id")
    fig, axes = plt.subplots(2, len(groups), figsize=(3.8 * len(groups), 5.4), sharex=True, squeeze=False)
    for j, gval in enumerate(groups):
        sub = ts[ts[group_col] == gval]
        for p in PROTOCOLS:
            q = sub[sub.protocol == p].groupby("t_start_s")
            if not len(sub[sub.protocol == p]):
                continue
            axes[0, j].plot(q.alive_nodes.mean().index, q.alive_nodes.mean().values, color=COLOR[p],
                            label=LABEL[p])
            tot = q[["sent", "delivered_within_1s"]].sum()
            share = 100 * tot.delivered_within_1s / tot.sent.replace(0, np.nan)
            axes[1, j].plot(share.index, share.values, color=COLOR[p], marker=MARKER[p], ms=3, label=LABEL[p])
        axes[0, j].set_title(title_of(gval))
        axes[1, j].set_xlabel("Simulation time (s)")
        axes[1, j].set_xlim(0, t_max)
    axes[0, 0].set_ylabel("Nodes still running (mean)")
    axes[1, 0].set_ylabel("Sent packets delivered within 1 s (%)")
    legend_protocols(fig, PROTOCOLS)
    savefig(fig, fname)


def energy():
    df = load("energy")
    if df is None:
        return []
    metrics = list(KEY_METRICS) + ["first_depletion_s", "depletion_10pct_s", "depletion_50pct_s",
                                   "radio_tx_time_mean_s", "radio_rx_time_mean_s", "connected_pdr_pct"]
    agg = aggregate(df, ["scenario", "protocol"], metrics)
    agg.to_csv(os.path.join(TAB, "energy_by_config.csv"), index=False)
    paired_tests(df, ["scenario"], metrics).to_csv(os.path.join(TAB, "energy_stats_tests.csv"), index=False)
    table_deliverable(df).to_csv(os.path.join(TAB, "summary_table_energy.csv"), index=False)
    protos = [p for p in PROTOCOLS if p in set(df.protocol)]
    profs = [s for s in ["default_radio", "low_idle_radio"] if s in set(df.scenario)]
    lab = {"default_radio": "ns-3 default radio (idle 0.273 A)", "low_idle_radio": "Low-idle radio (idle 0.033 A)"}
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.2))
    for ax, m, title in zip(axes, ["first_depletion_s", "depletion_10pct_s", "depletion_50pct_s"],
                            ["First node dead", "10% of nodes dead", "50% of nodes dead"]):
        grouped_bars(ax, agg, profs, "scenario", m, protos, {"default_radio": "Default radio",
                                                             "low_idle_radio": "Low-idle radio"})
        ax.set_title(title)
        ax.set_ylabel("Simulation time (s)")
    legend_protocols(fig, protos)
    savefig(fig, "energy_lifetime")
    alive_curves("energy", "scenario", profs, lambda g: lab[g], "energy_over_time", 600)
    return [f"energy: {len(df)} runs"]


def kerala():
    df = load("kerala")
    if df is None:
        return []
    df["model"] = np.where(df.severity.isna(), "control",
                           df.scenario + "_" + (100 * df.severity.fillna(0)).round().astype(int).astype(str))
    metrics = list(KEY_METRICS) + ["connected_pdr_pct", "connected_within_1s_pct", "within_0.5s_pct",
                                   "within_2s_pct", "within_5s_pct", "sent_while_connected", "nodes_depleted",
                                   "acute_14_18aug_within_1s_pct", "sustained_18_27aug_within_1s_pct",
                                   "acute_14_18aug_connected_within_1s_pct",
                                   "sustained_18_27aug_connected_within_1s_pct",
                                   "acute_14_18aug_pdr_pct", "sustained_18_27aug_pdr_pct",
                                   "acute_14_18aug_connected_pdr_pct", "sustained_18_27aug_connected_pdr_pct"]
    agg = aggregate(df, ["model", "nodes", "protocol"], metrics)
    agg.to_csv(os.path.join(TAB, "kerala_by_config.csv"), index=False)
    paired_tests(df, ["model", "nodes"], metrics).to_csv(os.path.join(TAB, "kerala_stats_tests.csv"), index=False)
    table_deliverable(df.assign(scenario=df.model)).to_csv(os.path.join(TAB, "summary_table_kerala.csv"), index=False)
    protos = [p for p in PROTOCOLS if p in set(df.protocol)]
    models = [m for m in ["control", "uniform_27", "kerala_27", "uniform_50", "kerala_50"] if m in set(df.model)]
    mlab = {"control": "No flooding", "uniform_27": "Random 27%", "kerala_27": "Kerala 27%",
            "uniform_50": "Random 50%", "kerala_50": "Kerala 50%"}
    for n in sorted(df.nodes.unique()):
        a = agg[agg.nodes == n]
        fig, axes = plt.subplots(2, 2, figsize=(9, 6), sharey=True)
        for ax, m, title in zip(axes.flat,
                                ["acute_14_18aug_within_1s_pct", "sustained_18_27aug_within_1s_pct",
                                 "acute_14_18aug_connected_within_1s_pct",
                                 "sustained_18_27aug_connected_within_1s_pct"],
                                ["Acute phase (14-18 Aug): all sent packets",
                                 "Sustained phase (18-27 Aug): all sent packets",
                                 "Acute phase: packets sent while a path existed",
                                 "Sustained phase: packets sent while a path existed"]):
            grouped_bars(ax, a, models, "model", m, protos, mlab)
            ax.set_title(title)
        axes[0, 0].set_ylabel("Delivered within T = 1 s (%)")
        axes[1, 0].set_ylabel("Delivered within T = 1 s (%)")
        legend_protocols(fig, protos)
        savefig(fig, f"kerala_within_T_by_phase_n{n}", "Hypothetical, time-compressed scenario anchored to "
                "dated 2018 events; not measured Kerala data. Error bars: 95% CI over seeds")
    for n in sorted(df.nodes.unique()):
        sub = df[df.nodes == n]
        ts_path = os.path.join(RES, "kerala", "timeseries.csv")
        if not os.path.exists(ts_path):
            continue
        ts = pd.read_csv(ts_path).merge(sub[["run_id", "protocol", "model"]], on="run_id")
        fig, axes = plt.subplots(2, len(models), figsize=(3.2 * len(models), 5.2), sharex=True, sharey="row",
                                 squeeze=False)
        for j, m in enumerate(models):
            q0 = ts[ts.model == m]
            for p in protos:
                q = q0[q0.protocol == p].groupby("t_start_s")
                if not len(q0[q0.protocol == p]):
                    continue
                axes[0, j].plot(q.alive_nodes.mean().index, q.alive_nodes.mean().values, color=COLOR[p])
                tot = q[["sent", "delivered_within_1s"]].sum()
                share = (100 * tot.delivered_within_1s / tot.sent.replace(0, np.nan)).rolling(3, min_periods=1).mean()
                axes[1, j].plot(share.index, share.values, color=COLOR[p], marker=MARKER[p], ms=3)
            axes[0, j].set_title(mlab[m])
            for ax in axes[:, j]:
                ax.axvline(day(18), color=INK2, lw=1)  # end of the acute phase
            axes[1, j].set_xlabel("Simulated time (s); line = 18 Aug")
        axes[0, 0].set_ylabel("Nodes still running")
        axes[1, 0].set_ylabel("Delivered within 1 s (%)")
        legend_protocols(fig, protos)
        savefig(fig, f"kerala_over_time_n{n}")
    return [f"kerala: {len(df)} runs"]


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def energy_validation():
    rows = []
    for f in glob.glob(os.path.join(RES, "main", "runs", "*", "energy.csv")):
        e = pd.read_csv(f)
        if e.consumed_ns3_J.notna().all():
            rel = ((e.consumed_J - e.consumed_ns3_J).abs() / e.consumed_ns3_J).max()
            rows.append(dict(run_id=os.path.basename(os.path.dirname(f)), state_based_total_J=e.consumed_J.sum(),
                             ns3_energy_model_total_J=e.consumed_ns3_J.sum(), max_relative_difference=rel))
    if rows:
        pd.DataFrame(rows).sort_values("run_id").to_csv(os.path.join(TAB, "check_energy_vs_ns3_model.csv"),
                                                         index=False)
        return [f"energy check: {len(rows)} runs, max relative difference "
                f"{max(r['max_relative_difference'] for r in rows):.2e}"]
    return []


def flowmon_crosscheck():
    """Compare this project's per-packet tracker with ns-3 FlowMonitor for data flows."""
    rows = []
    for f in glob.glob(os.path.join(RES, "main", "runs", "*", "flowmon.xml.gz")):
        rd = os.path.dirname(f)
        root = ET.fromstring(gzip.open(f).read())
        cls = {fl.get("flowId"): fl for fl in root.iter("Flow") if fl.get("destinationPort")}
        tx = rx = 0
        delay_ns = 0.0
        for fl in root.find("FlowStats").iter("Flow"):
            c = cls.get(fl.get("flowId"))
            if c is None or int(c.get("destinationPort")) < 10000:
                continue
            tx += int(fl.get("txPackets"))
            rx += int(fl.get("rxPackets"))
            delay_ns += float(re.sub(r"[^0-9.e+-]", "", fl.get("delaySum")))
        s = json.load(open(os.path.join(rd, "summary.json")))
        pk = pd.read_csv(os.path.join(rd, "packets.csv.gz"), usecols=["tx_s", "rx_s"])
        within10 = int(((pk.rx_s - pk.tx_s) <= 10.0).sum())
        rows.append(dict(run_id=os.path.basename(rd), tracker_sent=s["packets_sent"],
                         tracker_received_within_10s=within10,
                         tracker_received=s["packets_received"], flowmon_tx=tx, flowmon_rx=rx,
                         tracker_delay_mean_ms=s["delay_mean_ms"],
                         flowmon_delay_mean_ms=delay_ns / rx / 1e6 if rx else np.nan,
                         tracker_socket_refused=s["lost_no_route_at_source"]))
    if rows:
        d = pd.DataFrame(rows).sort_values("run_id")
        d.to_csv(os.path.join(TAB, "check_tracker_vs_flowmonitor.csv"), index=False)
        return [f"FlowMonitor check: {len(d)} runs, max |received difference| "
                f"{(d.tracker_received - d.flowmon_rx).abs().max()}, after excluding packets slower than 10 s: "
                f"{(d.tracker_received_within_10s - d.flowmon_rx).abs().max()}; max |sent difference| after "
                f"excluding source refusals: {(d.tracker_sent - d.tracker_socket_refused - d.flowmon_tx).abs().max()}"]
    return []


def scenario_properties():
    """Averages the scenario metadata (what failed, routes left) per experiment, scenario and size."""
    rows = []
    for f in glob.glob(os.path.join(RES, "*", "inputs", "*", "scenario_*.json")):
        exp = f.split(os.sep)[-4]
        m = json.load(open(f))
        n = int(re.search(r"n(\d+)_s", f).group(1))
        rows.append(dict(experiment=exp, scenario=os.path.basename(f)[9:-5], nodes=n,
                         n_failed_nodes=m.get("n_failed_nodes"), pct_failed_nodes=m.get("pct_failed_nodes"),
                         n_failed_links=m.get("n_failed_links"), pct_failed_links=m.get("pct_failed_links"),
                         flows_with_route_after=m.get("flows_with_alternative_route"),
                         flows_total=m.get("flows_total"),
                         components_after=m.get("components_after_failure", m.get("components_at_peak_flood")),
                         selection=m.get("selection")))
    if not rows:
        return []
    d = pd.DataFrame(rows)
    g = d.groupby(["experiment", "scenario", "nodes", "selection"], dropna=False).agg(
        seeds=("n_failed_nodes", "size"), failed_nodes_mean=("n_failed_nodes", "mean"),
        failed_nodes_pct_mean=("pct_failed_nodes", "mean"), failed_links_mean=("n_failed_links", "mean"),
        failed_links_pct_mean=("pct_failed_links", "mean"), flows_with_route_mean=("flows_with_route_after", "mean"),
        flows_total=("flows_total", "max"), components_after_mean=("components_after", "mean")).reset_index()
    g.to_csv(os.path.join(TAB, "scenario_properties.csv"), index=False)
    return [f"scenario properties: {len(d)} scenario files"]


def failed_runs():
    rows = []
    for f in glob.glob(os.path.join(RES, "*", "failed_runs.csv")):
        d = pd.read_csv(f)
        if len(d):
            d.insert(0, "experiment", os.path.basename(os.path.dirname(f)))
            rows.append(d)
    out = pd.concat(rows) if rows else pd.DataFrame(columns=["experiment", "run_id", "reason"])
    out.to_csv(os.path.join(TAB, "failed_runs_all.csv"), index=False)
    return [f"failed runs: {len(out)}"]


def md_table(df):
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if pd.isna(v) else (f"{v:.4g}" if isinstance(v, float) else str(v))
                                     for v in r.values) + " |")
    return "\n".join(out)


def findings_md():
    """A digest of means (± 95% CI) and significant paired differences. Numbers only, no interpretation."""
    parts = ["# Results digest", "",
             "Generated by `experiments/analyze.py` from `results/*/summary.csv`. Each cell is the mean over "
             "seeds ± the 95% confidence interval half-width. Paired tests: Wilcoxon signed-rank across seeds, "
             "Holm-corrected over the three protocol pairs; only differences with corrected p < 0.05 are listed. "
             "Definitions: `experiments/README.md`.", "",
             "If you want a blind check of your predictions, fill in `PREDICTIONS.md` before reading further.", ""]
    show = {"pdr_pct": "PDR %", "within_1s_pct": "≤1 s %", "delay_mean_ms": "delay ms",
            "delay_p95_ms": "p95 ms", "throughput_kbps": "kbps", "control_pkts_per_node_s": "ctrl/node/s",
            "nrl_ctrl_per_delivered": "NRL", "recovery_time_s": "recovery s",
            "restore_recovery_mean_s": "after restore s", "energy_mean_per_node_J": "J/node"}
    specs = [("main", ["scenario", "nodes"]), ("severity", ["scenario", "severity"]),
             ("load", ["scenario", "n_flows"]), ("energy", ["scenario"]), ("kerala", ["scenario", "severity"])]
    extra = {"energy": {"first_depletion_s": "1st death s", "depletion_50pct_s": "50% dead s",
                        "connected_pdr_pct": "connected PDR %"},
             "kerala": {"connected_pdr_pct": "connected PDR %", "acute_14_18aug_within_1s_pct": "acute ≤1 s %",
                        "sustained_18_27aug_within_1s_pct": "sustained ≤1 s %",
                        "acute_14_18aug_connected_within_1s_pct": "acute conn ≤1 s %",
                        "sustained_18_27aug_connected_within_1s_pct": "sustained conn ≤1 s %"}}
    for exp, keys in specs:
        df = load(exp)
        if df is None:
            continue
        cols = dict(show, **extra.get(exp, {}))
        if exp in ("energy", "kerala"):
            cols.pop("recovery_time_s", None)
            cols.pop("restore_recovery_mean_s", None)
        agg = aggregate(df, keys + ["protocol"], list(cols))
        parts += [f"## {exp} ({len(df)} runs)", ""]
        rows = []
        for _, r in agg.iterrows():
            row = {k: r[k] for k in keys + ["protocol"]}
            row["runs"] = r["runs"]
            for m, lab in cols.items():
                if f"{m}_mean" in r and not pd.isna(r[f"{m}_mean"]):
                    ci = r[f"{m}_ci95"]
                    row[lab] = f"{r[f'{m}_mean']:.3g}" + ("" if pd.isna(ci) else f" ± {ci:.2g}")
                else:
                    row[lab] = ""
            rows.append(row)
        t = pd.DataFrame(rows)
        order = {p: i for i, p in enumerate(PROTOCOLS)}
        t = t.sort_values(keys + ["protocol"], key=lambda c: c.map(order) if c.name == "protocol" else c)
        parts += [md_table(t), ""]
        tests = paired_tests(df, keys, list(cols))
        sig = []
        for _, r in tests.iterrows():
            for a, b in [("aodv", "olsr"), ("aodv", "dsdv"), ("olsr", "dsdv")]:
                hp = r.get(f"holm_p_{a}_{b}")
                if hp is not None and not pd.isna(hp) and hp < 0.05:
                    sig.append({**{k: r[k] for k in keys}, "metric": cols.get(r["metric"], r["metric"]),
                                "pair": f"{a.upper()} − {b.upper()}",
                                "median paired difference": f"{r[f'median_diff_{a}_minus_{b}']:.3g}",
                                "Holm p": f"{hp:.3g}", "seeds": r["n_seeds"]})
        if sig:
            parts += ["Significant paired differences:", "", md_table(pd.DataFrame(sig)), ""]
    with open(os.path.join(OUT, "FINDINGS.md"), "w") as f:
        f.write("\n".join(parts) + "\n")
    return ["findings digest written"]


def combined_summary_table():
    frames = []
    for exp in ("main", "severity", "load", "energy", "kerala"):
        df = load(exp)
        if df is not None:
            t = table_deliverable(df)
            t.insert(0, "Experiment", exp)
            frames.append(t)
    if frames:
        pd.concat(frames).to_csv(os.path.join(TAB, "summary_table_all_runs.csv"), index=False)
        return [f"combined summary table: {sum(len(f) for f in frames)} runs"]
    return []


def main():
    ensure_dirs()
    notes = []
    for step in (main_grid, severity, load_sweep, energy, kerala, energy_validation, flowmon_crosscheck,
                 scenario_properties, failed_runs, combined_summary_table, findings_md):
        try:
            notes += step()
        except Exception as e:  # keep going so one broken step doesn't hide the rest
            notes.append(f"{step.__name__} FAILED: {type(e).__name__}: {e}")
    with open(os.path.join(OUT, "analysis_log.txt"), "w") as f:
        f.write("\n".join(notes) + "\n")
    print("\n".join(notes))


if __name__ == "__main__":
    main()
