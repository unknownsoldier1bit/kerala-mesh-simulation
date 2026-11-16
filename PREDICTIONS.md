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

## Diagnosis 1: why AODV loses 40% of messages with 100 nodes and no failures (16 Nov 2026)

Setup: main experiment, baseline, 100 nodes in a 500 m square, 10 flows of 4 packets/s, nothing fails. AODV delivers 60%, OLSR 99.9%. Known before guessing: AODV sends 18.65 routing packets per node per second (OLSR 0.75) and its MAC reports 14,943 link breaks per run.

Saksham's ideas, in his words, written before the drop reasons were looked at:

> I think aodv might be dropping because theres a delay. it computes on demand, keeps quiet for a while then gets back. That delay is causing it to send alot of stuff in advance, but it isnt that long so thats not it. Another reason could be that one stray packet goes thru and accidentally broadcasts or broadcasts in a very specfic condition which others cant recreate causing the beacon signal or the path signal packet to reach but the others miss. another could be overflow who knows

The same three ideas as testable statements (rephrased by Claude, each with what the data should show if it is right):

| # | Idea | If it is right, the data shows |
|---|---|---|
| 1 | Messages pile up while AODV waits for a route. Saksham rules this out: the wait is too short. | Most lost messages are dropped while waiting for a route (waiting queue full or timed out); discoveries are slow |
| 2 | A routing packet gets through once, under conditions the data cannot repeat, so a route is set up that the data then cannot use | Discoveries complete, but the data dies on the route: lost at the MAC after the retry limit; routes break soon after they form |
| 3 | Overflow | Most lost messages are dropped from full or expired queues |

### What actually happened (fill in after the check)

