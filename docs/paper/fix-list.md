# Paper fix list

Started 2026-11-16. What stands between the draft and a strong paper, in the order we are fixing it.
How we work: Claude asks questions, Saksham gives the point, Claude may rephrase it (and says so), then the doc is updated.
New simulations are allowed; Saksham's prediction goes in `PREDICTIONS.md` before each one runs.

Working doc: https://docs.google.com/document/d/1jULbOBAzoe8FVNwMYo824ni0_Z7ThJIEu91CbIyw42k/edit

| # | Problem | Evidence | Needs | Status |
|---|---|---|---|---|
| 1 | Reasoning sections are empty: research question, related work, mechanism, discussion, conclusion | 25 highlighted placeholders in the doc | writing; filled in as 2-7 are settled | open |
| 2 | The stated contribution (Kerala failure model) gave a null result | Flood order vs random failures: 0 of 87 comparisons significant; the Chalakudy square is nearly flat, so the test is weak | an argument, or a study area where terrain shapes who floods | open |
| 3 | The flood does not cause OLSR's lead | OLSR ahead with no failures (99.9% vs 59.4% at 100 nodes); in the Kerala scenario flooding shrinks the gap from 24 points to 9-16 | writing | in progress: Saksham's first point (less crowding, fewer false alarms) checked and in the doc (Section V-D) with the two other reasons; waiting for his explanation of why OLSR loses packets that still had a path |
| 4 | The headline gap is lost messages, not late ones | 100-node grid: AODV PDR 60.0%, 14,943 MAC link breaks per run with nothing failing, 18.65 control packets per node per second; the only runs that do not replay exactly on a second machine | a diagnosis (new runs) | done 16 Nov: diagnosed, written into the paper (Section V-A, Table XVIII, abstract, Methods A and C, Limitations). Open: what the main experiment becomes now that its "100 nodes" means "crowded" (see problem 3) |
| 5 | The second half of the premise fails | OLSR sends the fewest control packets (0.49 vs 1.75 per node per second); battery life equal across protocols; all devices flat in 4-14 h | writing; battery and radio values are placeholders | open |
| 6 | Assumptions decide the results | T = 1 s is a placeholder; nothing delivered under the 3GPP path-loss model; 1 day = 30 s but routing timers are not compressed | decisions, possibly new runs | open |
| 7 | Too big | 18 tables, 11 figures | cutting | DSDV removed from the paper on 25 Nov (its runs stay in the repo); the rest of the cutting is open |

What is strong: on Chalakudy AODV's PDR stays 97-98% while delivery within 1 s falls as the gap between bursts grows and route discoveries per burst rise from 1.6 to 3.0 (direct evidence for the mechanism in the premise); reproducibility; measured/derived/assumed labels.

## Log

- 2026-11-16: list written. First questions asked: deadline and venue, whether DSDV stays, and Saksham's explanation for AODV's losses in the 100-node grid (problem 4).
- 2026-11-16: Saksham's answers. Deadline: ignore it and do the best version; he will say when to wrap up. DSDV: drop. Problem 4: his three ideas recorded in `PREDICTIONS.md` before the check; the stored runs show 83% of AODV's losses at 100 nodes fit his second idea (routes get set up, then the data cannot use them). Two diagnostic experiments launched (`diag_nofeedback100`, `diag_sparse100`), unopened until he predicts. New switch `--aodvMacFeedback` in `sim/manet/manet.cc`, checked on a 25-node relay failure (with it off, AODV keeps sending into the dead link: 4,392 retry-limit drops against 7).
- Design flaw found on the way: the main experiment keeps the 500 m square for 25, 50 and 100 nodes, so node count and density change together: 5.2, 10.5 and 22.4 neighbours per device on average (from `topology_info.json`). "100 nodes" there means "400 devices per km2".
- 2026-11-16: both diagnostic tests opened after Saksham's predictions were committed (`PREDICTIONS.md`, Diagnosis 2). Test 1: AODV ignoring MAC reports delivers 87.2% within 1 s (59.4% normally, OLSR 99.95%). Test 2: in a 1,000 m square AODV delivers 99.5% and OLSR 99.6%, no significant difference. So the 100-node gap is a crowding effect (22.4 neighbours per device) driven by AODV cancelling working routes after collisions. Summary tables: `docs/paper/tables/diag100.csv`, `diag100_tests.csv` (from `experiments/analyze_diag.py`). Raw runs of the two tests are not committed (waiting for Saksham's go-ahead).
- 2026-11-16: problem 4 written into the generator and the doc. The doc was patched in place with the new `docs/paper/patch_doc.py` (diffs two generator versions and emits one small update) and checked against the generator afterwards: 170 paragraphs and 18 tables identical. Table XVIII sits in a new Appendix D for now; tables get renumbered at the rebuild when the paper is cut (problem 7). Known to exist in the literature and to be cited from sources Saksham has opened: broadcast storms and false link failures in 802.11 ad hoc networks (not yet searched or verified).
- 2026-11-16: Saksham asked for every run to be saved so work can resume after a limit. From now on the raw runs of each new experiment are committed (`results/<experiment>/`) as soon as it finishes.
- 2026-11-25: everything discussed so far put into the doc, patched in place (no rebuild):
  - DSDV removed: text, tables, figures, references. Analysis rerun with AODV and OLSR only (`ANALYSIS_PROTOCOLS=aodv,olsr`, outputs in `results/analysis_paper/` and `results/analysis_chalakudy_paper/`; numbers equal the full analysis up to floating-point noise from newer pandas/NumPy, recorded in `VERSIONS.txt`). Every p value in the text rechecked: without DSDV there is one protocol pair per configuration, so p values are the Wilcoxon p (smallest 0.002) instead of Holm over three pairs (smallest 0.0059). Newly significant and now reported: at 50 nodes OLSR ahead in the baseline by 0.7 points (p = 0.004) and AODV ahead under node failure by 0.7 (p = 0.049); Kerala 50 nodes sustained, no flooding, OLSR ahead by 1.0 (p = 0.027); Chalakudy 25% flooded, flood order, OLSR ahead by 4.3 (p = 0.037), so OLSR is ahead in 5 of the 12 flooded configurations instead of 4. Flood order vs random: 0 of 32 comparisons significant on all packets, 2 of 32 on packets with a path (both favour the flood order).
  - Problem 3: Saksham's point and the check (`experiments/analyze_diag.py`, Kerala part) written into Section V-D, with a placeholder for his answer on OLSR.
  - Diagnosis table moved next to its text (Table VIII); table and figure references now resolved by the generator.
  - Related-work placeholder: the crowding effect is probably known (broadcast storm, false link failure); cite it.
  - Fixed: abstract, quote, captions and references justified; table captions centred; abstract bold as intended; Fig. 9's overlapping axis labels.
  - Checked afterwards: text, 18 tables and 11 figures identical to the generator; all 24 highlights and 7 links present; PDF export looked at page by page (15 pages). Cosmetic: Fig. 10's caption runs onto the next page.
  - New tool `docs/paper/patch_doc.py`: compares the live doc with the generator and sends only the differences.
