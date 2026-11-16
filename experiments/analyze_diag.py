"""Diagnosis of AODV's losses in the 100-node baseline (see PREDICTIONS.md, Diagnosis 1 and 2).

Compares the main experiment's 100-node baseline with two diagnostic grids:
    diag_nofeedback100   AODV ignores the MAC's retry-limit reports (same topologies and flows)
    diag_sparse100       the same 100 devices in a 1,000 m square (AODV and OLSR)

    python3 experiments/analyze_diag.py

Writes results/analysis/tables/diag100_by_config.csv, diag100_per_seed.csv and diag100_tests.csv.
"""
import os

import pandas as pd
from scipy import stats

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "results", "analysis", "tables")
METRICS = ["pdr_pct", "within_1s_pct", "delay_median_ms", "mean_hops", "control_pkts_per_node_s",
           "mac_link_break_detections", "route_discoveries", "ctrl_aodv_rreq_forwarded", "ctrl_aodv_rerr",
           "energy_mean_per_node_J", "radio_tx_time_mean_s", "radio_rx_time_mean_s", "packets_lost"]
LOST = ["lost_mac_retry_limit", "lost_ip_no_route", "lost_mac_lifetime_expired", "lost_ip_route_error",
        "lost_mac_queue_full", "lost_ip_ttl_expired", "lost_no_route_at_source", "lost_no_drop_event"]


def load(exp, label):
    s = pd.read_csv(os.path.join(REPO, "results", exp, "summary.csv"))
    s = s[(s.scenario == "baseline") & (s.nodes == 100) & (s.n_flows == 10) & s.protocol.isin(["aodv", "olsr"])].copy()
    s["config"] = label
    return s


def main():
    d = pd.concat([load("main", "main (500 m square)"),
                   load("diag_nofeedback100", "AODV ignores MAC reports (500 m)"),
                   load("diag_sparse100", "1,000 m square")])
    cols = [c for c in METRICS + LOST if c in d.columns]
    d[["config", "protocol", "seed"] + cols].sort_values(["config", "protocol", "seed"]).to_csv(
        os.path.join(OUT, "diag100_per_seed.csv"), index=False)
    g = d.groupby(["config", "protocol"])
    by = g[cols].mean()
    by.insert(0, "runs", g.size())
    for c in ("pdr_pct", "within_1s_pct"):
        sem = g[c].sem()
        by[c + "_ci95"] = sem * stats.t.ppf(0.975, g.size() - 1)
    for c in LOST:
        if c in by:
            by[c.replace("lost_", "lostshare_") + "_pct"] = 100 * by[c] / by["packets_lost"].where(by["packets_lost"] > 0)
    by.round(4).to_csv(os.path.join(OUT, "diag100_by_config.csv"))

    def paired(a, b, metric):
        x = a.set_index("seed")[metric]
        y = b.set_index("seed")[metric]
        seeds = x.index.intersection(y.index)
        diff = (y[seeds] - x[seeds])
        p = stats.wilcoxon(diff).pvalue if (diff != 0).any() else 1.0
        return dict(n=len(seeds), median_diff=diff.median(), min_diff=diff.min(), max_diff=diff.max(), wilcoxon_p=p)

    sel = lambda cfg, pr: d[(d.config == cfg) & (d.protocol == pr)]
    rows = []
    for metric in ("pdr_pct", "within_1s_pct"):
        rows.append(dict(comparison="AODV: ignores MAC reports minus main (same topologies)", metric=metric,
                         **paired(sel("main (500 m square)", "aodv"), sel("AODV ignores MAC reports (500 m)", "aodv"), metric)))
        rows.append(dict(comparison="AODV ignoring MAC reports minus OLSR main (same topologies)", metric=metric,
                         **paired(sel("main (500 m square)", "olsr"), sel("AODV ignores MAC reports (500 m)", "aodv"), metric)))
        rows.append(dict(comparison="1,000 m square: AODV minus OLSR (same topologies)", metric=metric,
                         **paired(sel("1,000 m square", "olsr"), sel("1,000 m square", "aodv"), metric)))
        for pr in ("aodv", "olsr"):   # different topologies: unpaired
            a, b = sel("main (500 m square)", pr)[metric], sel("1,000 m square", pr)[metric]
            rows.append(dict(comparison=f"{pr.upper()}: 1,000 m minus 500 m (different topologies, Mann-Whitney)", metric=metric,
                             n=len(b), median_diff=b.median() - a.median(), min_diff=float("nan"), max_diff=float("nan"),
                             wilcoxon_p=stats.mannwhitneyu(a, b).pvalue))
    pd.DataFrame(rows).round(4).to_csv(os.path.join(OUT, "diag100_tests.csv"), index=False)
    pd.set_option("display.width", 250, "display.max_columns", 60, "display.max_rows", 200)
    print(by.round(2).T)
    print(pd.DataFrame(rows).round(4).to_string())


if __name__ == "__main__":
    main()
