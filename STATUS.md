# Status of the overnight experiment run

Updated on every push. The full list of requested outputs is in `docs/deliverables.md`.

| Step | State |
|---|---|
| Save deliverables list | done |
| Build simulator for all scenarios (`sim/manet`) | done |
| Main grid: 3 protocols × 6 scenarios × 25/50/100 nodes × seeds | running |
| Failure-severity sweep | not started |
| Traffic-load sweep | not started |
| Energy and network lifetime | code done, not run yet |
| Kerala time-evolving failure model + baselines | code done, not run yet |
| Analysis: tables, figures, statistics | code done (`experiments/analyze.py`) |
| README for the experiments | done (`experiments/README.md`) |

## Found along the way

- AODV's link-break detection was silently disabled by `NeighborCacheHelper` in both sims. Fixed; see `docs/ns3-defaults.md`. Re-run any diamond AODV results made before 27 Oct.
- NS-3's `WifiRadioEnergyModel` stops counting a radio that is switched back on after being switched off. The experiments use their own state-based energy accounting, checked against NS-3's model.
