# Deliverables handoff

Everything requested in `docs/deliverables.md`, sections 1–9, and where to find it. All of it is final as of 28 October 2026: 1,350 simulation runs, every metric recomputed from the raw files, the analysis regenerated and checked to reproduce exactly.

Paths are relative to the repo root (branch `overnight-experiments`). If you received zips, unzip `kerala-mesh-deliverables.zip` (everything you need to write, about 8 MB) and, only if you need the per-run raw files, `kerala-mesh-raw-runs.zip` (about 93 MB) in the same place. Both unpack into one `kerala-mesh-deliverables/` folder, and the paths below apply inside it.

## Start here

| If you need | Open |
|---|---|
| Every number, one row per run, in the format of deliverables §7 | `results/analysis/tables/summary_table_all_runs.csv` |
| Mean, standard deviation, n and 95% CI per configuration | `results/analysis/tables/<experiment>_by_config.csv` |
| Statistical tests | `results/analysis/tables/<experiment>_stats_tests.csv` |
| A readable digest of the means and significant differences | `results/analysis/FINDINGS.md` |
| Figures for the paper (PDF) and for viewing (PNG) | `results/analysis/figures/` |
| How everything was set up, every metric definition, checks, limitations | `experiments/README.md` |
| What each results file contains | `results/README.md` |

## The experiments

| Experiment | What varies | Runs |
|---|---|---|
| `main` | 3 protocols × 6 scenarios × 25/50/100 nodes × seeds 1–10 | 540 |
| `severity` | 3 protocols × random relay nodes or random links × 5/10/20/30% × 50 nodes × 10 seeds | 240 |
| `load` | 3 protocols × baseline or node failure × 5/10/20 flows × 50 nodes × 10 seeds | 180 |
| `energy` | 3 protocols × 2 radio profiles × 50 nodes × 10 seeds; batteries run out, no other failures | 60 |
| `kerala` | 3 protocols × no-flood control, Kerala-anchored 27% and 50%, random 27% and 50% × 50 nodes × 10 seeds | 150 |
| `kerala100` | The same as `kerala` at 100 nodes (extra, beyond the list) | 150 |
| `rtscts100` | 100-node baseline with RTS/CTS on (extra sensitivity check) | 30 |

Protocols: AODV, OLSR and DSDV, all with NS-3.47 default parameters.

## §1 Simulation configuration

Full table with reasons: `experiments/README.md`, section 1. Every run's exact settings: `results/<experiment>/runs/<run_id>/run_config.json` and `command.txt`.

| Item | Value |
|---|---|
| NS-3 version | 3.47 (optimized build) |
| Routing protocols | AODV, OLSR, DSDV (NS-3 implementations, default parameters; timers in `docs/ns3-defaults.md`) |
| Network type and topology | Flat ad-hoc mesh (802.11 IBSS). Uniform random placement, redrawn until connected. The same topology per node count and seed for every protocol and scenario |
| Total nodes | 25, 50, 100 (main); 50 (severity, load, energy, kerala); 100 (kerala100, rtscts100) |
| Sources, destinations, relays, coordinators | 10 flows (5/10/20 in the load sweep, 20 in Kerala); random pairs at least 2 hops apart; every node can relay; no coordinators |
| Node coordinates | `results/<experiment>/inputs/n<N>_s<seed>/topology.csv` (metres) |
| Simulation area | 500 m × 500 m for every node count (mean degree 5.2, 10.5 and 22.4 at 25, 50 and 100 nodes) |
| Wireless standard and channel | IEEE 802.11b, `AdhocWifiMac`, one shared `YansWifiChannel` |
| Transmit power, sensitivity, range | 16.02 dBm; −101 dBm; 150 m |
| Propagation loss and delay | `RangePropagationLossModel` (MaxRange 150 m) plus a project model that silences failed links; `ConstantSpeedPropagationDelayModel` |
| Data rate and MAC | `ConstantRateWifiManager`: data 11 Mbps, control 1 Mbps; RTS/CTS off; retry limits 7/4; MAC queue 500 packets / 500 ms; ARP pre-filled |
| Packet size | 512 B UDP payload (540 B at IP) |
| Traffic model and transport | UDP. Constant bit rate (main, severity, load, energy); short bursts (Kerala) |
| Rate and start/stop | 4 packets/s per flow, 60 s to 290 s (595 s in energy). Kerala: bursts of 5 packets 0.2 s apart, exponential gaps averaging 15 s, 60 s to 448 s |
| Duration | 300 s (main, severity, load, rtscts100); 600 s (energy); 450 s (Kerala) |
| Seeds and run numbers | Seeds 1–10; `RngSeedManager::SetSeed(1)`, `SetRun(seed)` |
| Mobility | None (`ConstantPositionMobilityModel`, speed 0) |
| Warm-up | 60 s with no traffic so the proactive protocols can build their tables |

## §2 Disaster scenarios

Definitions and the assumption behind each: `experiments/README.md`, section 2.

| Scenario | What fails | When | Selection |
|---|---|---|---|
| `baseline` | Nothing | n/a | n/a |
| `link_fail` | The 5 links carrying the most traffic | 120 s, permanent | Deterministic |
| `node_fail` | The busiest 10% of relays | 120 s, permanent | Deterministic |
| `multi_fail` | Three waves of 5% of relays and 5% of links | 120, 135, 150 s | Random (seeded) |
| `partition` | Every link crossing the vertical midline | 120 s to 210 s, then restored | Deterministic |
| `recovery` | The same relays as `node_fail` | 120 s to 210 s, then restored | Deterministic |
| `random_nodes`, `random_links` (severity) | 5/10/20/30% of nodes or links | 120 s, permanent | Random (seeded) |
| Kerala `kerala_27`, `kerala_50` | 27% or 50% of nodes, lowest ground first, following a dated flood curve; then batteries run down | Compressed timeline, 1 day = 30 s | Spatially correlated |
| Kerala `uniform_27`, `uniform_50`, `control` | Same counts and times at random nodes; or no flood failures | As above | Random / none |

Recorded for every scenario and run:

- Failure start and end time, identity and coordinates of each failed node and link, number and % affected, whether each flow still has an alternative route, and whether selection was deterministic or random: `results/<experiment>/inputs/n<N>_s<seed>/scenario_<name>.json`.
- The same, averaged per scenario and node count: `results/analysis/tables/scenario_properties.csv`.
- The assumption linking the scenario to disaster disruption: the `assumption` field in each `scenario_*.json`.
- Kerala assumptions: `kerala_assumptions.json` in each Kerala input folder; the sources are in `data/sources.md`.

The Kerala scenarios are hypothetical and anchored to dated 2018 events. They are not measurements from Kerala, and the paper must not present them as such.

## §3 Core performance metrics

Per run in `results/<experiment>/summary.csv` and in the §7 summary table. Mean, standard deviation, n and 95% CI per configuration in `<experiment>_by_config.csv`. Exact definitions: `experiments/README.md`, section 3.

| Metric | Columns |
|---|---|
| PDR, with counts | `packets_sent`, `packets_received`, `pdr_pct` |
| End-to-end delay (ms) | `delay_mean_ms`, `delay_median_ms`, `delay_std_ms`, `delay_p95_ms`, `delay_max_ms` |
| Throughput (kbps) and interval | `throughput_kbps`, `throughput_interval_s` |
| Routing overhead | `control_pkts`, `control_bytes`, `control_pkts_traffic_period`, `control_bytes_traffic_period`, `control_pkts_per_node_s`; overhead relative to delivered data: `nrl_ctrl_per_delivered` (control packets per delivered packet), `ctrl_bytes_per_payload_byte` |
| Packet loss and reason | `packets_lost`, `loss_pct`, `lost_<reason>` (no route at source, IP route error, MAC retry limit, and so on) |
| Recovery time | `recovery_time_s` (mean over recovered flows); also `recovery_median_s`, `recovery_max_s`, `recovery_recovered_flows`, `recovery_not_recovered_flows`, `recovery_affected_no_route`; per event and flow in `results/<experiment>/recovery.csv` |
| Delivered within deadline T (the paper's primary metric) | `within_0.5s_pct`, `within_1s_pct`, `within_2s_pct`, `within_5s_pct` (T is a placeholder until set from Kerala data) |

## §4 Additional metrics

| Metric | Columns |
|---|---|
| Route discovery time and number (AODV) | `route_discoveries`, `route_discoveries_completed`, `route_discovery_attempts`, `route_discovery_mean_ms`, `route_discovery_median_ms`, `route_discovery_p95_ms` |
| Route errors (AODV) | `route_errors_rerr_tx` |
| Routing-table convergence (OLSR, DSDV) | `initial_convergence_s`, `convergence_after_events_s`, `convergence_mean_s`, `route_validity_mean_pct` |
| Broken routes (link breaks detected) | `mac_link_break_detections` |
| Successful transmissions during recovery | `recovery_window_delivered`, `recovery_window_pdr_pct` (10 s after each failure) |
| Time without successful delivery | `recovery_outage_mean_s`; per flow `longest_delivery_gap_s` in `per_flow.csv` |
| Per-node energy | `energy_total_J`, `energy_mean_per_node_J`, `energy_max_node_J`; per node in each run's `energy.csv` |
| Network lifetime | `first_depletion_s`, `depletion_10pct_s`, `depletion_50pct_s` (energy and Kerala experiments) |
| Control traffic before, during, after failure | `pre_ctrl_pkts_per_node_s`, `during_ctrl_pkts_per_node_s`, `post_ctrl_pkts_per_node_s` |
| Connected PDR (the connectivity control) | `sent_while_connected`, `connected_pdr_pct`, `connected_within_1s_pct` (energy and Kerala) |

Metrics that don't apply to a protocol are left empty, never reported as zero.

## §5 Density and robustness

- Node counts: `main` (25/50/100, same 500 m × 500 m area, so density rises with node count).
- Failure severity: `severity` (5/10/20/30%).
- Traffic load: `load` (5/10/20 flows).
- Seeds: 1–10 for every configuration; paired design (for a given seed every protocol sees the same topology, traffic and failures).
- Mean and standard deviation, n and 95% CI: `<experiment>_by_config.csv`.
- Repetitions: 10 per configuration.
- Failed or incomplete runs: none in the final datasets (`results/<experiment>/failed_runs.csv`, `results/analysis/tables/failed_runs_all.csv`). Four 100-node runs failed on a first attempt (memory) and were redone: `results/main/failed_runs_history.csv`.
- Non-target variables: only the failure schedule changes between scenarios.

## §6 Raw files

| Requested | Where |
|---|---|
| Source code | `sim/manet/manet.cc`, `sim/diamond/diamond.cc`, `experiments/*.py`, `scripts/` |
| Exact commands and arguments | `results/<experiment>/commands.txt`; per run `command.txt` and `run_config.json` |
| Standard output and error logs | per run `stdout.log`, `stderr.log` (no run logged an error) |
| FlowMonitor XML | `flowmon.xml.gz` in seed 1 of every main-grid configuration |
| Packet captures (.pcap) | Not enabled: gigabytes per run; the per-packet log holds the same delivery information |
| Routing and topology traces | `rtables-<t>s.txt.gz` (seed 1 of the main grid), `routes.csv.gz` (OLSR/DSDV), `topology.csv`, `topology_info.json` |
| Failure-event logs with timestamps | per run `events.csv` |
| Per-run CSVs | per run `packets.csv.gz`, `control.csv.gz`, `energy.csv`, `discoveries.csv.gz`, `stats.csv`, `per_flow.csv`, `recovery.csv`, `summary.json` |
| README | `experiments/README.md`, `results/README.md` |

Per-run folders: `results/<experiment>/runs/<protocol>_<scenario>_n<nodes>_f<flows>_s<seed>/`.

## §7 Summary table

`results/analysis/tables/summary_table_all_runs.csv`: 1,350 rows, one per protocol, scenario, configuration and seed, with the columns from §7 (protocol, scenario, node count, seed and run ID, failure time, severity, packets sent and received, PDR, mean and 95th-percentile delay, throughput, control packets and bytes, packet loss, recovery time, energy). Per experiment: `summary_table_<experiment>.csv`. "Recovery time" says "unavailable" where no failure happened or no affected flow recovered.

## §8 Outputs for the paper

| Requested | Figures (in `results/analysis/figures/`, PDF and PNG) | Tables |
|---|---|---|
| PDR across protocols and scenarios | `main_pdr` | `main_by_config.csv` |
| End-to-end delay | `main_delay_mean`, `main_delay_p95`, `delay_cdf_node_fail_n50` | same |
| Throughput | `main_throughput` | same |
| Routing overhead | `main_control_per_node_s`, `main_control_bytes`, `main_nrl` | same |
| Recovery time after failures | `main_recovery_after_failure`, `main_recovery_after_restore`, `severity_recovery` | same |
| Performance vs node density | `density_pdr`, `density_delay_mean`, `density_within_1s`, `density_control_per_node_s` | `main_by_config.csv` |
| Performance vs failure severity | `severity_pdr`, `severity_delay_mean`, `severity_within_1s`, `severity_control_per_node_s` | `severity_by_config.csv` |
| Performance vs traffic load | `load_pdr`, `load_delay_mean`, `load_delay_p95`, `load_throughput`, `load_nrl` | `load_by_config.csv` |
| Delivered within T | `main_within_1s`, `main_deadline_sweep_n25/n50/n100` | `main_by_config.csv` |
| Packet loss | `main_loss` | same |
| Control traffic before, during, after failure | `control_over_time_node_fail_n50`, `control_over_time_partition_n50` | |
| Energy and network lifetime | `main_energy_per_node`, `energy_lifetime`, `energy_over_time` | `energy_by_config.csv` |
| Kerala-anchored experiment (acute vs sustained phase) | `kerala_within_T_by_phase_n50/n100`, `kerala_deadline_sweep_n50/n100`, `kerala_over_time_n50/n100` | `kerala_by_config.csv` |
| RTS/CTS sensitivity (extra) | `sensitivity_rtscts_n100` | `sensitivity_rtscts_n100_by_config.csv` |

- **Error bars:** every bar and point is the mean over 10 seeds with a 95% confidence interval (t-distribution), clipped at 0 and 100%.
- **Statistical tests:** `<experiment>_stats_tests.csv`. A Friedman test across the three protocols, then pairwise Wilcoxon signed-rank tests paired by seed, Holm-corrected over the three pairs. `FINDINGS.md` lists only differences with corrected p < 0.05, plus the median paired difference.
- **Checks to cite:** `check_tracker_vs_flowmonitor.csv` (the packet tracker vs NS-3's FlowMonitor), `check_energy_vs_ns3_model.csv` (energy accounting vs NS-3's energy model), `check_initial_convergence.csv` (DSDV start-up in sparse networks).
- **Limitations and deviations for the discussion section:** `experiments/README.md`, section 7. In short: unit-disk radio; static nodes; constant-rate traffic outside Kerala; RTS/CTS off; default protocol parameters; a Wi-Fi-only energy model in which idle listening dominates; time compression and assumed parameters in the Kerala scenario; targeted vs random failures; predictions were not written before the runs; DSDV included because the deliverables list asks for it.
- **Reproducibility:** `experiments/README.md` ("Reproducing", sections 6 and 7). One command per experiment regenerates everything.

## §9 Minimum vs stronger dataset

| Minimum viable dataset | Status |
|---|---|
| AODV, OLSR and DSDV under a baseline and at least one failure scenario | Done (6 scenarios) |
| PDR, mean delay, throughput, routing overhead | Done |
| Defined failure and recovery events | Done |
| Repeated runs with documented seeds | Done (10 seeds per configuration) |
| Raw output files and exact configurations | Done |

| Stronger research dataset | Status |
|---|---|
| Multiple network sizes | Done (25, 50, 100) |
| Several failure severities | Done (5, 10, 20, 30%) |
| Node and link failures | Done |
| Network partitions | Done |
| Recovery experiments | Done |
| Delay distributions | Done (median, p95, max, CDF figure) |
| Control-byte overhead | Done |
| Statistical analysis | Done |
| Reproducible source code | Done |

## Corrections made on 28 October 2026

All 1,350 runs were checked: every configuration has 10 seeds, there are no duplicates or failed runs, no run logged an error, and every raw file is present. Every run's metrics were recomputed from its raw files and matched the committed summaries exactly. Two errors were fixed and everything downstream was regenerated:

1. **Time without delivery (§4).** A flow's longest stretch without a delivery (`longest_delivery_gap_s`) left out the time from its last delivery to the end of traffic. Flows that were cut off for good were therefore undercounted (148 of 5,400 flows in the main grid, by about 170 s at the median). Fixed in `experiments/metrics.py`.
2. **Paired tests (§8).** Protocols that tie exactly were treated as slightly different because of floating-point noise around 1e-15, which made some p-values too small. Values are now rounded to 9 decimal places before testing. As a result, 24 Holm-corrected comparisons, mostly median-delay ones, are no longer significant at 0.05. Fixed in `experiments/analyze.py`; all tables, figures and `FINDINGS.md` regenerated. The analysis now reproduces identically on repeated runs.

Any summary or figure taken from the repo before this date should be replaced with the current files.

## Chalakudy experiment (added 29 October 2026, branch `chalakudy-buildings`)

A further experiment: mesh devices at real building positions in a 1 km square of Chalakudy town, with flood failures ordered by real data (Sentinel-1 radar, Copernicus elevation) and timed by the dated 2018 events. Nothing in the seven experiments above was changed or rerun. Every number in the scenario is labelled MEASURED, DERIVED or ASSUMED in `data/chalakudy/PROVENANCE.md`; the step-by-step log, including every problem found, is `data/chalakudy/WORKLOG.md`.

| If you need | Open |
|---|---|
| What is real data, what is assumed, with sources, licences and checksums | `data/chalakudy/PROVENANCE.md`, `data/chalakudy/downloads.csv`, `data/chalakudy/derived_files.csv` |
| Files this session could not download (please fetch) | `data/chalakudy/MANUAL_DOWNLOADS.md` |
| Method | `experiments/README.md`, section 8 (limitations in section 7) |
| Numbers: means ± 95% CI, tests, checks | `results/analysis_chalakudy/FINDINGS.md` |
| Tables | `results/analysis_chalakudy/tables/` (`chalakudy_by_config.csv`, `chalakudy_protocol_tests.csv`, `chalakudy_flood_vs_uniform_tests.csv`, `summary_table_chalakudy.csv`, `scenario_properties.csv`, `check_*.csv`) |
| Figures (PDF and PNG; every caption says what is real and what is assumed) | `results/analysis_chalakudy/figures/` |

| Experiment | What varies | Runs |
|---|---|---|
| `chalakudy` | 3 protocols × {no-flood control, flood 25% (lowest ground first), uniform random 25%} × onset 15 or 17 Aug × batteries unlimited or limited × 100 devices × seeds 1–10 | 360 |
| `chalakudy_prop` | Propagation sensitivity: 3GPP TR 37.885 NLOS log-distance model instead of the 150 m unit disk | 90 |
| `chalakudy_share` | Flooded share 10% and 50% | 120 |
| `chalakudy_battery` | Battery share for the radio 25% and 100% (main 50%) | 180 |
| `chalakudy_traffic` | Mean gap between message bursts 7.5 s and 30 s (main 15 s) | 180 |
| `chalakudy_check` | Cross-checks: FlowMonitor and NS-3's energy framework, 50 devices, seeds 1–2 | 36 |

The 50- and 150-device sweep (`chalakudy_nodes`) was not run (owner's compute decision, 29 Oct); density is covered at the graph level by `data/chalakudy/network_structure.csv` and the figure `chalakudy_network_density`.

Deliverables §1–9 for this experiment:

| Section | Where |
|---|---|
| §1 Configuration | As in §1 above except: 100 devices at building centroids in a 1 km square (coordinates in `results/chalakudy*/inputs/n100_s<seed>/topology.csv`, building ids in `nodes.csv`); 20 burst flows; 450 s with 1 day = 30 s; per-run `run_config.json` and `command.txt` |
| §2 Scenarios | Flood order, uniform random with the same counts and times, no-flood control; each run's `scenario_*.json` lists every failed device with its time, position, building and ground estimate; averages and clustering in `tables/scenario_properties.csv` |
| §3 Core metrics | `results/chalakudy*/summary.csv`; per window (before onset, acute, sustained): `<window>_within_1s_pct`, `<window>_pdr_pct`, `<window>_delay_mean_ms`, `<window>_ctrl_pkts_per_node_s` |
| §4 Additional metrics | As in §4 above; connected PDR (`connected_pdr_pct`, `<window>_connected_within_1s_pct`) for every run; battery lifetime in battery-limited runs |
| §5 Robustness | Seeds 1–10, paired; sweeps of flooded share, battery share and traffic; onsets 15 and 17 Aug; no failed runs (`tables/check_failed_runs.csv`) |
| §6 Raw files | Per run as in §6 above; FlowMonitor XML in `chalakudy_check`; raw data downloads re-fetched by `experiments/chalakudy_fetch.py` (not committed, about 170 MB) |
| §7 Summary table | `results/analysis_chalakudy/tables/summary_table_chalakudy.csv` |
| §8 Outputs | Figures `chalakudy_within_T_by_window*`, `chalakudy_connected_within_T_by_window`, `chalakudy_over_time_*`, `chalakudy_sensitivity_acute`, `chalakudy_network_density`, `chalakudy_study_area`, `chalakudy_qa_geolocation`; tests in `tables/`; checks in `FINDINGS.md` |
| §9 Dataset | Real positions and real-data failure order for the stronger dataset; the remaining gaps are listed in `MANUAL_DOWNLOADS.md` and `PROVENANCE.md` |
