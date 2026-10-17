# Kerala mesh simulation

Context for Claude sessions in this repo. The owner, Saksham, works from Claude Code on the web and on his Mac.

## The project

- A research paper by Saksham (12th grade), co-authored with a classmate: AODV vs OLSR in NS-3 under a node-failure model based on the 2018 Kerala floods. Simulation only; hardware was dropped.
- The contribution is the time-evolving, Kerala-anchored failure model, not the protocol comparison (plain AODV-vs-OLSR comparisons are saturated).
- Primary metric: fraction of messages delivered within a fixed deadline T. T is a placeholder until it's set from Kerala data.
- Premise, in Saksham's words (don't rewrite it):
  > During the acute phase of a flood such as Kerala 2018, OLSR delivers a higher fraction of messages within a fixed deadline than AODV. OLSR keeps routes computed in advance, so a message can leave immediately. AODV has to discover a route first, and again after every link break. With frequent breaks and short bursts of traffic, that discovery delay uses up much of the deadline. The advantage has a cost: OLSR's periodic control traffic drains batteries faster. So over the sustained phase, as nodes run out of power, AODV should close the gap or overtake it.

## Order of work

1. Premise — done.
2. Mechanism paragraph — Saksham writes it himself.
3. Diamond sanity sim — `sim/diamond`. His predictions go in `PREDICTIONS.md` first.
4. Energy model (`BasicEnergySource` + `WifiRadioEnergyModel`).
5. Kerala failure model, with a connectivity control and a uniform-random-failure baseline.
6. Write the paper.

## How to work with him

- Teach as you go. He's learning networking and NS-3, and must be able to explain everything to his teacher.
- He writes the reasoning (premise, mechanism paragraph, predictions). Critique it; don't write it for him.
- Guess-then-check: if `PREDICTIONS.md` has no predictions for an experiment, ask for them before running it or showing results.
- Keep replies short and direct.
- Don't pull parked ideas into the paper: ESP32 or other hardware, federated learning, LoRa, a hybrid AODV/OLSR protocol, Punjab floods, other protocols (DSDV, DSR, B.A.T.M.A.N.).
- Call it "mesh nodes" or "mobile devices", not "phones": stock phones can't do ad-hoc WiFi routing.
- Flag anything unverified before he cites it. Never cite the unsourced figures listed in `data/sources.md`.

## Running things

- NS-3 isn't preinstalled in cloud sessions. Run `scripts/setup.sh` first. It downloads ns-allinone-3.47 from nsnam.org and builds only the modules this project needs, which takes several minutes. If the download is blocked, the environment's network access must allow nsnam.org.
- `scripts/run.sh diamond --protocol=aodv --run=1` writes CSVs to `results/` (gitignored).
- Each simulation lives in `sim/<name>/` with exactly one `main()`. `setup.sh` links each folder into NS-3's `scratch/`.
- Verified NS-3 behaviour is in `docs/ns3-defaults.md`. Check the NS-3 source before stating any default.
- Keep commits small. Don't commit `results/` unless he asks.
