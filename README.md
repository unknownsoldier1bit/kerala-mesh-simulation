# Kerala mesh simulation

NS-3 simulations for a research paper comparing two mesh routing protocols, AODV (reactive) and OLSR (proactive), when infrastructure fails under conditions based on the 2018 Kerala floods.

## Layout

```
sim/diamond/diamond.cc   sanity sim: 4 nodes, two paths, the relay in use dies mid-run
sim/manet/manet.cc       main sim: AODV/OLSR/DSDV on a static mesh with scheduled node/link failures
experiments/             input generation, experiment grids, metrics, analysis (see its README)
results/                 experiment outputs, tables and figures (see its README)
docs/deliverables.md     the data and outputs the paper needs
STATUS.md                what has been run so far
scripts/setup.sh         finds or installs NS-3, links sim/ into NS-3, builds
scripts/run.sh           runs one sim, writes CSVs to results/
PREDICTIONS.md           your predictions, written before running
docs/ns3-defaults.md     NS-3 behaviour checked in the source code
data/sources.md          Kerala 2018 data: verified, partial, missing
CLAUDE.md                context for Claude sessions working in this repo
```

## Setup

```bash
scripts/setup.sh
```

On your Mac it finds `~/ns-allinone-3.47` and leaves its settings alone. On a machine without NS-3 (like a cloud session) it downloads NS-3.47 and builds only the modules this project needs.

## Run

```bash
scripts/run.sh diamond --protocol=aodv --run=1
scripts/run.sh diamond --protocol=olsr --run=1
```

Useful flags: `--deadline` (T, in seconds), `--killTime`, `--interval`, `--aodvHello=false`, `--olsrHello`, `--kill=B|D|relay`. Every run prints a summary and writes:

- `results/diamond-<protocol>-run<N>.csv`, one row per packet
- `results/diamond-summary.csv`, one row per run

For 10 runs: `for r in $(seq 1 10); do scripts/run.sh diamond --protocol=olsr --run=$r; done`

## Experiments

```bash
python3 experiments/run_experiment.py main    # or severity, load, energy, kerala, kerala100
python3 experiments/analyze.py
```

How each experiment is set up, every metric definition and the known limitations are in `experiments/README.md`.

## Before you run anything

Fill in `PREDICTIONS.md` first.
