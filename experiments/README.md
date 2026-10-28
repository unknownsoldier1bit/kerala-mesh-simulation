# Experiments: how they were run

This folder holds everything that turns the simulator (`sim/manet/manet.cc`) into the dataset requested in `docs/deliverables.md`. Every number in `results/` can be regenerated from the commands below.

- `gen.py` builds the inputs of a run: node positions, traffic and failure schedule.
- `kerala.py` builds the energy-depletion experiment and the Kerala-anchored failure experiment.
- `run_experiment.py` runs a whole experiment grid in parallel and computes the metrics for each run.
- `metrics.py` turns one run's raw output into the metrics (the definitions are in its docstring and below).
- `analyze.py` builds the tables, figures and statistical tests in `results/analysis/`.

## Reproducing

```bash
scripts/setup.sh                                   # NS-3.47 with AODV, OLSR, DSDV
pip install numpy pandas scipy matplotlib networkx
python3 experiments/run_experiment.py main         # also: severity, load, energy, kerala
python3 experiments/analyze.py
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
| Time without delivery | Per affected flow, time from the event until delivery resumes, or until the next event if it never does (`recovery_outage_mean_s`); and the longest gap between deliveries of each flow (`per_flow.csv`) |
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

- **AODV link-break detection.** `NeighborCacheHelper` (used at first to pre-fill ARP tables) creates entries that AODV's MAC lookup ignores, which silently disabled AODV's reaction to failed transmissions. A relay forwarding into a dead link then kept its route alive indefinitely. Both sims now pre-fill ARP with permanent entries. Details in `docs/ns3-defaults.md`.
- **Energy.** The state-based energy figure was compared with NS-3's own energy framework (`BasicEnergySource` + `WifiRadioEnergyModel`) in seed 1 of the main grid: `results/analysis/tables/check_energy_vs_ns3_model.csv`. They agree exactly except in the `recovery` scenario: NS-3's `WifiRadioEnergyModel` never leaves its OFF state once a radio has been switched off (`ChangeState` only updates the state while `m_currentState != OFF`), so it stops counting a radio that is switched back on. The state-based figure counts it. The energy and Kerala experiments use the state-based battery for this reason and for speed (the framework doubles run time). The comparison was run at 25 and 50 nodes only: at 100 nodes the framework's memory use grew to several gigabytes per run (each radio state change cancels and reschedules a far-future "battery empty" event, and cancelled events stay in the scheduler), and four such runs in parallel exhausted the machine's memory.
- **FlowMonitor.** Seed 1 of the main grid also ran NS-3's FlowMonitor: `check_tracker_vs_flowmonitor.csv`. Sent counts match except for packets the source refused because it had no route (FlowMonitor never sees them). Received counts match except where packets were delivered more than 10 s after sending: FlowMonitor declares those lost (`MaxPerHopDelay` = 10 s), while this project's tracker counts them as delivered, with their real delay.
- **Duplicates.** The destination counts each packet once. Extra copies are counted in `duplicate_receptions`.
- **Switching radios off.** NS-3.47 crashes if a radio is switched off while it is sending a broadcast frame (details in `docs/ns3-defaults.md`). A failing or battery-dead node therefore finishes the frame it is sending before its radio goes off (a few milliseconds at most). All runs with node failures were made with this rule.
- **Memory.** Running NS-3's energy framework on 100-node runs exhausted the machine's memory on the first attempt (four runs were killed). Those runs were redone without the framework; see section 6, Energy.

## 7. Deviations and limitations

Read these before writing the methods and discussion sections.

- **Predictions were not written first.** `PREDICTIONS.md` was empty when these runs were made (owner's decision, 27 Oct 2026, to save time). Any prediction written now is not a blind prediction.
- **DSDV** was included because the deliverables list requires it, although `CLAUDE.md` lists it among parked ideas. Its results are separate columns and can be dropped.
- **Unit-disk radio.** Full signal within 150 m, nothing beyond: no fading, no gradual loss, no obstacles except the deliberate link failures. This keeps "is there a route?" exact, but real links are less clear-cut.
- **Static nodes.** No mobility. Fine for people sheltering in place; it doesn't cover rescue boats or people moving.
- **Constant-rate traffic** in the main experiments. Real emergency traffic is burstier (used in the Kerala experiment only).
- **DSDV start-up in sparse networks.** The 60 s warm-up was not enough for DSDV in some sparse 25-node topologies (see `check_initial_convergence.csv`), so part of DSDV's loss there comes from tables that were still being built. That is real DSDV behaviour (slow convergence over many hops), but say so if you compare DSDV at 25 nodes; those runs can be excluded using the check table.
- **NS-3 default protocol parameters.** Tuning (for example a shorter OLSR HELLO interval) would change the results.
- **Energy model:** a fixed current per radio state, no sleep scheduling, and nothing but the Wi-Fi radio draws power. Idle listening dominates, which is a real property of always-on ad-hoc Wi-Fi but makes routing traffic a small share of energy use.
- **Time compression** in the Kerala experiment (see section 5).
- **Kerala parameters are assumptions** anchored to dates, not measurements: the flood curve shape, failure shares, spatial pattern, battery sizes and traffic.
- **Failure selection.** Targeted failures (the busiest relays and links) are a worst case; random failures (multi_fail, severity sweep) are a milder case. Real floods sit somewhere in between, and are spatially correlated (as in the Kerala experiment).
