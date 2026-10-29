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
| RTS/CTS sensitivity check, 100-node baseline (30 runs) | done, committed (extra: checks whether hidden-terminal collisions explain the 100-node AODV results) |
| Analysis: tables, figures, statistics | done for all 1,350 runs (`results/analysis/`); regenerated 29 Oct, reproduces byte for byte |
| Methods README (`experiments/README.md`) | done |

| **Chalakudy experiment (29 Oct, branch `chalakudy-buildings`)**: real building positions, real-data flood order | see below |
|---|---|
| Data: buildings, boundary, elevation, rivers, 24 Sentinel-1 images; provenance of every number | done (`data/chalakudy/PROVENANCE.md`); some sources blocked here (`data/chalakudy/MANUAL_DOWNLOADS.md`) |
| `chalakudy` (360), `chalakudy_prop` (90), `chalakudy_share` (120), `chalakudy_battery` (180), cross-checks (36) | done, committed; metrics recomputed with the 29 Oct corrections |
| `chalakudy_traffic` (180) | done, committed; metrics recomputed with the 29 Oct corrections |
| `chalakudy_nodes` (50/150 devices, 180) | not run (owner's compute decision); covered at graph level by `network_structure.csv` |
| Chalakudy analysis (`results/analysis_chalakudy/`) | done for all 930 runs; reproduces byte for byte on a second run |

All finished runs completed without failures in their final pass. Four 100-node runs failed in earlier attempts and were redone (`results/main/failed_runs_history.csv`).

## Where to start reading

1. `results/analysis/FINDINGS.md` has the numbers (means ± 95% CI and significant paired differences). Fill in `PREDICTIONS.md` first if you want a blind check.
2. `results/analysis/figures/` has every figure as PNG and PDF.
3. `experiments/README.md` covers how everything was set up, the metric definitions, the checks, and the limitations you need to state in the paper.

## Audit and corrections, 28 Oct 2026 (evening)

- All 1,350 runs present: 10 seeds per configuration, no duplicates, no failed runs, no errors in any `stderr.log`, every raw file listed in deliverables §6 present.
- Every run's metrics recomputed from raw files with the final `metrics.py`: identical to the committed summaries.
- Fixed `longest_delivery_gap_s` (deliverables §4, time without delivery): it now includes the time from a flow's last delivery to the end of traffic. Per-flow files regenerated.
- Fixed tie handling in the paired tests (deliverables §8): exact ties are no longer broken by floating-point noise. 24 Holm-corrected comparisons are no longer significant at 0.05. All tables, figures and `FINDINGS.md` regenerated, and the analysis now reproduces identically.
- `DELIVERABLES-HANDOFF.md` in the repo root maps every deliverables item to its files.

## Audit and corrections, 29 Oct 2026

All 2,316 runs (1,350 earlier + 930 Chalakudy + 36 cross-checks) were checked again, with an independent audit of the Chalakudy branch. Everything downstream was regenerated; both analyses reproduce byte for byte.

- **Fragmented routing packets.** Replaying all 450 committed OLSR runs of the earlier experiments with the fixed simulator found fragments in 29 runs at 100 nodes (none at 25 or 50). Their control-byte counts were short by at most 0.028%; everything else was identical. The 29 runs were redone.
- **Recovery (affected flows).** A flow's route before a failure was taken from the last packet *sent* before it, which can have arrived later over a new route; it is now the last packet *received* before it, as documented. 102 affected/unaffected decisions changed in 75 runs; recovery tables and tests regenerated.
- **AODV route-discovery times.** The simulator keeps a discovery open until an RREP reaches its originator, so discoveries AODV abandoned or resolved another way absorbed later ones (records up to 371 s). Records longer than AODV's own give-up time (11.32 s with margin) are now excluded from discovery times and counted in `route_discoveries_failed_then_retried`. Mean discovery times fall sharply (main grid: about 1.96 s to 0.14 s); medians barely change.
- **New metrics.** `delivered_of_scheduled_pct` and `within_1s_of_scheduled_pct` count messages that a failed or flat device never sent. In battery-limited Chalakudy runs only 6–26% of scheduled messages arrive, although PDR is 85–97%.
- **Reproducing on another machine.** 467 of 482 runs replayed on a Mac matched exactly; the 15 AODV runs at 100 nodes in the 500 m grid did not (different floating-point rounding, amplified by congestion), but their 10-seed averages agree (`experiments/README.md` §6).
- **Other.** The runner finds a default-profile build (or `MANET_BIN`) and checks for it before starting; main-analysis PDFs no longer embed the time of the run; limitations added to `experiments/README.md` §7 (time compression, building data dates, terrain-based flood order, radio coverage, many tests); `data/sources.md` notes which cited documents still need URLs.

## Found along the way

- AODV's link-break detection was silently disabled by `NeighborCacheHelper` in both sims. Fixed; see `docs/ns3-defaults.md`. Re-run any diamond AODV results made before 27 Oct.
- NS-3's `WifiRadioEnergyModel` stops counting a radio that is switched back on after being switched off. The experiments use their own state-based energy accounting, checked against NS-3's model.
- ns-3.47 crashes if a radio is switched off in the middle of a broadcast. Failing radios now finish their current frame first (see `docs/ns3-defaults.md`).
- NS-3's energy framework used gigabytes of memory per 100-node run; it now runs only at 25 and 50 nodes (as a cross-check).
- DSDV needs more than the 60 s warm-up to build complete tables in some sparse 25-node topologies. Listed in `results/analysis/tables/check_initial_convergence.csv`.

## Chalakudy experiment (29 Oct 2026)

For the paper's data section, start with `docs/paper-data-guide.md`. Paper draft (Google Doc, the working copy Claude can edit): https://docs.google.com/document/d/1SNSzLxNARXC23C7tTHJGshCh_LWfS0TynoMmm9px1lE/edit (source: `docs/paper-scaffold.html`).

Read `data/chalakudy/WORKLOG.md` (what was done, in order, and every problem found), `data/chalakudy/PROVENANCE.md` (every number: measured, derived or assumed), `experiments/README.md` section 8 (method) and `results/analysis_chalakudy/FINDINGS.md` (numbers). Found along the way:

- OLSR runs with 150 devices crashed in our control-traffic counter, which did not expect fragmented routing packets. Fixed in `sim/manet/manet.cc`. The earlier experiments were affected slightly, without crashing (29 runs redone; see "Audit and corrections, 29 Oct 2026" below).
- NS-3's energy framework does not drain finite batteries correctly (its radio model stops counting at about 72% and never reports depletion). The experiments use the state-based battery, which is checked separately (`docs/ns3-defaults.md`).
- Sentinel-1 cannot see water between houses, so it cannot say which buildings flooded; the failure order comes from ground height.
- Under a cited path-loss model (3GPP TR 37.885 NLOS) the default radio reaches 62.8 m, and 100 devices in the square no longer form a network: the 150 m range assumption carries every result.

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
