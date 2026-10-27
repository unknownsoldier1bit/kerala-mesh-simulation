"""Runs one experiment grid: generates inputs, runs NS-3 in parallel, computes metrics.

Usage, from the repo root:
    python3 experiments/run_experiment.py main          # or severity, load, energy, kerala
    python3 experiments/run_experiment.py main --dry    # list the runs without running them

Runs that already finished are skipped, so an interrupted experiment can be resumed
by running the same command again. Outputs go to results/<experiment>/:
    inputs/                  topology, traffic and failure files (+ scenario metadata)
    runs/<run_id>/           raw outputs of each run (see sim/manet/manet.cc)
    summary.csv              one row per run (all metrics)
    per_flow.csv             one row per flow per run
    recovery.csv             one row per (failure event, affected flow) per run
    failed_runs.csv          runs that crashed or timed out, with the reason
    commands.txt             the exact command of every run
"""

import argparse
import gzip
import json
import multiprocessing as mp
import os
import shutil
import subprocess
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen  # noqa: E402
import kerala  # noqa: E402
import metrics  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTOCOLS = ["aodv", "olsr", "dsdv"]
SEEDS = list(range(1, 11))
NS3_VERSION = "3.47"


def ns3_dir():
    d = os.environ.get("NS3_DIR")
    if not d:
        with open(os.path.join(REPO, ".ns3-path")) as f:
            d = f.read().strip()
    return d


def binary():
    return os.path.join(ns3_dir(), "build", "scratch", "manet", f"ns{NS3_VERSION}-manet-optimized")


# ---------------------------------------------------------------------------
# Experiment grids
# ---------------------------------------------------------------------------


def grid(name):
    """Returns a list of run configs for experiment `name`."""
    if name == "main":
        return standard_runs(
            name,
            scenarios=["baseline", "link_fail", "node_fail", "multi_fail", "partition", "recovery"],
            nodes=[25, 50, 100],
            flows=[10],
            severities=[None],
        )
    if name == "severity":
        return standard_runs(
            name, scenarios=["random_nodes", "random_links"], nodes=[50], flows=[10],
            severities=[0.05, 0.10, 0.20, 0.30],
        )
    if name == "load":
        return standard_runs(name, scenarios=["baseline", "node_fail"], nodes=[50], flows=[5, 10, 20], severities=[None])
    if name == "energy":
        return kerala.energy_runs(name, PROTOCOLS, SEEDS)
    if name == "kerala":
        return kerala.kerala_runs(name, PROTOCOLS, SEEDS)
    if name == "kerala100":  # same as kerala, with 100 nodes
        return kerala.kerala_runs(name, PROTOCOLS, SEEDS, nodes=(100,))
    raise SystemExit(f"unknown experiment {name}")


def severity_label(scenario, meta):
    if scenario == "baseline":
        return "none"
    parts = []
    if meta["n_failed_nodes"]:
        parts.append(f"{meta['n_failed_nodes']} nodes ({meta['pct_failed_nodes']}%)")
    if meta["n_failed_links"]:
        parts.append(f"{meta['n_failed_links']} links ({meta['pct_failed_links']}%)")
    return " + ".join(parts)


def standard_runs(exp, scenarios, nodes, flows, severities):
    runs = []
    for n in nodes:
        for seed in SEEDS:
            xy, g, draws = gen.make_topology(n, seed)
            idir = os.path.join("results", exp, "inputs", f"n{n}_s{seed}")
            os.makedirs(os.path.join(REPO, idir), exist_ok=True)
            topo = os.path.join(idir, "topology.csv")
            gen.write_topology(os.path.join(REPO, topo), xy)
            gen.write_json(
                os.path.join(REPO, idir, "topology_info.json"),
                {"nodes": n, "seed": seed, "area_m": gen.AREA_M, "range_m": gen.RANGE_M,
                 "links": g.number_of_edges(), "mean_degree": 2 * g.number_of_edges() / n,
                 "placement_draws_until_connected": draws, "diameter_hops": nx_diameter(g)},
            )
            for nf in flows:
                fl = gen.make_flows(g, nf, seed)
                ffile = os.path.join(idir, f"flows_f{nf}.csv")
                gen.write_flows(os.path.join(REPO, ffile), fl)
                for sc in scenarios:
                    for sev in severities:
                        tag = sc if sev is None else f"{sc}_{sev:g}"
                        events, meta = gen.scenario_events(sc, xy, g, fl, seed, sev)
                        efile = os.path.join(idir, f"events_{tag}_f{nf}.csv")
                        gen.write_events(os.path.join(REPO, efile), events)
                        gen.write_json(os.path.join(REPO, idir, f"scenario_{tag}_f{nf}.json"), meta)
                        flows_meta = [dict(f, alternative_route_exists=st["alternative_route_exists"])
                                      for f, st in zip(fl, meta["per_flow"])]
                        for p in PROTOCOLS:
                            run_id = f"{p}_{tag}_n{n}_f{nf}_s{seed}"
                            runs.append(dict(
                                experiment=exp, run_id=run_id, protocol=p, scenario=sc, nodes=n, seed=seed,
                                rng_run=seed, n_flows=nf, severity=sev, severity_label=severity_label(sc, meta),
                                topo=topo, flows_file=ffile, events_file=efile,
                                fail_time_s=meta["failure_start_s"], restore_time_s=meta["failure_end_s"],
                                traffic_start_s=gen.TRAFFIC_START_S, traffic_stop_s=gen.TRAFFIC_STOP_S,
                                sim_time_s=gen.SIM_TIME_S, payload_bytes=gen.PAYLOAD_B, range_m=gen.RANGE_M,
                                energy_j=0, deadline_s=1.0,
                                # seed 1 of the main grid also runs the ns-3 energy framework, to check
                                # the fast state-based energy numbers against it. Not at 100 nodes: the
                                # framework's memory grows by gigabytes there (see experiments/README.md).
                                energy_model=("ns3" if seed == 1 and exp == "main" and n <= 50 else "states"),
                                flowmon=(seed == 1 and exp == "main"),
                                rt_dump=("119,140" if seed == 1 and exp == "main" else ""),
                                flows=flows_meta,
                            ))
    return runs


def nx_diameter(g):
    import networkx as nx

    return nx.diameter(g)


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------


def command(cfg, out_dir):
    args = [
        f"--protocol={cfg['protocol']}",
        f"--topo={cfg['topo']}",
        f"--flows={cfg['flows_file']}",
        f"--outDir={out_dir}",
        f"--run={cfg['rng_run']}",
        f"--simTime={cfg['sim_time_s']}",
        f"--range={cfg['range_m']}",
        f"--energyJ={cfg['energy_j']}",
    ]
    if cfg.get("events_file"):
        args.append(f"--events={cfg['events_file']}")
    if cfg.get("energy_model", "states") != "states":
        args.append(f"--energyModel={cfg['energy_model']}")
    if cfg.get("idle_current_a") is not None:
        args.append(f"--idleCurrentA={cfg['idle_current_a']}")
    if cfg.get("energy_file"):
        args.append(f"--energyFile={cfg['energy_file']}")
    if cfg.get("flowmon"):
        args.append("--flowmon=true")
    if cfg.get("rt_dump"):
        args.append(f"--rtDump={cfg['rt_dump']}")
    return args


def gzip_file(path):
    with open(path, "rb") as src, gzip.open(path + ".gz", "wb", compresslevel=6) as dst:
        shutil.copyfileobj(src, dst)
    os.remove(path)


def run_one(cfg):
    out_dir = os.path.join("results", cfg["experiment"], "runs", cfg["run_id"])
    abs_out = os.path.join(REPO, out_dir)
    done_file = os.path.join(abs_out, "summary.json")
    if os.path.exists(done_file):
        with open(done_file) as f:
            return cfg["run_id"], "skipped", json.load(f), None
    if os.path.exists(abs_out):
        shutil.rmtree(abs_out)
    os.makedirs(abs_out)
    args = command(cfg, out_dir)
    with open(os.path.join(abs_out, "command.txt"), "w") as f:
        f.write("ns3.47-manet " + " ".join(args) + "\n")
    with open(os.path.join(abs_out, "run_config.json"), "w") as f:
        json.dump(cfg, f, indent=1)
    t = time.time()
    try:
        with open(os.path.join(abs_out, "stdout.log"), "w") as so, open(os.path.join(abs_out, "stderr.log"), "w") as se:
            proc = subprocess.run([binary()] + args, cwd=REPO, stdout=so, stderr=se, timeout=3 * 3600)
        if proc.returncode != 0:
            return cfg["run_id"], "failed", None, f"exit code {proc.returncode} (see stderr.log)"
        summary, per_flow, rec, ts = metrics.compute(abs_out, cfg)
    except subprocess.TimeoutExpired:
        return cfg["run_id"], "failed", None, "timed out after 3 h"
    except Exception as e:  # metrics errors are recorded, not fatal for the whole grid
        return cfg["run_id"], "failed", None, f"{type(e).__name__}: {e}"
    per_flow.to_csv(os.path.join(abs_out, "per_flow.csv"), index=False)
    rec.to_csv(os.path.join(abs_out, "recovery.csv"), index=False)
    if ts is not None:
        ts.to_csv(os.path.join(abs_out, "timeseries.csv"), index=False)
    for name in ("packets.csv", "control.csv", "routes.csv", "discoveries.csv", "flowmon.xml"):
        p = os.path.join(abs_out, name)
        if os.path.exists(p):
            gzip_file(p)
    for name in os.listdir(abs_out):
        if name.startswith("rtables-") and name.endswith(".txt"):
            gzip_file(os.path.join(abs_out, name))
    summary["run_seconds"] = round(time.time() - t, 2)
    with open(done_file, "w") as f:
        json.dump(summary, f, indent=1, default=float)
    return cfg["run_id"], "ok", summary, None


def recompute_one(cfg):
    """Recomputes the metrics of a finished run from its raw files (after a metrics change)."""
    abs_out = os.path.join(REPO, "results", cfg["experiment"], "runs", cfg["run_id"])
    done_file = os.path.join(abs_out, "summary.json")
    if not os.path.exists(done_file):
        return cfg["run_id"], "missing"
    with open(done_file) as f:
        old = json.load(f)
    try:
        summary, per_flow, rec, ts = metrics.compute(abs_out, cfg)
    except Exception as e:
        return cfg["run_id"], f"failed: {type(e).__name__}: {e}"
    summary["run_seconds"] = old.get("run_seconds")
    per_flow.to_csv(os.path.join(abs_out, "per_flow.csv"), index=False)
    rec.to_csv(os.path.join(abs_out, "recovery.csv"), index=False)
    if ts is not None:
        ts.to_csv(os.path.join(abs_out, "timeseries.csv"), index=False)
    with open(done_file, "w") as f:
        json.dump(summary, f, indent=1, default=float)
    return cfg["run_id"], "ok"


def collect(exp, runs):
    """Rebuilds the experiment-level CSVs from every finished run."""
    base = os.path.join(REPO, "results", exp)
    rows, flows, recs, tss = [], [], [], []
    for cfg in runs:
        d = os.path.join(base, "runs", cfg["run_id"])
        sj = os.path.join(d, "summary.json")
        if not os.path.exists(sj):
            continue
        with open(sj) as f:
            rows.append(json.load(f))
        for name, acc in (("per_flow.csv", flows), ("recovery.csv", recs), ("timeseries.csv", tss)):
            p = os.path.join(d, name)
            if os.path.exists(p) and os.path.getsize(p) > 1:
                try:
                    acc.append(pd.read_csv(p))
                except pd.errors.EmptyDataError:
                    pass
    if rows:
        pd.DataFrame(rows).to_csv(os.path.join(base, "summary.csv"), index=False)
    if flows:
        pd.concat(flows).to_csv(os.path.join(base, "per_flow.csv"), index=False)
    if recs:
        pd.concat(recs).to_csv(os.path.join(base, "recovery.csv"), index=False)
    if tss:
        pd.concat(tss).to_csv(os.path.join(base, "timeseries.csv"), index=False)
    with open(os.path.join(base, "commands.txt"), "w") as f:
        f.write("# Run from the repo root. ns3.47-manet = <NS-3 dir>/build/scratch/manet/ns3.47-manet-optimized\n")
        f.write("# (equivalently: ./ns3 run \"manet <args>\" from the NS-3 dir, with absolute paths)\n")
        for cfg in runs:
            out_dir = os.path.join("results", exp, "runs", cfg["run_id"])
            f.write("ns3.47-manet " + " ".join(command(cfg, out_dir)) + "\n")
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("experiment")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--only", default="", help="substring filter on run_id (for testing)")
    ap.add_argument("--recompute", action="store_true", help="recompute metrics of finished runs only")
    a = ap.parse_args()
    os.chdir(REPO)
    runs = grid(a.experiment)
    if a.only:
        runs = [r for r in runs if a.only in r["run_id"]]
    print(f"{a.experiment}: {len(runs)} runs", flush=True)
    if a.dry:
        for r in runs[:20]:
            print(r["run_id"])
        return
    if a.recompute:
        with mp.Pool(a.jobs) as pool:
            res = pool.map(recompute_one, runs)
        bad = [r for r in res if r[1] != "ok"]
        print(f"recomputed {len(res) - len(bad)} runs; not recomputed: {bad[:10]}", flush=True)
        collect(a.experiment, runs)
        return
    base = os.path.join(REPO, "results", a.experiment)
    failed_path = os.path.join(base, "failed_runs.csv")
    failed = []
    t0 = time.time()
    done = 0
    with mp.Pool(a.jobs) as pool:
        for run_id, status, _, err in pool.imap_unordered(run_one, runs):
            done += 1
            if status == "failed":
                failed.append({"run_id": run_id, "reason": err})
                print(f"FAILED {run_id}: {err}", flush=True)
            if done % 25 == 0 or done == len(runs):
                print(f"{done}/{len(runs)} runs, {time.time() - t0:.0f} s elapsed", flush=True)
                collect(a.experiment, runs)
    pd.DataFrame(failed, columns=["run_id", "reason"]).to_csv(failed_path, index=False)
    n = collect(a.experiment, runs)
    print(f"done: {n} runs summarised, {len(failed)} failed", flush=True)


if __name__ == "__main__":
    main()
