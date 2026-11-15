# Run 1 diagnosis

Run 1 is `01f1f6f-06b10c13` and stays exactly as published: full arm 83.9% → 84.2% on held-out, H1, H4 and H5
FAIL. Nothing in this document changes it. This is why it came out that way.

**Rules this followed.** Everything is measured on the train split and `faults.json`. Held-out questions are used in
one place only, §5, where the graph is repaired *from the fault file* rather than from any answer — that measures a
property of the data, not of a tuned system, and no constant was chosen from it.

**Written by code, not by hand.** `uv run python -m trailmend.eval.diagnose` wrote
`evidence/anatomy.json`, `evidence/oracle.json` and `evidence/fault_recoverability.json`; the per-round numbers in §6
come from `evidence/changes.json` and `evidence/non_regression.json`, which run 1 already published. The round-5
graph is reached by replaying the full arm's own receipts onto a freshly loaded G0, so no judging and no new
randomness is involved. These three files carry their own `measured_on` and are deliberately **not** added to
`evidence/run_manifest.json`: that manifest is run 1's, and rebuilding it would rewrite run 1's published
digests for files whose content did not change.

---

## 1. Error anatomy, full arm, train split

Every train question that was not answered correctly, classified by what broke the path that should have carried the
gold answer. A question can have more than one cause; the first in the order *planted wrong edge, missing edge,
alias duplicate, conflated entity, tie, other* is the one counted, and the rest are kept in `also_applied`.

**Round 0** (`evidence/anatomy.json`):

| seed | train | correct | wrong | unreachable | planted wrong edge | missing edge | alias duplicate | conflated | tie | other |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 510 | 430 | 49 | 31 | 33 | 42 | 5 | 0 | 0 | 0 |
| 7 | 510 | 412 | 44 | 53 | 35 | 59 | 3 | 1 | 0 | 0 |
| 42 | 514 | 420 | 45 | 47 | 38 | 49 | 5 | 1 | 1 | 0 |

**After the last recorded round:**

| seed | correct | wrong | unreachable | planted wrong edge | missing edge | alias duplicate | conflated | tie | other |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 448 | 27 | 35 | 33 | 18 | 5 | 0 | 0 | 6 |
| 7 | 442 | 25 | 42 | 35 | 22 | 3 | 1 | 0 | 7 |
| 42 | 439 | 25 | 48 | 38 | 23 | 5 | 1 | 1 | 7 |

Three things move, and only three:

- **The planted-wrong-edge count does not move at all** — 33, 35, 38 at both ends. What moves is where the wrong
  edge sits: `wrong_edge_on_the_chosen_path` goes 28 → 0, 31 → 0, 33 → 0. The Mend quarantined every planted wrong
  edge it was walking, and each of those questions went from a wrong answer to a refusal. The question is still
  failing; it just fails politely now.
- **Missing-edge failures fall by about half** — 42 → 18, 59 → 22, 49 → 23. That is gap-fill, and it is the only
  cause the Mend actually repairs.
- **`other` appears from nothing** — 0 → 6, 0 → 7, 0 → 7. These are train questions with no planted fault anywhere
  near them that the Mend broke by itself.

## 2. Can a planted wrong edge ever be repaired? No.

`_swap_targets` in `src/trailmend/data/faults.py` **deletes** the true edge and inserts the wrong one in its place.
The deleted edge does not go into the gap-fill pool. Counted over all three seeds
(`evidence/fault_recoverability.json`):

| seed | planted wrong edges | true edge still in G0 | true edge in the gap-fill pool | true edge nowhere |
|---|---|---|---|---|
| 1 | 13 | 0 | 0 | **13** |
| 7 | 13 | 0 | 0 | **13** |
| 42 | 13 | 0 | 0 | **13** |

It is worse than "not in the graph". `documents.render` builds the corpus from G0's edges, so **every planted wrong
edge has a document asserting the wrong fact, and the true edge it replaced has no document anywhere.** The same
holds for the other two structural faults: the 7, 7 and 8 alert links moved to a duplicate service, and the 2, 2 and
3 edges rewritten onto a conflated person, are in G0 and the pool nowhere.

So for a planted wrong edge, reweight and quarantine can only ever turn **wrong into unreachable**. Not into
correct. §5 measures exactly what that is worth.

## 3. Blame concentration against `quarantine_min_blames = 3`

Train questions walking each planted wrong edge at round 0:

| seed | questions walking one | per-edge counts | edges no train question walks |
|---|---|---|---|
| 1 | 30 | 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 5 | 0 |
| 7 | 31 | 1, 1, 1, 1, 1, 2, 2, 2, 3, 3, 4, 5, 5 | 0 |
| 42 | 34 | 0, 1, 1, 2, 2, 3, 3, 3, 3, 3, 4, 4, 5 | 1 |

The rule needs 3 blames inside a 6-signal window, at a blame share ≥ 0.8, with ≤ 1 confirmation ever. Most planted
wrong edges are walked by one, two or three train questions, so they reach three blames by accumulating across
rounds rather than within one — which is what the run shows: quarantines fire in rounds 1, 2 and 3 (5, 8, 4 for seed
1) and then stop. One edge on seed 42 is walked by no train question at all and can never be blamed. The threshold
is not the thing holding the Mend back; §2 is.

## 4. Which mechanisms ran in the full arm

`MECHANISMS[FULL] = Mechanisms(reweight=True, quarantine=True, promote=True, gapfill=True)` — all four. The receipts
agree: **D5 gap-fill and D4 promotion both ran.**

| seed | reweight | quarantine | promote (D4) | gapfill (D5) |
|---|---|---|---|---|
| 1 | 2876 | 17 | 9 | 31 |
| 7 | 2869 | 16 | 5 | 35 |
| 42 | 2850 | 14 | 1 | 25 |

## 5. Oracle ceiling: what any repair could reach on this data

Perfect repairs taken straight from `faults.json`, each stage applied on top of the last, scored on held-out
(`evidence/oracle.json`). The first two rungs are the whole vocabulary this build has. The last two are repairs no
mechanism in this build can make, and the final rung is the truth graph itself.

| stage | seed 1 | seed 7 | seed 42 | mean change |
|---|---|---|---|---|
| G0, no repair | 85.3% | 82.4% | 83.9% | — |
| every planted wrong edge quarantined | **85.3%** | **82.4%** | **83.9%** | **+0.0** |
| … and every withheld edge ingested | 92.6% | 94.1% | 94.2% | **+9.8** |
| … and every duplicate service merged | 93.2% | 94.4% | 95.0% | +0.6 |
| … and every conflated person split | 93.2% | 94.7% | 95.0% | +0.1 |

**Perfect quarantine is worth exactly zero.** On seed 1 it turns 13 wrong answers into 13 refusals: wrong 27 → 14,
unreachable 23 → 36, accuracy unchanged to the digit. Same on the other two seeds.

**Every point of headroom on this data is in gap-fill**: +9.8 points on average for ingesting all 104, 105 and 106
withheld edges. The full arm ingested 31, 35 and 25 of them — a quarter to a third — and `gapfill_only` scored
+2.2 points against this +9.8 ceiling. The Mend captured about **4% of the headroom that exists** (+0.4 of +9.8).

The data can show learning. Run 1's mechanisms could not reach it.

## 6. Per round: what changed, what it fixed, what it broke

Applied changes, full arm (`evidence/changes.json`), and held-out fixes and breaks with the receipts traced to each
break (`evidence/non_regression.json`):

| seed | round | reweights | quarantines | ingests | promotes | newly fixed | newly broken | net | receipts blamed for the breaks |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 572 | 5 | 21 | 8 | 6 | 9 | -3 | 44, 43 confirm-only |
| 1 | 2 | 587 | 8 | 6 | 1 | 1 | 0 | +1 | — |
| 1 | 3 | 575 | 4 | 4 | 0 | 2 | 0 | +2 | — |
| 1 | 4 | 571 | 0 | 0 | 0 | 0 | 1 | -1 | 4, 4 confirm-only |
| 1 | 5 | 571 | 0 | 0 | 0 | 3 | 0 | +3 | — |
| 7 | 1 | 564 | 5 | 33 | 4 | 6 | 9 | -3 | 42, 40 confirm-only |
| 7 | 2 | 584 | 3 | 0 | 1 | 0 | 0 | +0 | — |
| 7 | 3 | 579 | 8 | 1 | 0 | 2 | 1 | +1 | 2, 0 confirm-only |
| 7 | 4 | 571 | 0 | 1 | 0 | 2 | 0 | +2 | — |
| 7 | 5 | 571 | 0 | 0 | 0 | 0 | 0 | +0 | — |
| 42 | 1 | 570 | 8 | 23 | 1 | 10 | 9 | +1 | 47, 42 confirm-only |
| 42 | 2 | 575 | 2 | 1 | 0 | 0 | 0 | +0 | — |
| 42 | 3 | 571 | 4 | 0 | 0 | 0 | 0 | +0 | — |
| 42 | 4 | 567 | 0 | 1 | 0 | 0 | 0 | +0 | — |
| 42 | 5 | 567 | 0 | 0 | 0 | 1 | 0 | +1 | — |

Net over five rounds: seed 1 +2 held-out answers, seed 7 +3, seed 42 +1.

Two things to see here.

**The breaks are caused by confirmations, not by blame.** Of the receipts on the old correct path of a newly broken
question in round 1, 43 of 44 on seed 1 carry only `confirm` signals; the pattern repeats on both other seeds. A
confirmed edge gets cheaper by `e^-0.35` each time, so a route confirmed by many questions keeps falling and
eventually undercuts a different question's correct route. Blame is barely involved.

**The cost field collapses.** Counting the last cost written to every edge the full arm touched:

| seed | edges touched | at the 0.05 floor by round 5 | below 0.2 |
|---|---|---|---|
| 1 | 616 | 194 (31%) | 551 (89%) |
| 7 | 611 | 177 (29%) | 533 (87%) |
| 42 | 603 | 197 (33%) | 534 (89%) |

Nine confirmations take an edge from 1.0 to the floor, and every correct path is confirmed every round. By round 4
almost nothing is left to distinguish one route from another: no edge is quarantined after round 3 on any seed,
rounds 4 and 5 ingest one edge between all three seeds, and the ~571 reweights a round are confirmations moving
costs that are already on the floor. That is why the curve is flat after round 3.

---

## What this diagnosis says

1. **The data makes three of its four fault classes unrepairable.** The true edge behind every planted wrong edge,
   every alias move and every conflation is in neither the graph nor the corpus, and the corpus corroborates the
   wrong version. Only the withheld edges can be repaired, and only by gap-fill.
2. **Quarantine cannot raise accuracy on this data, even if it were perfect.** Measured, not argued: +0.0 on every
   seed. It converts wrong answers into refusals. That is worth something to a product and nothing to the metric
   run 1 preregistered.
3. **Gap-fill is where the headroom is, and run 1 used a quarter of it.** +9.8 points available, +2.2 achieved by
   `gapfill_only`, +0.4 by the full arm.
4. **Confirmation, not blame, is what breaks previously-correct answers**, and the multiplicative cost rule drives
   89% of touched edges below 0.2 by round 5, after which the graph stops discriminating between routes at all.
5. **H1's test was the wrong shape.** It compared a per-seed delta against the *spread between seeds at round 0*.
   That spread measures how different three generated companies are; it is not the noise in the delta. The arms
   share seeds, splits and questions, so a paired test per question against the frozen arm is both available and far
   more sensitive.

## What it does not say

- It does not say the Mend is sound. Finding 4 is a real defect in the update rule, not a data problem.
- It does not say run 1 should be withdrawn. It is a correct measurement of a system on a dataset that could not
  show what the system was built to show, and it stays published as FAIL.
- It does not establish that the proposed run-2 changes will help. Nothing here was chosen by looking at held-out
  accuracy under any mechanism, and nothing may be, until run 2's hypotheses are written down and fixed.
