# Status of the overnight experiment run

Updated on every push. The full list of requested outputs is in `docs/deliverables.md`; the table at the bottom says where each item is answered.

| Step | State |
|---|---|
| Save deliverables list | done |
| Build simulator for all scenarios (`sim/manet`) | done |
| Main grid: 3 protocols × 6 scenarios × 25/50/100 nodes × 10 seeds (540 runs) | done, committed |
| Failure-severity sweep (240 runs) | done, committed |
| Traffic-load sweep (180 runs) | done, committed |
| Energy and network lifetime (60 runs) | done, committed |
| Kerala time-evolving failure model + baselines, 50 nodes (150 runs) | done, committed |
| Kerala, 100 nodes (150 runs) | done, committed (extra) |
| RTS/CTS sensitivity check, 100-node baseline (30 runs) | running (extra; added because AODV degrades sharply at 100 nodes) |
| Analysis: tables, figures, statistics | done for everything above; regenerated once the sensitivity check finishes |
| Methods README (`experiments/README.md`) | done |

All finished runs completed without failures in their final pass. Four 100-node runs failed in earlier attempts and were redone (`results/main/failed_runs_history.csv`).

## Where to start reading

1. `results/analysis/FINDINGS.md` has the numbers (means ± 95% CI and significant paired differences). Fill in `PREDICTIONS.md` first if you want a blind check.
2. `results/analysis/figures/` has every figure as PNG and PDF.
3. `experiments/README.md` covers how everything was set up, the metric definitions, the checks, and the limitations you need to state in the paper.

## Found along the way

- AODV's link-break detection was silently disabled by `NeighborCacheHelper` in both sims. Fixed; see `docs/ns3-defaults.md`. Re-run any diamond AODV results made before 27 Oct.
- NS-3's `WifiRadioEnergyModel` stops counting a radio that is switched back on after being switched off. The experiments use their own state-based energy accounting, checked against NS-3's model.
- ns-3.47 crashes if a radio is switched off in the middle of a broadcast. Failing radios now finish their current frame first (see `docs/ns3-defaults.md`).
- NS-3's energy framework used gigabytes of memory per 100-node run; it now runs only at 25 and 50 nodes (as a cross-check).
- DSDV needs more than the 60 s warm-up to build complete tables in some sparse 25-node topologies. Listed in `results/analysis/tables/check_initial_convergence.csv`.

## Where each deliverable is answered

| Deliverable (`docs/deliverables.md`) | Where |
|---|---|
| §1 Simulation configuration | `experiments/README.md` §1; every run's `run_config.json` and `command.txt` |
| §2 Scenarios: baseline, link, node, multiple, partition, recovery | `experiments/README.md` §2; `results/<exp>/inputs/*/scenario_*.json` |
| §2 Failure times, affected nodes/links and locations, % affected, alternative route, deterministic or random | `scenario_*.json` (per run); `results/analysis/tables/scenario_properties.csv` (averages) |
| §2 Assumptions linking scenarios to disasters | `experiments/README.md` §2 and §5; `assumption` field in each `scenario_*.json` |
| §3 PDR, delay (mean, median, std, p95), throughput, routing overhead (packets, bytes, ratios), loss and reasons, recovery time | `results/<exp>/summary.csv`; definitions in `experiments/README.md` §3 |
| §4 Route discovery time and count, route errors (AODV) | `route_discovery_*`, `route_errors_rerr_tx` columns; `discoveries.csv.gz` per run |
| §4 Routing-table convergence (OLSR, DSDV) | `convergence_*`, `initial_convergence_s`, `route_validity_mean_pct`; `routes.csv.gz` per run |
| §4 Broken routes, delivery during recovery, time without delivery | `mac_link_break_detections`, `recovery_window_*`, `recovery_outage_mean_s`; `per_flow.csv` (`longest_delivery_gap_s`) |
| §4 Control traffic before / during / after failure | `pre_`, `during_`, `post_ctrl_pkts_per_node_s`; figures `control_over_time_*` |
| §4 Energy per node, network lifetime | `energy_*`, `first_depletion_s`, `depletion_10pct_s`, `depletion_50pct_s`; `energy.csv` per run; energy experiment |
| §5 Node counts 25/50/100, severities, traffic loads, seeds, mean and std, repetitions, failed runs | `main`, `severity`, `load` experiments; `results/analysis/tables/*_by_config.csv` (runs, mean, std, 95% CI); `failed_runs_all.csv` |
| §6 Source code, commands, logs, FlowMonitor XML, routing/topology traces, failure-event logs, per-run CSVs, README | `sim/manet/manet.cc`, `experiments/`; per-run `command.txt`, `stdout.log`, `stderr.log`, `flowmon.xml.gz` (seed 1), `rtables-*.txt.gz` (seed 1), `routes.csv.gz`, `topology.csv`, `events.csv`, `packets.csv.gz`; `results/README.md`. No pcap (too large; see `results/README.md`) |
| §7 Summary table, one row per run | `results/analysis/tables/summary_table_all_runs.csv` |
| §8 Comparisons, density, severity, error bars, statistical tests | `results/analysis/figures/`, `*_stats_tests.csv`, `results/analysis/FINDINGS.md` |
| §8 Discussion of trade-offs and limitations | Limitations listed in `experiments/README.md` §7. The discussion itself is yours to write |
| §8 Reproducibility, deviations | `experiments/README.md` (Reproducing, §6 Checks, §7 Deviations) |
| §9 Minimum and stronger dataset | Both covered: 3 protocols, 6 scenarios, 3 sizes, 4 severities, 3 loads, 10 seeds, raw files |
