# Deliverables (Re: Research Paper)

The data and outputs requested for the paper, copied from Saksham's instructions of 27 Oct 2026. `STATUS.md` in the repo root tracks which items are done.

## 1. Simulation configuration

Record these for every experiment, or once if they remain unchanged.

- NS-3 version
- Routing protocols tested: AODV, OLSR, DSDV, or others
- Network type and topology
- Total number of nodes
- Number of source, destination, relay and coordinator nodes
- Node coordinates or placement method
- Simulation area dimensions
- Wireless standard and channel configuration
- Transmission power, receiver sensitivity and communication range, if configured
- Propagation-loss and propagation-delay models
- Data rate and MAC-layer settings
- Packet size in bytes
- Traffic generation model and transport protocol
- Packet generation rate and traffic start/stop times
- Total simulation duration
- Random seed and run number
- Mobility model and node speed, if applicable

## 2. Disaster scenarios

Run each routing protocol under comparable scenarios.

- Baseline: no deliberately introduced failures
- Link failure: one or more communication links become unavailable
- Node failure: selected intermediate nodes become unavailable
- Multiple failures: several links or nodes fail
- Network partition: the network separates into disconnected components
- Recovery: connectivity is restored after a failure, where applicable

For each scenario record:

- Failure start time and end time
- Identity and location of affected nodes or links
- Number or percentage of links/nodes affected
- Whether a valid alternative route exists
- Whether failures are deterministic or randomly generated

For each scenario, document the assumptions connecting it to disaster-related communication disruption. Do not present hypothetical failures as historical measurements from Kerala.

## 3. Core performance metrics

Collect the following for every protocol × scenario × node-density configuration × random seed.

| Metric | Definition | Priority |
|---|---|---|
| Packet delivery ratio (PDR) | Packets received ÷ packets sent × 100. Record sent and received packet counts as well as the percentage. | Essential |
| End-to-end delay | Mean, median, standard deviation, and preferably the 95th percentile of packet delay, in milliseconds. | Essential |
| Throughput | Successfully received application data per unit time, in bits per second or kbps. State the measurement interval. | Essential |
| Routing overhead | Routing control packets and, where possible, control bytes. Also calculate control-packet overhead relative to delivered data, with the definition stated explicitly. | Essential |
| Packet loss | Packets lost, loss percentage and, if available, the reason for loss. | Essential |
| Recovery time | Time between a defined failure event and renewed successful packet delivery over an available route. | Essential |

## 4. Additional metrics that strengthen the paper

- Route discovery time
- Number of route discoveries
- Number of route errors
- Routing-table convergence time, where measurable
- Number of broken routes
- Successful transmissions during the recovery period
- Time spent without successful packet delivery
- Per-node energy consumption, if an energy model is implemented
- Network lifetime, if energy depletion is part of the research question
- Control traffic before, during and after failure

These additional metrics are useful only if the chosen NS-3 models support reliable measurement. Do not report unavailable metrics as zero.

## 5. Network density and robustness experiments

To make the comparison more substantial, collect results across different network sizes and disruption severities.

- Results for each chosen node count, such as 25, 50 and 100 nodes
- Results for each failure severity
- Results under different traffic loads
- Results with different random seeds
- Mean and standard deviation across repeated runs
- Number of repetitions for each configuration
- Any failed or incomplete simulation runs and the reasons

Keep all non-target variables consistent when comparing protocols. If you change node density, for example, document whether the simulation area stays constant.

## 6. Raw files to preserve

These allow results to be independently checked and analysed.

- NS-3 simulation source code (.cc files and any supporting files)
- Exact run commands and configuration arguments
- Standard output and error logs
- FlowMonitor XML files, if used
- Packet capture files (.pcap), if enabled
- Routing and topology traces
- Failure-event logs with timestamps
- CSV files containing per-run measurements
- A README documenting how the experiments were executed

Do not send only screenshots of graphs if the underlying CSV, XML or trace files are available. Raw output allows us to verify calculations and generate publication-quality figures.

## 7. Summary table for every experimental run

Each row represents one protocol, scenario, configuration and random seed.

| Field | Example format |
|---|---|
| Protocol | AODV |
| Scenario | Link failure |
| Node count | 50 |
| Seed / run ID | 1 |
| Failure time | 100 s |
| Failure severity | Defined percentage or number of failed links |
| Packets sent | Integer |
| Packets received | Integer |
| PDR | % |
| Mean delay | ms |
| 95th-percentile delay | ms |
| Throughput | kbps |
| Control packets | Integer |
| Control bytes | Bytes |
| Packet loss | Count / % |
| Recovery time | s or unavailable |
| Energy consumed | Joules, if measured |

The example values and formats above describe the data structure, not experimental findings.

## 8. Outputs needed for the final paper

- Comparison of PDR across routing protocols and scenarios
- Comparison of end-to-end delay
- Comparison of throughput
- Comparison of routing overhead
- Recovery-time comparison following failures
- Performance versus node density
- Performance versus failure severity
- Variability across random seeds, including error bars
- Statistical tests where justified by the design and data
- Discussion of trade-offs and practical limitations
- Reproducibility details and any deviations from the planned methodology

## 9. Minimum versus ideal dataset

**Minimum viable dataset**

- AODV, OLSR and DSDV under a baseline and at least one failure scenario
- PDR, mean delay, throughput and routing overhead
- Defined failure and recovery events
- Repeated runs with documented seeds
- Raw output files and exact configurations

**Stronger research dataset**

Everything above, plus multiple network sizes, several failure severities, node and link failures, network partitions, recovery experiments, delay distributions, control-byte overhead, statistical analysis and reproducible source code.
