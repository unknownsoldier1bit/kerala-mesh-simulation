# Predictions

Write your predictions **before** running an experiment, and commit them. Then run it, fill in what actually happened, and explain any difference. The point is to find out where your mental model is wrong.

## Experiment 1: diamond sanity sim

Setup: A sends 10 packets/s to C from t = 15 s. At t = 30 s the relay A is using (B or D) is switched off. Deadline T = 1 s (placeholder). Defaults: AODV with hellos, OLSR HELLO every 2 s.

| Question | AODV prediction | OLSR prediction | Why |
|---|---|---|---|
| Route recovery time after the relay dies (s) | | | |
| Packets lost around the failure | | | |
| % delivered within T in the 10 s after the failure | | | |
| Routing control packets per node per second | | | |

What result would make you doubt the acute-phase half of your premise?

>

What do you expect with `--aodvHello=false`, and why?

>

### What actually happened (fill in after running)

| Measure | AODV | OLSR |
|---|---|---|
| Route recovery time (s) | | |
| Packets lost | | |
| % delivered within T after the failure | | |
| Control packets per node per second | | |

Where were you wrong, and why?

>
