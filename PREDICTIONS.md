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

### What actually happened (checked 16 Nov 2026, from the stored runs of the main experiment)

Where the lost messages died, AODV, 100 nodes, baseline, mean of 10 runs (3,677 lost of 9,200 sent):

| Where | Share of lost messages | Fits idea |
|---|---|---|
| At the radio, after the retry limit: the next device never acknowledged | 43.9% | 2 |
| At a relay that had no route any more (the route had just been cancelled) | 38.9% | 2 |
| Expired in a radio queue after waiting 0.5 s for a free channel | 16.3% | 3 |
| Dropped while waiting for a route | 0.6% | 1 |
| Radio queue full | 0% | 3 |

Route discoveries: 4,324 per run, 94% of them completed, median 77.6 ms. With 10 flows in a network where nothing fails, about 10 would be enough. Each run also has 14,943 MAC link-break reports and 190,820 forwarded route requests.

- Idea 1: correctly ruled out. Almost nothing is lost while waiting for a route, and discovery is fast.
- Idea 2: the main cause, 83% of the losses. Routes do get set up, and then the data cannot use them.
- Idea 3: a smaller part, 16%, and only as waiting too long, never as a full queue.

Not answered by this check: why the data frames go unacknowledged when no device has failed. Tests 1 and 2 below are for that.

## Diagnosis 2: what makes the links look broken (16 Nov 2026)

Two new experiments, both the 100-node baseline with the same traffic, 10 seeds. Results stay unopened until the predictions are written here.

| Test | The one thing changed | Runs |
|---|---|---|
| 1 `diag_nofeedback100` | AODV ignores the radio's "no acknowledgement" reports (`--aodvMacFeedback=false`), so it never cancels a route it is using. Same networks and flows as the main experiment. Diagnostic only: in ns-3 this AODV also cannot notice a dead next hop while it sends to it, which does not matter when nothing fails. | AODV, 10 |
| 2 `diag_sparse100` | The same 100 devices in a 1,000 m square instead of 500 m: 6.3 neighbours per device instead of 22.4. Side effect: paths get longer (network diameter 17.8 hops instead of 5.0). | AODV and OLSR, 20 |

Saksham's predictions:

| Question | Prediction | Why |
|---|---|---|
| Test 1: AODV's delivery (60% now) | Goes down | "its gonna send it regardless of any response from the other side" |
| Test 2: AODV's delivery (60% now) | Improves | "that same beacon error wont occur" |
| Test 2: OLSR's delivery (99.9% now) | Stays at 99.9% | "the foundation was good in a crowded setting it shd retain itself in an I would say better setting" |
| Test 2: OLSR's battery use | Higher drain | "because its spread out more" |

Saksham's full answer, written before the results were opened:

> for 1 I think it will go down cuz its gonna send it regardless of any response from the other side.
>
> I think overall for 2, AODV improved because that same beacon error wont occur right, for OLSR, higher battery drain because its spread out more but it shd remain at the 99.9 because the foundation was good in a crowded setting it shd retain itself in an I would say better setting

### What actually happened (fill in after the runs are opened)


