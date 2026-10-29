# Experiments: how they were run

This folder holds everything that turns the simulator (`sim/manet/manet.cc`) into the dataset requested in `docs/deliverables.md`. Every number in `results/` can be regenerated from the commands below.

- `gen.py` builds the inputs of a run: node positions, traffic and failure schedule.
- `kerala.py` builds the energy-depletion experiment and the Kerala-anchored failure experiment.
- `run_experiment.py` runs a whole experiment grid in parallel and computes the metrics for each run.
- `metrics.py` turns one run's raw output into the metrics (the definitions are in its docstring and below).
- `analyze.py` builds the tables, figures and statistical tests in `results/analysis/`.
- Chalakudy experiment (section 8): `chalakudy_fetch.py` downloads the raw data, `chalakudy_flood.py` maps water on the Sentinel-1 images, `chalakudy.py` turns the data into simulator inputs (every parameter, with its kind and reasoning, is in its `PARAMS`), `chalakudy_provenance.py` writes `data/chalakudy/PROVENANCE.md`, and `analyze_chalakudy.py` writes `results/analysis_chalakudy/`.

## Reproducing

```bash
scripts/setup.sh                                   # NS-3.47 with AODV, OLSR, DSDV
pip install numpy pandas scipy matplotlib networkx
python3 experiments/run_experiment.py main         # also: severity, load, energy, kerala
python3 experiments/analyze.py
```

Chalakudy (section 8), after the commands above:

```bash
pip install pyarrow shapely pyproj rasterio requests
python3 experiments/chalakudy_fetch.py boundary            # needs data/chalakudy/raw/ (re-fetch: see the script)
python3 experiments/chalakudy_flood.py                     # Sentinel-1 water maps (reads image windows over HTTP)
python3 experiments/chalakudy.py prepare                   # buildings.csv, study_area.json
python3 experiments/chalakudy.py network                   # network_structure.csv
python3 experiments/chalakudy_provenance.py                # PROVENANCE.md, derived_files.csv
python3 experiments/run_experiment.py chalakudy            # also: chalakudy_prop, chalakudy_share,
                                                           #   chalakudy_battery, chalakudy_traffic, chalakudy_check
python3 experiments/analyze_chalakudy.py
```

An interrupted experiment resumes where it stopped: finished runs are skipped. The exact command of every run is in `results/<experiment>/commands.txt` and in each run folder (`command.txt`, plus `run_config.json` with every setting).

## 1. Simulation configuration

The same for every experiment unless the table says otherwise.

| Item | Setting |
|---|---|
| NS-3 version | 3.47 (ns-allinone-3.47), optimized build |
| Routing protocols | AODV, OLSR, DSDV, NS-3 implementations with default parameters (timers in `docs/ns3-defaults.md`) |
| Network type and topology | Flat ad-hoc mesh (802.11 IBSS), no hierarchy. Random uniform placement, redrawn until every node can reach every other node (connected unit-disk graph). One topology per (node count, seed), shared by all protocols and scenarios |
| Total nodes | 25, 50 and 100 (main grid); 50 (severity, load, energy and Kerala experiments) |
| Sources, destinations, relays, coordinators | 10 flows (5, 10 or 20 in the load sweep; 20 in the Kerala experiment). Source–destination pairs are drawn at random among pairs at least 2 hops apart, so every flow needs at least one relay. A node may be in several flows. Every node can relay. No coordinator nodes |
| Node coordinates | `results/<experiment>/inputs/n<N>_s<seed>/topology.csv` (metres) |
| Simulation area | 500 m × 500 m for every node count, so density grows with node count: mean degree 5.2 (25 nodes), 10.5 (50), 22.4 (100); diameter 5–11 hops (25 nodes), 5–6 (50), 5 (100) |
| Wireless standard and channel | IEEE 802.11b, `AdhocWifiMac`, one shared channel (`YansWifiChannel` / `YansWifiPhy`) |
| Transmit power, sensitivity, range | 16.02 dBm (NS-3 default); receiver sensitivity -101 dBm (NS-3 default, irrelevant under the range model); range 150 m for both communication and interference |
| Propagation loss and delay | `RangePropagationLossModel` (MaxRange 150 m: full power inside, nothing outside) followed by a project model that silences failed links; `ConstantSpeedPropagationDelayModel` (speed of light) |
| Data rate and MAC | `ConstantRateWifiManager`: data at DSSS 11 Mbps, control frames and broadcasts at DSSS 1 Mbps. RTS/CTS off; retry limits 7 (short) / 4 (long); MAC queue 500 packets or 500 ms (all NS-3 defaults). ARP tables pre-filled with permanent entries (see Checks) |
| Packet size | 512 B UDP payload (including a 12 B sequence number and timestamp header), 540 B at the IP layer |
| Traffic model and transport | UDP. Main, severity and load: constant bit rate. Kerala: short bursts (5 packets 0.2 s apart; exponential gaps between bursts, mean 15 s) |
| Packet rate, start, stop | CBR: 4 packets/s per flow (16.4 kbps of payload), from 60 s plus a random offset under 0.25 s, until 290 s (595 s in the energy experiment). Kerala: from 60 s to 448 s |
| Simulation duration | 300 s (main, severity, load); 600 s (energy); 450 s (Kerala) |
| Seeds and run numbers | Seeds 1–10. NS-3: `RngSeedManager::SetSeed(1)`, `SetRun(seed)`. Inputs (positions, flows, random failures, batteries) use NumPy generators seeded from (node count, seed): see `gen.topo_seed` |
| Mobility | None: `ConstantPositionMobilityModel` (nodes are static) |
| Energy | Every run measures each radio's time in each PHY state and converts it to joules with NS-3's `WifiRadioEnergyModel` currents at 3 V (see Checks). Batteries run out only in the energy and Kerala experiments |
| Warm-up | No traffic during the first 60 s, so OLSR and DSDV can build their tables. OLSR's tables were always complete by then. DSDV's were not in a few sparse 25-node topologies (up to 11 hops across), where DSDV needs longer: `results/analysis/tables/check_initial_convergence.csv` lists those runs, and `initial_convergence_s` in the summaries gives the time for every run |

## 2. Disaster scenarios

None of these failures are Kerala measurements. They are modelling choices meant to stand for kinds of disruption that floods cause. The assumption behind each is stored next to its inputs (`scenario_<name>.json`, field `assumption`).

| Scenario | What fails | When | Chosen how | Deterministic? |
|---|---|---|---|---|
| `baseline` | Nothing | n/a | n/a | n/a |
| `link_fail` | 5 links (both devices stay up; they just can't hear each other: water, debris or a collapsed building in the way) | 120 s, until the end | The 5 links carrying the most traffic on shortest paths | Yes |
| `node_fail` | 10% of nodes, relays only (submerged, destroyed, or flat battery) | 120 s, until the end | The relays carrying the most traffic on shortest paths; flow endpoints are never failed | Yes |
| `multi_fail` | 3 waves, each 5% of nodes (relays) and 5% of links | 120, 135 and 150 s, until the end | Random (seeded) | No (random) |
| `partition` | Every link crossing the vertical midline: the network splits into a west and an east half | 120 s to 210 s, then restored | Geometric | Yes |
| `recovery` | The same relays as `node_fail` | 120 s to 210 s, then restored | As `node_fail` | Yes |
| `random_nodes` (severity sweep) | 5, 10, 20 or 30% of all nodes, relays only | 120 s, until the end | Random (seeded) | No |
| `random_links` (severity sweep) | 5, 10, 20 or 30% of all links | 120 s, until the end | Random (seeded) | No |

For every run, `scenario_<name>.json` records: failure start and end time, the identity and coordinates of every failed node and link (links by their midpoint), the number and percentage of nodes and links affected, the number of connected pieces the network splits into, and whether each flow still has a route after the failures (`per_flow` → `alternative_route_exists`). `results/analysis/tables/scenario_properties.csv` averages these per scenario and node count.

Note that in sparse 25-node networks the targeted `link_fail` and `node_fail` choices can cut flows off completely, so they partly behave like a partition. The per-flow `alternative_route_exists` field shows when that happens.

The Kerala experiment has its own scenarios: see section 5.

## 3. Metrics

All computed by `metrics.py` from the per-packet log, so they can be recomputed from the raw files.

| Metric | Definition |
|---|---|
| Packets sent | Data packets the source application created while its radio was on. Packets that couldn't be created because the source's radio was already off are counted separately (`suppressed_sends`) |
| Packets received, PDR | Distinct packets that reached the destination application; PDR = received / sent × 100 |
| End-to-end delay | Receive time minus send time of each delivered packet: mean, median, standard deviation, 95th percentile and maximum, in ms |
| Delivered within T | Share of sent packets delivered with delay ≤ T, for T = 0.5, 1, 2 and 5 s. T is a placeholder until it is set from Kerala data |
| Throughput | UDP payload bits delivered ÷ length of the traffic period (60–290 s in the main grid; the interval is stored in `throughput_interval_s`) |
| Control packets, control bytes | Routing packets each working node hands to its network interface, counting every rebroadcast. Bytes are IP-layer bytes (IP + UDP headers + routing message). Totals over the whole run |
| Normalised routing load | Control packets sent during the traffic period ÷ data packets delivered |
| Control-byte ratio | Control bytes during the traffic period ÷ payload bytes delivered |
| Packet loss and its reason | Lost = sent − received. The reason is the last drop event recorded for that packet: no route at the source; IP-layer drops (no route, route error such as a routing-protocol queue timeout, TTL expired); MAC drops (retry limit reached, i.e. the next hop never acknowledged; queue full; queue timeout). `no_drop_event` = lost without any recorded drop (still queued when the run ended) |
| Recovery time | For each failure event and each flow it affected: time from the event until the destination first receives a packet sent at or after the event. A flow counts as affected if the last packet it delivered before the event used a node or link that failed. Recovery is measured only for affected flows that still had a route; flows left without any route are counted separately (`recovery_affected_no_route`). Measurement stops at the next restore (or the end of traffic), so a restore isn't credited to rerouting. The mean, median and maximum are over flows that recovered; flows that never did are counted in `recovery_not_recovered_flows`. `recovery_from_next_send_mean_s` counts from the flow's first send after the event instead; it differs only for bursty traffic (Kerala), where a flow may be silent when the failure happens |
| Recovery after restore | After a restore event, for flows that delivered nothing in the previous 5 s: time until the first delivery of a packet sent after the restore |
| Delivery during recovery | Packets sent and delivered by affected flows in the 10 s after each failure (`recovery_window_pdr_pct`) |
| Time without delivery | Per affected flow, time from the event until delivery resumes, or until the next event if it never does (`recovery_outage_mean_s`); and the longest stretch without a delivery for each flow, counting from the start of traffic, between deliveries, and from the last delivery to the end of traffic (`longest_delivery_gap_s` in `per_flow.csv`) |
| Route discoveries (AODV) | RREQs a node originates for a destination; retries of the same discovery are counted in `route_discovery_attempts`. Discovery time = first RREQ until the RREP reaches the originator |
| Route errors (AODV) | RERR packets transmitted, including rebroadcasts |
| Link breaks detected | Unicast frames dropped by the MAC after the retry limit (`mac_link_break_detections`). This is what AODV reacts to; OLSR and DSDV don't use it |
| Routing-table convergence (OLSR, DSDV) | Every second, for every pair of working nodes that are connected, follow the routing tables hop by hop and check that they reach the destination over links that currently work. Validity = share of pairs that do. Convergence time = time from an event until validity is back to 100%. Not measurable for AODV (it only keeps routes it is using), so it is left empty |
| Control traffic before, during, after failure | Control packets per second in each window divided by the total number of nodes (failed ones included): `pre_`, `during_`, `post_` columns (windows in `*_window_s`) |
| Energy | Per node: time in each radio state × the `WifiRadioEnergyModel` current × 3 V. `energy_total_J`, `energy_mean_per_node_J` |
| Network lifetime (energy and Kerala) | Times at which the first node, 10% of nodes and 50% of nodes ran out of battery |
| Connected PDR (energy and Kerala) | Delivered ÷ packets sent while a path existed between source and destination (checked against the topology and every failure and battery death up to that moment). This is the connectivity control |

Metrics that don't apply to a protocol are left empty, never set to zero.

## 4. Experiments

| Experiment | Grid | Runs |
|---|---|---|
| `main` | 3 protocols × 6 scenarios × 25/50/100 nodes × seeds 1–10 | 540 |
| `severity` | 3 protocols × {random relay nodes, random links} × {5, 10, 20, 30}% × 50 nodes × seeds 1–10 | 240 |
| `load` | 3 protocols × {baseline, node_fail} × {5, 10, 20} flows × 50 nodes × seeds 1–10 | 180 |
| `energy` | 3 protocols × 2 radio profiles × 50 nodes × seeds 1–10, batteries run out | 60 |
| `kerala` | 3 protocols × {no-flood control, Kerala 27%, random 27%, Kerala 50%, random 50%} × 50 nodes × seeds 1–10 | 150 |
| `kerala100` | The same as `kerala`, with 100 nodes | 150 |
| `rtscts100` | Sensitivity check: 3 protocols × baseline × 100 nodes × seeds 1–10 with RTS/CTS switched on (same topologies and traffic as the main grid) | 30 |
| `chalakudy` | Section 8. 3 protocols × {no-flood control, flood 25% (real-data order), uniform random 25%} × onset 15 or 17 Aug × batteries unlimited or limited × 100 devices at real building positions × seeds 1–10 | 360 |
| `chalakudy_prop` | As `chalakudy` (onset 15 Aug, batteries unlimited) with a log-distance radio (3GPP TR 37.885 NLOS formula) instead of the 150 m unit disk | 90 |
| `chalakudy_share` | Flooded share 10% and 50% (flood and uniform), onset 15 Aug, batteries unlimited | 120 |
| `chalakudy_battery` | Batteries limited with 25% and 100% of the battery left for the radio (main: 50%), onset 15 Aug | 180 |
| `chalakudy_traffic` | Mean gap between message bursts 7.5 s and 30 s (main: 15 s), onset 15 Aug, batteries unlimited | 180 |
| `chalakudy_check` | Cross-checks: 50 devices, seeds 1–2, FlowMonitor and NS-3's energy framework on | 36 |

Failed or incomplete runs, with the reason, are listed in `results/<experiment>/failed_runs.csv` (final pass) and `results/analysis/tables/failed_runs_all.csv`. In the final datasets no run failed. Earlier attempts of four 100-node runs failed (three killed for lack of memory, one crash); all were redone, and the history is in `results/main/failed_runs_history.csv`.

## 5. Energy and Kerala experiments

**Energy.** No failures; every node starts with a random amount of battery and nothing recharges. Each node's battery is sized so that, idling only, it would last a random time between 200 and 600 s. As in NS-3's `BasicEnergySource`, a radio switches off at 10% charge left. Two radio profiles:

- `default_radio`: NS-3 default currents. An idle radio draws 0.273 A, almost as much as receiving (0.313 A), so routing traffic changes battery life only a little.
- `low_idle_radio`: a hypothetical radio drawing 0.033 A when idle (NS-3's sleep current), so that energy depends mainly on sending and receiving. This shows the most that a protocol's control traffic could matter.

**Kerala-anchored failures.** A time-compressed, hypothetical scenario whose order and timing of events come from the dated 2018 events in `data/sources.md`. Every assumption is in `kerala.py` (`KERALA_ASSUMPTIONS`) and is copied to `results/kerala/inputs/*/kerala_assumptions.json`:

- 1 day = 30 simulated seconds. 14 Aug 2018 00:00 is at 60 s; the run ends on 27 Aug, the day the last Thrissur substation got power back (KSEB).
- Acute phase, 14–18 Aug: nodes fail as the water rises (dam releases 14–18 Aug, IMD red rain 15–17 Aug, Chalakudy flooded early 15 Aug). The share of eventual flood failures reached by each date is an assumed curve: 0%, 15%, 60%, 90% and 100% on 14, 15, 16, 17 and 18 Aug.
- 27% or 50% of nodes are lost to flooding by 18 Aug. 27% matches the statewide share of base stations down (a press figure, used as a floor); 50% is a harsher hypothetical.
- Spatial pattern: a river along the west edge; ground height grows eastward (plus noise); the lowest nodes flood first.
- Uniform-random baseline: the same number of failures at the same times, at random nodes.
- No-flood control: no flood failures.
- Sustained phase, 18–27 Aug: nothing recharges (power cut), so batteries run out one by one. Each node's battery would last, idling only, until a random date between 19 Aug and 6 Sep.
- Traffic: 20 flows of message bursts.

Only the failure process is compressed. Routing timers and packets run at real speed, so "one day" holds only 30 s of protocol activity. The scenario preserves the order and relative timing of events, not their absolute durations.

## 6. Checks

- **Reproducibility and corrections (28 Oct 2026).** Every run's metrics were recomputed from its raw files with the final `metrics.py`; all summaries matched the committed ones exactly, and the analysis now gives identical tables and `FINDINGS.md` on repeated runs. Two errors were fixed: (1) a flow's longest stretch without delivery (`longest_delivery_gap_s`) left out the time from its last delivery to the end of traffic, so flows cut off for good were undercounted (148 of 5,400 flows in the main grid; median undercount about 170 s); (2) the paired tests treated protocols that tie exactly as slightly different because of floating-point noise in the CSV values (around 1e-15). Values are now rounded to 9 decimal places before the Friedman and Wilcoxon tests. This changed 24 Holm-corrected results from p < 0.05 to p ≥ 0.05, mostly median-delay comparisons.

- **AODV link-break detection.** `NeighborCacheHelper` (used at first to pre-fill ARP tables) creates entries that AODV's MAC lookup ignores, which silently disabled AODV's reaction to failed transmissions. A relay forwarding into a dead link then kept its route alive indefinitely. Both sims now pre-fill ARP with permanent entries. Details in `docs/ns3-defaults.md`.
- **Energy.** The state-based energy figure was compared with NS-3's own energy framework (`BasicEnergySource` + `WifiRadioEnergyModel`) in seed 1 of the main grid: `results/analysis/tables/check_energy_vs_ns3_model.csv`. They agree exactly except in the `recovery` scenario: NS-3's `WifiRadioEnergyModel` never leaves its OFF state once a radio has been switched off (`ChangeState` only updates the state while `m_currentState != OFF`), so it stops counting a radio that is switched back on. The state-based figure counts it. The energy and Kerala experiments use the state-based battery for this reason and for speed (the framework doubles run time). The comparison was run at 25 and 50 nodes only: at 100 nodes the framework's memory use grew to several gigabytes per run (each radio state change cancels and reschedules a far-future "battery empty" event, and cancelled events stay in the scheduler), and four such runs in parallel exhausted the machine's memory.
- **FlowMonitor.** Seed 1 of the main grid also ran NS-3's FlowMonitor: `check_tracker_vs_flowmonitor.csv`. Sent counts match except for packets the source refused because it had no route (FlowMonitor never sees them). Received counts match except where packets were delivered more than 10 s after sending: FlowMonitor declares those lost (`MaxPerHopDelay` = 10 s), while this project's tracker counts them as delivered, with their real delay.
- **Duplicates.** The destination counts each packet once. Extra copies are counted in `duplicate_receptions`.
- **Switching radios off.** NS-3.47 crashes if a radio is switched off while it is sending a broadcast frame (details in `docs/ns3-defaults.md`). A failing or battery-dead node therefore finishes the frame it is sending before its radio goes off (a few milliseconds at most). All runs with node failures were made with this rule.
- **Fragmented routing packets (29 Oct 2026).** OLSR puts up to 64 messages into one packet; with 150 devices on the Chalakudy building topologies some packets exceeded the 2,296-byte WiFi MTU and were sent as IP fragments. The IP `Tx` trace fires once per fragment, and `sim/manet`'s control-traffic counter parsed the first fragment as a whole OLSR packet, which crashed 3 of 4 pilot runs (segmentation fault). The counter now joins the fragments of a packet before parsing it, counts the packet once with the bytes of all its fragments, and the data-packet parsers skip later fragments. Seven committed runs from the earlier experiments (including the densest OLSR configurations) were rerun with the old and the fixed binary: all outputs identical to each other and to the committed files, and none had a fragmented routing packet. The diamond sim was rerun as well. Details in `docs/ns3-defaults.md`.
- **Memory.** Running NS-3's energy framework on 100-node runs exhausted the machine's memory on the first attempt (four runs were killed). Those runs were redone without the framework; see section 6, Energy.

## 7. Deviations and limitations

Read these before writing the methods and discussion sections.

- **Predictions were not written first.** `PREDICTIONS.md` was empty when these runs were made (owner's decision, 27 Oct 2026, to save time). Any prediction written now is not a blind prediction.
- **Chalakudy predictions were not written first either.** Before the `chalakudy` runs the owner was asked whether to record predictions in `PREDICTIONS.md` and chose to skip (29 Oct 2026). Two design findings from no-flood pilot checks were already in `data/chalakudy/WORKLOG.md` by then: with the assumed batteries and ns-3's radio currents every device runs flat within hours of the power cut under all three protocols, and with the cited log-distance model the 100-device network falls apart. Predictions written now about the Chalakudy results are not blind.
- **DSDV** was included because the deliverables list requires it, although `CLAUDE.md` lists it among parked ideas. Its results are separate columns and can be dropped.
- **Unit-disk radio.** Full signal within 150 m, nothing beyond: no fading, no gradual loss, no obstacles except the deliberate link failures. This keeps "is there a route?" exact, but real links are less clear-cut.
- **Static nodes.** No mobility. Fine for people sheltering in place; it doesn't cover rescue boats or people moving.
- **Constant-rate traffic** in the main experiments. Real emergency traffic is burstier (used in the Kerala experiment only).
- **DSDV start-up in sparse networks.** The 60 s warm-up was not enough for DSDV in some sparse 25-node topologies (see `check_initial_convergence.csv`), so part of DSDV's loss there comes from tables that were still being built. That is real DSDV behaviour (slow convergence over many hops), but say so if you compare DSDV at 25 nodes; those runs can be excluded using the check table.
- **No RTS/CTS** (the NS-3 default), so hidden-terminal collisions hit unicast frames in dense networks. AODV treats a frame that fails after the retry limit as a broken link, so collisions turn into route errors and new route discoveries. The `rtscts100` experiment repeats the 100-node baseline with RTS/CTS on to show how much this matters.
- **NS-3 default protocol parameters.** Tuning (for example a shorter OLSR HELLO interval) would change the results.
- **Energy model:** a fixed current per radio state, no sleep scheduling, and nothing but the Wi-Fi radio draws power. Idle listening dominates, which is a real property of always-on ad-hoc Wi-Fi but makes routing traffic a small share of energy use.
- **Time compression** in the Kerala experiment (see section 5).
- **Kerala parameters are assumptions** anchored to dates, not measurements: the flood curve shape, failure shares, spatial pattern, battery sizes and traffic.
- **Failure selection.** Targeted failures (the busiest relays and links) are a worst case; random failures (multi_fail, severity sweep) are a milder case. Real floods sit somewhere in between, and are spatially correlated (as in the Kerala experiment).
- **Chalakudy: the radar cannot see which buildings flooded.** Sentinel-1 shows flooded fields, but walls and trees make flooded built-up areas look like dry land, and there is no image between 10 and 20 Aug (the peak). In the study square no building lies within 20 m of radar-visible flood water, so devices fail in order of ground height alone. The ground height comes from a surface model (Copernicus DEM: trees and roofs included) and the square is nearly flat (10th–90th percentile of the ground estimate: 10.0–13.5 m). The flood failures are therefore only moderately clustered: with 100 devices and 25% lost, a failed device's nearest other failed device is 83 m away on average, against 104 m for uniform random failures (seeds 1–10; closer in 9 of 10 seeds). The flood pattern also splits the network into slightly fewer groups at the peak (3.3 vs 4.2 on average).
- **Chalakudy: the share of buildings flooded at the peak is assumed** (25%; 10% and 50% swept), as are the devices per building, the power-cut date (pending KSEB), battery size and charge, and the message traffic. `data/chalakudy/PROVENANCE.md` labels every number.
- **Chalakudy: batteries.** With mobile-device batteries of an assumed 3,000 mAh (placeholder) and NS-3's radio currents (0.82 W while idle, no power saving), every device runs flat within hours of the power cut, before most flood failures and under every protocol. The battery-limited runs therefore say little about protocols; the unlimited-battery runs isolate the flood effect.
- **Chalakudy: radio range.** The 150 m unit disk is kept for comparability. Under the cited 3GPP NLOS path-loss model, the NS-3 default radio reaches only 62.8 m, and 100 devices in the square no longer form a network (`chalakudy_prop`, `data/chalakudy/network_structure.csv`). The 150 m results assume line-of-sight-like links that a town under tree cover may not give.

## 8. Chalakudy experiment: real building positions and 2018 flood data

A 1 km × 1 km square of Chalakudy town (Thrissur district), with mesh devices at real building positions and flood failures ordered by real data. `data/chalakudy/PROVENANCE.md` lists every number in the scenario as MEASURED (cited), DERIVED (by a script here) or ASSUMED (with the reasoning and the range swept); `data/chalakudy/WORKLOG.md` is the step-by-step log, including what went wrong; `data/chalakudy/MANUAL_DOWNLOADS.md` lists the sources this session could not reach.

**Data.** Municipality boundary: DataMeet (ODbL). Buildings: Overture Maps 2026-10-21.0 (Google Open Buildings and OpenStreetMap), 21,355 in the municipality. Ground height: Copernicus DEM GLO-30. Rivers and ponds: OpenStreetMap via Overture. Water: 24 Sentinel-1 radar images from 5 Jan to 26 Sep 2018, mapped on a 10 m grid by `chalakudy_flood.py` (calibration, 5 × 5 speckle filter, terrain correction with a geoid offset estimated from the data (-96 m; the EGM2008 geoid model, checked afterwards, gives -95.7 m at the town centre), a per-image threshold, and change detection against dry-season water and the 28 Jul image). Event dates: `data/sources.md` (heavy rain 15–17 Aug, dam releases 14–18 Aug, Chalakudy flooded on 15 Aug or 17 Aug depending on the source, last Thrissur substation back on 27 Aug).

**Study square.** The 1 km square, at least 99% inside the municipality, with the most buildings among the town's lowest 25% by ground estimate (1,383 buildings). Ward boundaries were not available.

**Devices.** 100 per run (50 in `chalakudy_check`), each at the centroid of a different building drawn at random from the square (seeded by node count and seed). Static. The same devices for every protocol and scenario of a seed.

**Network structure.** At 150 m, 100 devices have 7.2 neighbours on average and 97% of them are in the largest connected group (`data/chalakudy/network_structure.csv`). The main grid's 25, 50 and 100 nodes sit in a 500 m square (100, 200 and 400 per km², mean degree 5.2, 10.5 and 22.4, always fully connected), so 100 Chalakudy devices per km² match the density of the 25-node main grid. Density effects must not be read as flood effects: compare the flood runs with the no-flood control of the same devices.

**Failure models (same failure counts and times in both flood models).**
- *Flood (real-data order):* devices fail from the onset day (15 or 17 Aug) until 18 Aug 00:00, evenly spaced in time, until 25% of them are down; devices near radar-visible flood water would fail first (none in this square), then the lowest ground first. Flooded devices do not come back.
- *Uniform random:* the same number of failures at the same times, at random devices.
- *No-flood control:* no flood failures.

**Batteries.** Unlimited (isolates the flood effect) or limited: from the power cut (assumed at the onset day) each device has its random charge (20–100%) × a share of an assumed 3,000 mAh, 3.85 V battery left for the radio (50%; 25% and 100% swept), time-compressed like the scenario. No recharging until the end of the run (27 Aug, when power returned).

**Traffic and time.** 20 flows between devices in the same connected group, at least 2 hops apart, chosen on the 150 m graph; bursts of 5 packets 0.2 s apart, exponential gaps (mean 15 s; 7.5 s and 30 s swept). 1 day = 30 simulated seconds, 14 Aug 00:00 at 60 s, end at 450 s (27 Aug 00:00); routing timers are not compressed. Windows: before onset (14 Aug to the onset day), acute (onset to 18 Aug), sustained (18 to 27 Aug).

**Propagation sensitivity (`chalakudy_prop`).** The unit disk is replaced by a log-distance model with the 3GPP TR 37.885 V2V-Urban NLOS formula (36.85 + 30 log10 d + 18.9 log10 f, f = 2.412 GHz: exponent 3, 44.08 dB at 1 m), as implemented in NS-3.47, without adjustment. With NS-3's default transmit power and preamble-detection threshold (-82 dBm) frames get through up to 62.8 m (checked with two devices: 100% at 62.5 m, 0% at 63 m). The same devices, flows and failures as the main runs are used; the connectivity metrics use 62.8 m as the link distance.

**Warm-up.** 60 s as in every experiment. In no-flood pilot runs OLSR's tables were complete within 13 s; DSDV's route validity reached its long-run level (96–99.7% of connected pairs) by 40–60 s and fluctuated around it for the whole run, so a longer warm-up would not have helped. `results/analysis_chalakudy/tables/check_routing_tables_control.csv` gives the values for every run.

**Results in brief** (means over seeds 1–10; all numbers, CIs and tests in `results/analysis_chalakudy/FINDINGS.md`). Delivered within T = 1 s, no battery limit, onset 15 Aug, 25% flooded:

- *Without any flooding* OLSR delivers 100% within 1 s, DSDV 96–98% and AODV 90–91% (acute and sustained windows, both onsets; AODV below OLSR by about 9 points, Holm p < 0.01). This gap comes from the real topology and the bursty traffic, not from flooding: it grows with the time between bursts (about 4, 9 and 12–15 points at 7.5, 15 and 30 s), and so do AODV's route discoveries per burst (1.6, 2.3, 3.0) and its 95th-percentile discovery time (0.5, 1.0, 1.3 s), while AODV's PDR stays at 97–98%. That is consistent with AODV's routes expiring between bursts, so each burst waits for a new discovery; it was not tested directly.
- *Acute phase with flooding:* OLSR 75.8%, AODV 72.3%, DSDV 70.2% (flood order); 75.9%, 75.9%, 65.8% (uniform random). OLSR vs AODV is not significant here. Across the 12 flooded configurations without battery limits (both failure models × the share and traffic sweeps), OLSR is significantly ahead of AODV in 4 (10% flooded, and a 30 s gap between bursts) and never behind; OLSR leads DSDV in 11 and AODV leads DSDV in 7. At 50% flooded AODV and OLSR are level (about 57%).
- *Sustained phase:* 51–60% for all protocols; OLSR above AODV by 5.5–7 points (significant), about the same gap as without flooding.
- *Packets sent while a path existed:* 77–94% in the acute phase and 86–100% in the sustained phase (25% flooded, both failure models), so most of the loss after the onset is to devices that were flooded or cut off, not to routing.
- *Flood order vs uniform random* (same counts and times): no significant difference in delivery within 1 s in any of 87 comparisons (every protocol, window, onset, share, battery and traffic level; smallest Holm p = 0.15). On packets sent while a path existed, 2 of 78 comparisons reach p < 0.05 (DSDV at 25% and OLSR at 50% flooded did better under the flood order in the acute phase). In this square the real-data failure pattern is only moderately clustered and behaves much like random failures.
- *Batteries:* with the assumed mobile-device batteries and NS-3's radio currents, the last device runs flat 4, 7 and 14 real hours after the power cut when 25%, 50% and 100% of the battery is left for the radio (half of them after 2.4, 4–5 and 9 hours), at the same time under every protocol, so nothing is sent in the sustained phase. The battery arm cannot test the sustained-phase half of the premise. Do not compare whole-run PDR across battery settings: battery-limited runs show a higher PDR (85–97%) than unlimited ones (62–73% with 25% flooded) only because devices with flat batteries send nothing, so most of their packets come from before the power cut.
- *Propagation:* with the cited NLOS path-loss model no packet is delivered (184,731 sent, none received): 100 devices in the square are not a network at 62.8 m range. All the results above assume the 150 m unit disk.
