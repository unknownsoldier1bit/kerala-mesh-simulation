# Paper fix list

Started 2026-11-16. What stands between the draft and a strong paper, in the order we are fixing it.
How we work: Claude asks questions, Saksham gives the point, Claude may rephrase it (and says so), then the doc is updated.
New simulations are allowed; Saksham's prediction goes in `PREDICTIONS.md` before each one runs.

Working doc: https://docs.google.com/document/d/1jULbOBAzoe8FVNwMYo824ni0_Z7ThJIEu91CbIyw42k/edit

| # | Problem | Evidence | Needs | Status |
|---|---|---|---|---|
| 1 | Reasoning sections are empty: research question, related work, mechanism, discussion, conclusion | 25 highlighted placeholders in the doc | writing; filled in as 2-7 are settled | open |
| 2 | The stated contribution (Kerala failure model) gave a null result | Flood order vs random failures: 0 of 87 comparisons significant; the Chalakudy square is nearly flat, so the test is weak | an argument, or a study area where terrain shapes who floods | open |
| 3 | The flood does not cause OLSR's lead | OLSR ahead with no failures (99.9% vs 59.4% at 100 nodes); in the Kerala scenario flooding shrinks the gap from 24 points to 9-16 | writing | open |
| 4 | The headline gap is lost messages, not late ones | 100-node grid: AODV PDR 60.0%, 14,943 MAC link breaks per run with nothing failing, 18.65 control packets per node per second; the only runs that do not replay exactly on a second machine | a diagnosis (new runs) | open |
| 5 | The second half of the premise fails | OLSR sends the fewest control packets (0.49 vs 1.75 per node per second); battery life equal across protocols; all devices flat in 4-14 h | writing; battery and radio values are placeholders | open |
| 6 | Assumptions decide the results | T = 1 s is a placeholder; nothing delivered under the 3GPP path-loss model; 1 day = 30 s but routing timers are not compressed | decisions, possibly new runs | open |
| 7 | Too big | 17 tables, 11 figures, 3 protocols; DSDV decision pending | cutting | open |

What is strong: on Chalakudy AODV's PDR stays 97-98% while delivery within 1 s falls as the gap between bursts grows and route discoveries per burst rise from 1.6 to 3.0 (direct evidence for the mechanism in the premise); reproducibility; measured/derived/assumed labels.

## Log

- 2026-11-16: list written. First questions asked: deadline and venue, whether DSDV stays, and Saksham's explanation for AODV's losses in the 100-node grid (problem 4).
