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

### What actually happened

Test 1, opened 16 Nov 2026 after the predictions above were committed (10 runs, same networks and flows as the main experiment; mean of 10 seeds):

| Measure | AODV, main | AODV ignoring "no acknowledgement" reports | OLSR, main |
|---|---|---|---|
| Delivered (PDR) | 60.0% | 87.3% | 99.95% |
| Delivered within 1 s | 59.4% | 87.2% (95% CI ± 0.7) | 99.95% |
| Route discoveries per run | 4,324 | 2,508 | none |
| Routing packets per node per second | 18.65 | 8.99 | 0.75 |
| Frames given up after the retry limit | 14,943 | 7,454 | 2.4 |
| Lost at a relay with no route | 1,429 | 169 | 0 |
| Lost at the radio after the retry limit | 1,615 | 925 | 2.4 |
| Lost waiting over 0.5 s for the channel | 600 | 70 | 0 |

Delivery rose in every seed (median +28 points, Wilcoxon p = 0.002), the opposite of the prediction, and stayed below OLSR in every seed (median 12.6 points lower, p = 0.002). AODV still ran 2,508 discoveries per run with the reports ignored: it also drops a neighbour after missed HELLOs, and HELLOs are broadcasts that collisions can destroy.

Test 2, opened 16 Nov 2026 (20 runs; 100 devices in a 1,000 m square, 6.3 neighbours each, mean of 10 seeds):

| Measure | AODV, 500 m | AODV, 1,000 m | OLSR, 500 m | OLSR, 1,000 m |
|---|---|---|---|---|
| Delivered (PDR) | 60.0% | 99.8% | 99.95% | 99.6% |
| Delivered within 1 s | 59.4% | 99.5% (95% CI ± 0.3) | 99.95% | 99.6% (± 0.5) |
| Mean hops of delivered packets | 3.5 | 7.2 | 2.7 | 6.8 |
| Route discoveries per run | 4,324 | 77 | none | none |
| Frames given up after the retry limit | 14,943 | 3.4 | 2.4 | 1.1 |
| Routing packets per node per second | 18.65 | 1.19 | 0.75 | 0.97 |
| Energy used per device in the 300 s run | 251.8 J | 246.3 J | 247.8 J | 246.8 J |

| Prediction | Outcome |
|---|---|
| AODV improves | Right: 59.4% to 99.5% within 1 s (Mann-Whitney p = 0.0002) |
| OLSR stays at 99.9% | Right: 99.6%, no significant change (p = 0.32) |
| OLSR drains more battery when spread out | Not seen: 247.8 J to 246.8 J per device, no real change |

In the 1,000 m square AODV and OLSR do not differ (median difference 0.1 points within 1 s, Wilcoxon p = 0.48), although paths are twice as long. So the 40-point gap of the main experiment's "100 nodes" comes from crowding (22.4 neighbours per device), not from the number of devices.

Where were you wrong, and why? (Saksham)

Asked: if sending on the same route anyway works better than cancelling it, what does that say about the "broken" links, and why would cancelling a route make things worse for everyone nearby?

> so it was accidentally ruling out the good paths over one wrong run?

Reworded by Claude (first half of the answer): the links were never broken. A frame went unacknowledged because the air was crowded, AODV took that false alarm for a dead link, and it cancelled a route that worked. 
Asked next: each cancelled route starts a search that about 44 devices re-broadcast; what does that do to the frames nearby devices are sending, and what happens next?

> I remember you saying something about this, like the stuff doesnt have a way to go or something wrong with the line, so when they send data they dont get a response back.

The two answers joined and reworded by Claude, as used in the paper (Section V-A): the links were never broken. In a crowded network a data frame can go unacknowledged because other transmissions garble it. AODV takes the missing acknowledgement for a dead link and cancels a route that worked. The search for a new route is a broadcast that about 44 nodes repeat, which crowds the air further, so more frames nearby go unacknowledged and more working routes are cancelled. The last step, that this closes into a loop, was added by Claude from the two answers; Saksham to confirm he can explain it.




## Diagnosis 3: why flooding shrinks AODV's gap in the crowded Kerala scenario (16 Nov 2026)

Known before guessing: in the Kerala-anchored scenario with 100 devices in the 500 m square, AODV is 24 points behind OLSR in the acute phase without flooding, and 9-16 points behind when the flood removes 27-50% of the devices.

Saksham's explanation, written before the stored runs were checked for it:

> because the crowd would decrease, causing the data frames that had previously gona un-acknowledged to be acknowledged.

As a testable statement (Claude): if this is right, the flooded runs show fewer frames given up after the retry limit and fewer route discoveries than the no-flood runs, and the more devices are removed, the fewer.

### What actually happened (checked 16 Nov 2026, from the stored `kerala100` runs; acute phase, mean of 10 seeds)

| Scenario | Devices flooded by the end | AODV frames given up after the retry limit | AODV route discoveries | AODV within 1 s, all packets | OLSR within 1 s, all packets | AODV, packets that had a path | OLSR, packets that had a path |
|---|---|---|---|---|---|---|---|
| No flood | 0 | 4,049 | 1,568 | 76.0% | 100.0% | 76.0% | 100.0% |
| Kerala-anchored 27% | 27 | 2,950 | 1,263 | 65.4% | 81.1% | 80.2% | 99.5% |
| Random 27% | 27 | 2,661 | 1,260 | 71.0% | 84.6% | 82.6% | 98.3% |
| Kerala-anchored 50% | 50 | 2,126 | 1,108 | 60.5% | 73.3% | 81.6% | 99.0% |
| Random 50% | 50 | 1,861 | 919 | 61.7% | 70.2% | 82.9% | 94.5% |

- The explanation holds. Frames given up and route discoveries are lower than without flooding in every seed of every flooded scenario (Wilcoxon p = 0.002), and lower still when 50% of devices are removed. Per 100 packets sent the retry-limit drops also fall (531 without flooding, 340-461 with).
- It is not the whole reason the gap narrows from 24 points to 8.5-15.7. On packets that had a path, AODV gains 4-7 points (the effect above), but OLSR also loses 0.5-5.5 points. And packets with no path are lost by both protocols, which pulls the two overall figures together.
- Where OLSR's lost packets died in the flooded acute phase, per run: 79-114 had no route at the source, 12-36 were sent to a next hop that never acknowledged, 2-8 ran out of hops, 3-6 found no route at a relay.

