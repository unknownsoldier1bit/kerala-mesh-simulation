"""Compact tables for the paper, from the analysis outputs.

Writes docs/paper/tables/*.csv: one row per configuration, one column per protocol, each cell
"mean ± 95% CI" over seeds 1-10 (and a numeric twin, *_numeric.csv, for spreadsheets). Also writes
docs/paper/tests.csv with the paired protocol tests behind every table (Holm-corrected p values).

    python3 experiments/paper_tables.py
"""

import json
import os

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAB = os.path.join(REPO, "results", "analysis", "tables")
CTAB = os.path.join(REPO, "results", "analysis_chalakudy", "tables")
OUT = os.path.join(REPO, "docs", "paper", "tables")
PROTOS = ["aodv", "olsr", "dsdv"]
LABEL = {"aodv": "AODV", "olsr": "OLSR", "dsdv": "DSDV"}


def cell(mean, ci, digits=1):
    if pd.isna(mean):
        return "-"
    return f"{mean:.{digits}f} ± {ci:.{digits}f}" if not pd.isna(ci) else f"{mean:.{digits}f}"


def wide(df, keys, metric, digits=1, labels=None):
    """One row per configuration (keys), one column per protocol."""
    rows, nums = [], []
    for k, g in df.groupby(keys, sort=False, dropna=False):
        k = k if isinstance(k, tuple) else (k,)
        row = dict(zip(labels or keys, k))
        num = dict(row)
        for p in PROTOS:
            r = g[g.protocol == p]
            m = r[f"{metric}_mean"].iloc[0] if len(r) else np.nan
            c = r[f"{metric}_ci95"].iloc[0] if len(r) else np.nan
            row[LABEL[p]] = cell(m, c, digits)
            num[f"{LABEL[p]} mean"], num[f"{LABEL[p]} ci95"] = m, c
        rows.append(row)
        nums.append(num)
    return pd.DataFrame(rows), pd.DataFrame(nums)


def save(name, pair):
    text, num = pair
    text.to_csv(os.path.join(OUT, f"{name}.csv"), index=False)
    num.to_csv(os.path.join(OUT, f"{name}_numeric.csv"), index=False)
    return text


SCEN = {"baseline": "Baseline", "link_fail": "Link failure", "node_fail": "Node failure",
        "multi_fail": "Multiple failures", "partition": "Partition", "recovery": "Recovery"}


def main():
    os.makedirs(OUT, exist_ok=True)

    m = pd.read_csv(os.path.join(TAB, "main_by_config.csv"))
    m["scenario"] = pd.Categorical(m.scenario.map(SCEN), list(SCEN.values()), ordered=True)
    m = m.sort_values(["scenario", "nodes"])
    save("main_within_1s", wide(m, ["scenario", "nodes"], "within_1s_pct", labels=["Scenario", "Nodes"]))
    base = m[m.scenario == "Baseline"]
    for met, name, dg in (("pdr_pct", "main_baseline_pdr", 1), ("delay_median_ms", "main_baseline_delay_median", 1),
                          ("control_pkts_per_node_s", "main_baseline_control", 2)):
        save(name, wide(base, ["nodes"], met, dg, labels=["Nodes"]))

    s = pd.read_csv(os.path.join(TAB, "severity_by_config.csv"))
    s["scenario"] = s.scenario.map({"random_nodes": "Random relay nodes", "random_links": "Random links"})
    s["severity"] = (100 * s.severity).round().astype(int).astype(str) + "%"
    save("severity_within_1s", wide(s, ["scenario", "severity"], "within_1s_pct", labels=["Failures", "Share failed"]))

    lo = pd.read_csv(os.path.join(TAB, "load_by_config.csv"))
    lo["scenario"] = lo.scenario.map(SCEN)
    save("load_within_1s", wide(lo, ["scenario", "n_flows"], "within_1s_pct", labels=["Scenario", "Flows"]))

    e = pd.read_csv(os.path.join(TAB, "energy_by_config.csv"))
    e["scenario"] = e.scenario.map({"default_radio": "ns-3 default radio", "low_idle_radio": "Low-idle radio"})
    rows = []
    for (sc, p), g in e.groupby(["scenario", "protocol"], sort=False):
        r = g.iloc[0]
        rows.append({"Radio profile": sc, "Protocol": LABEL[p],
                     "First node flat (s)": cell(r.first_depletion_s_mean, r.first_depletion_s_ci95),
                     "Half of nodes flat (s)": cell(r.depletion_50pct_s_mean, r.depletion_50pct_s_ci95),
                     "Control pkts/node/s": cell(r.control_pkts_per_node_s_mean, r.control_pkts_per_node_s_ci95, 2),
                     "Within 1 s (%)": cell(r.within_1s_pct_mean, r.within_1s_pct_ci95)})
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "energy.csv"), index=False)

    k = pd.read_csv(os.path.join(TAB, "kerala_by_config.csv"))
    order = ["control", "kerala_27", "uniform_27", "kerala_50", "uniform_50"]
    kl = {"control": "No flooding", "kerala_27": "Kerala-anchored 27%", "uniform_27": "Random 27%",
          "kerala_50": "Kerala-anchored 50%", "uniform_50": "Random 50%"}
    k["model"] = pd.Categorical(k.model, order, ordered=True)
    k = k.sort_values(["nodes", "model"])
    k["model"] = k.model.map(kl)
    for ph, col in (("acute", "acute_14_18aug_within_1s_pct"), ("sustained", "sustained_18_27aug_within_1s_pct"),
                    ("acute_connected", "acute_14_18aug_connected_within_1s_pct"),
                    ("sustained_connected", "sustained_18_27aug_connected_within_1s_pct")):
        save(f"kerala_{ph}_within_1s", wide(k, ["nodes", "model"], col, labels=["Nodes", "Scenario"]))

    c = pd.read_csv(os.path.join(CTAB, "chalakudy_by_config.csv"))
    ml = {"control": "No flooding", "flood": "Flood (lowest ground first)", "uniform": "Uniform random"}
    main_c = c[(c.experiment == "chalakudy") & (c.battery == "nobatt") & (c.onset == 15)].copy()
    main_c["model"] = pd.Categorical(main_c.model.map(ml), list(ml.values()), ordered=True)
    main_c = main_c.sort_values("model")
    rows, nums = [], []
    for w, wl in (("before_onset", "14-15 Aug (before onset)"), ("acute", "15-18 Aug (acute)"),
                  ("sustained", "18-27 Aug (sustained)")):
        for met, lab in (("within_1s_pct", "all sent"), ("connected_within_1s_pct", "path existed")):
            if w == "before_onset" and met.startswith("connected"):
                continue
            t, n = wide(main_c, ["model"], f"{w}_{met}", labels=["Scenario"])
            t.insert(1, "Window", f"{wl}, {lab}")
            n.insert(1, "Window", f"{wl}, {lab}")
            rows.append(t)
            nums.append(n)
    t = pd.concat(rows, ignore_index=True)
    t.to_csv(os.path.join(OUT, "chalakudy_main_within_1s.csv"), index=False)
    pd.concat(nums, ignore_index=True).to_csv(os.path.join(OUT, "chalakudy_main_within_1s_numeric.csv"), index=False)

    sweep = []
    for exp, col, lab in (("chalakudy_share", "share", "Flooded share (%)"), ("chalakudy_traffic", "gap",
                                                                               "Mean gap between bursts (s)")):
        d = pd.concat([c[(c.experiment == "chalakudy") & (c.battery == "nobatt") & (c.onset == 15)
                         & (c.model != "control")], c[(c.experiment == exp) & (c.model != "control")]])
        d = d[(d.share == 25) | (exp == "chalakudy_share")] if exp == "chalakudy_traffic" else d[d.gap == 15]
        d = d.copy().assign(Parameter=lab, Value=d[col].map(lambda v: f"{v:g}"), model=d.model.map(ml))
        d = d.sort_values(["model", col])
        tt, _ = wide(d, ["Parameter", "Value", "model"], "acute_within_1s_pct", labels=["Parameter", "Value", "Scenario"])
        sweep.append(tt)
    pd.concat(sweep, ignore_index=True).to_csv(os.path.join(OUT, "chalakudy_sweeps_acute_within_1s.csv"), index=False)

    tests = []
    for f in ("main_stats_tests", "severity_stats_tests", "load_stats_tests", "energy_stats_tests",
              "kerala_stats_tests"):
        d = pd.read_csv(os.path.join(TAB, f + ".csv"))
        d.insert(0, "table", f)
        tests.append(d)
    d = pd.read_csv(os.path.join(CTAB, "chalakudy_protocol_tests.csv"))
    d.insert(0, "table", "chalakudy_protocol_tests")
    tests.append(d)
    pd.concat(tests, ignore_index=True).to_csv(os.path.join(REPO, "docs", "paper", "tests.csv"), index=False)
    print("wrote", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
