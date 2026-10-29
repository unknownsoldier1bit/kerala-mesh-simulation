# Results

Raw and processed output of the experiments described in `experiments/README.md`. Everything here can be regenerated with `experiments/run_experiment.py` and `experiments/analyze.py`.

## Layout

```
results/
  analysis/
    FINDINGS.md                 digest: mean ± 95% CI per configuration, significant paired differences
    figures/*.png, *.pdf        all figures (PDF for the paper, PNG for viewing)
    tables/
      summary_table_all_runs.csv    one row per run, in the format of docs/deliverables.md §7
      summary_table_<exp>.csv       the same, per experiment
      <exp>_by_config.csv           mean, std, n and 95% CI of every metric per configuration
      <exp>_stats_tests.csv         Friedman + pairwise Wilcoxon (Holm) tests, paired by seed
      scenario_properties.csv       what failed in each scenario, routes left, network pieces
      check_energy_vs_ns3_model.csv     energy accounting vs NS-3's energy framework
      check_tracker_vs_flowmonitor.csv  packet tracker vs NS-3 FlowMonitor
      failed_runs_all.csv           runs that crashed or timed out, with the reason
  <experiment>/                 main, severity, load, energy, kerala, kerala100
    summary.csv                 one row per run, every metric (column definitions: experiments/README.md §3)
    per_flow.csv                one row per flow per run
    recovery.csv                one row per (failure event, affected flow) per run
    timeseries.csv              10 s bins over time (energy and Kerala experiments)
    commands.txt                the exact command of every run
    failed_runs.csv
    inputs/n<N>_s<seed>/
      topology.csv              node positions (m)
      topology_info.json        links, mean degree, diameter, placement draws
      flows_*.csv               traffic: one row per sending period of each flow
      events_<scenario>.csv     failure schedule fed to the simulator
      scenario_<scenario>.json  failed nodes/links with coordinates, %, routes left per flow, assumption
      battery*.csv, elevation.csv, kerala_assumptions.json   (energy and Kerala experiments)
    runs/<run_id>/              run_id = <protocol>_<scenario>_n<nodes>_f<flows>_s<seed>
      command.txt, run_config.json   exact command and every setting
      stdout.log, stderr.log
      packets.csv.gz            every data packet: flow, seq, send/receive time, relay path, last drop event
      control.csv.gz            routing control packets/bytes per second, by message type; MAC link breaks
      events.csv                failures, restores and battery deaths as they happened (timestamps)
      energy.csv                per node: energy used, time in each radio state, battery death time
      routes.csv.gz             OLSR/DSDV: routing-table validity every second
      discoveries.csv.gz        AODV: every route discovery with start and end time
      rtables-<t>s.txt.gz       every node's routing table at time t (seed 1 of the main grid)
      flowmon.xml.gz            NS-3 FlowMonitor output (seed 1 of the main grid)
      summary.json, per_flow.csv, recovery.csv, timeseries.csv   metrics of this run
      stats.csv                 run counters (refused sends, duplicates, wall-clock time)
```

Drop codes in `packets.csv.gz` (`drop_code`): 0 none recorded, 1 no route at the source, 11–17 IPv4 drop reasons (12 no route, 15 route error, 11 TTL expired), 20–23 MAC drops (22 retry limit reached). See `DROP_NAMES` in `experiments/metrics.py`.

Packet capture (.pcap) was not enabled: for 100 nodes over 300 s it would be gigabytes, and the per-packet log above records the same delivery information.
