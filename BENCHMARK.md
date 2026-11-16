# TrailMend benchmark

Every experiment TrailMend ran, the hypotheses fixed before each one, and the verdicts as measured, failures
included. Back to the [README](README.md) · How to check all of this yourself: [JUDGING.md](JUDGING.md).

**Nothing in this file is typed by hand.** The paragraph and every table between the markers are written by
`uv run python -m trailmend.eval.report` from the files in [`evidence/`](evidence/). Each evidence file is listed at
the bottom with its sha256, and [`evidence/benchmark.json`](evidence/benchmark.json) records which files each sentence
of the paragraph was read from. The evaluation data is **generated** (company graphs) or **public** (MetaQA); no
customer data has been measured.

## Contents

- [The benchmark in one paragraph](#the-benchmark-in-one-paragraph)
- [How the experiments are designed](#how-the-experiments-are-designed)
- [All results](#all-results): run 2, the clean replication, MetaQA, unweighted search, run 3, run 4, run 1 and the evidence files
- [Why run 1 failed and what run 2 changed](#why-run-1-failed-and-what-run-2-changed)
- [Limitations](#limitations)
- [Reproduce it](#reproduce-it)

## The benchmark in one paragraph

<!-- benchmark:start -->
I tested TrailMend on 3 generated company graphs (1,165 nodes, 124 to 126 planted faults each) and on MetaQA, a public movie knowledge graph (134,741 triples, 360 held-out questions per seed, 3 seeds, half the triples withheld). Run 2's shared graph carried stray edges from earlier runs, so it was replicated on an emptied HydraDB (run 3dbcdf3-580ae8dc): the full loop went from 77.0% to 84.6% against 77.0% for the frozen graph, which reproduced the gain; run 2's own numbers below stay as recorded. After 5 rounds of learning from its own answers, held-out accuracy on the company graphs rose from 77.9% to 85.7% (p < 0.001 on a paired test, every seed), and held-out Hits@1 on MetaQA rose from 55.3% to 71.5% (p < 0.001 on a paired test, every seed). It captured 69% of the gain that perfect repairs would give on the company graphs and 38% on MetaQA. Random reweighting, matched to its own targeted plan's number and size of cost changes each round, ends at 76.6% on the company graphs against 77.9% for the untouched graph, and at 55.6% on MetaQA against 55.3% for the untouched graph, and random reweighting did not significantly beat the untouched graph on any seed. The random arm reads no new documents; gap-fill alone, with no reweighting, reaches 82.9% on the company graphs. A plain document store over the same corpus stays flat at 28.3% (15.5% on MetaQA) because it has no links for the loop to repair, and on the clean replication, the same loop with unweighted search goes from 83.3% to 89.9%, 5.3 points above the loop that searches on cost on the same graph (significantly higher on 3 of 3 seeds, significantly lower on 0). Wrong answers fell 30% on the company graphs and fell 9% on MetaQA, and 1,386 of 1,393 held-out questions that were right at the start were still right at the end, with every break along the way traced to a receipt. The graph did get bigger, but only by reading: the company graphs gained 158 links (3.2%), each from a withheld document and each under a receipt, and MetaQA read back 5,684 withheld triples. Reweighting and quarantine also change the graph; these results do not isolate their gain from gap-fill.
<!-- benchmark:end -->

## How the experiments are designed

| | |
|---|---|
| **Question** | Does a graph that learns only from whether its own answers were right get more accurate on questions it never saw? |
| **Data** | 3 generated company graphs (seeds 1, 7, 42; ~1,165 nodes, ~125 planted faults each, with the truth behind every fault known) and MetaQA, a public movie knowledge graph with half its triples withheld. |
| **Split** | Training questions are judged and fed to the Mend; held-out questions are only scored. Splits are made in one place (`src/trailmend/eval/splits.py`), and the round runner only accepts `TrainQuestion`, so a held-out question reaching the Mend is a type error. |
| **Metric** | Held-out exact-match accuracy (company graphs) and Hits@1 (MetaQA), both fixed before the runs. No LLM scores anything. |
| **Baselines** | The frozen graph (no learning); random reweighting and random quarantine that make the same number and size of changes as the real Mend each round; a BM25 document store over the same corpus, tuned in its own favour. |
| **Statistics** | Every held-out question is paired against the frozen graph on the same seed (two-sided exact McNemar). |
| **Preregistration** | Hypotheses and constants are written into [docs/PRD.md](docs/PRD.md) and [DECISIONS.md](DECISIONS.md) before each run is built. Run ids are `<commit>-<config digest>`, so a changed constant changes the id. Failed hypotheses stay published. |

## All results

<!-- numbers:start -->
### Run 2, on dataset v2

**Replicated on a clean graph.** Run 2's shared graph carried stray edges from earlier runs, so it was replicated on an emptied HydraDB (run 3dbcdf3-580ae8dc): the full loop went from 77.0% to 84.6% against 77.0% for the frozen graph, which reproduced the gain; run 2's own numbers below stay as recorded. The replication and its comparison with this run are in [the next section](#clean-replication-of-run-2).

| arm | round 0 | round 5 | change |
|---|---|---|---|
| `frozen` | 77.9% | 77.9% | +0.0 points |
| `full_v1_rule` | 77.9% | 83.2% | +5.3 points |
| `full_v2` | 77.9% | 85.7% | +7.8 points |
| `gapfill_wide_only` | 77.9% | 82.9% | +5.0 points |
| `plain_store` | 28.3% | 28.3% | +0.0 points |
| `random_quarantine` | 77.9% | 75.6% | -2.3 points |
| `random_reweight` | 77.9% | 76.6% | -1.3 points |

The document-only baseline (BM25 over the same corpus, no graph) scores 28.3%, with its one hyperparameter re-tuned on this data to its own best held-out score.

Against the frozen graph, question by question on the same seed and split:

| seed | arm | gain over frozen | p (exact McNemar) |
|---|---|---|---|
| 1 | `full_v2` | +10.3 points | 0.0000 |
| 7 | `full_v2` | +6.2 points | 0.0000 |
| 42 | `full_v2` | +7.0 points | 0.0000 |
| 1 | `gapfill_wide_only` | +5.6 points | 0.0000 |
| 7 | `gapfill_wide_only` | +4.1 points | 0.0001 |
| 42 | `gapfill_wide_only` | +5.3 points | 0.0000 |
| 1 | `random_quarantine` | -3.5 points | 0.0005 |
| 7 | `random_quarantine` | -2.1 points | 0.0156 |
| 42 | `random_quarantine` | -1.2 points | 0.1250 |
| 1 | `random_reweight` | -1.2 points | 0.3438 |
| 7 | `random_reweight` | -0.6 points | 0.5000 |
| 42 | `random_reweight` | -2.0 points | 0.0391 |

How much of the repairable damage the full arm repaired, with the denominator measured by an oracle on the same data:

| seed | round 0 | last round | gained | reachable | captured |
|---|---|---|---|---|---|
| 1 | 77.1% | 87.4% | +10.3 points | 11.5 points | 90% |
| 7 | 77.3% | 83.5% | +6.2 points | 11.8 points | 53% |
| 42 | 79.2% | 86.3% | +7.0 points | 10.8 points | 65% |

#### Hypotheses, fixed before run 2 was built

| id | claim | verdict |
|---|---|---|
| H1' | the full Mend beats the frozen graph on the same held-out questions, every seed | **PASS** |
| H2' | neither random control beats the frozen graph | **PASS** |
| H3' | the plain-store arm is flat across rounds | **PASS** |
| H4' | quarantine recall on planted wrong edges >= 0.7 with false-quarantine rate <= 0.1 | **FAIL** |
| H5' | net regressions on previously-correct held-out questions <= 2% per round | **PASS** |
| H6' | the held-out wrong-answer rate falls by at least 40% | **FAIL** |
| H7' | gap-fill ingests most of what its own rule reaches | **PASS** |
| H8' | the run-2 update and gap-fill rules beat the run-1 rules on the same data | **PASS** |

### Clean replication of run 2

Run 2's arms and config digest, plus `full_unweighted` and `plain_store`, on a HydraDB emptied before the run. It decides nothing preregistered and run 2 is not replaced. Edges outside G0 on the clean frozen arm's round-0 paths: 0.

| arm | round 0 | round 5 | change |
|---|---|---|---|
| `frozen` | 77.0% | 77.0% | +0.0 points |
| `full_unweighted` | 83.3% | 89.9% | +6.7 points |
| `full_v1_rule` | 77.0% | 82.4% | +5.4 points |
| `full_v2` | 77.0% | 84.6% | +7.6 points |
| `gapfill_wide_only` | 77.0% | 81.9% | +4.9 points |
| `plain_store` | 28.3% | 28.3% | +0.0 points |
| `random_quarantine` | 77.0% | 74.8% | -2.3 points |
| `random_reweight` | 77.0% | 75.5% | -1.5 points |

Held-out questions right, clean replication against run 2 as recorded:

| seed | arm | round | clean | run 2 | difference |
|---|---|---|---|---|---|
| 1 | `frozen` | 0 | 261/340 | 262/340 | -1 |
| 1 | `frozen` | 5 | 261/340 | 262/340 | -1 |
| 1 | `full_v2` | 0 | 261/340 | 262/340 | -1 |
| 1 | `full_v2` | 5 | 294/340 | 297/340 | -3 |
| 7 | `frozen` | 0 | 259/340 | 263/340 | -4 |
| 7 | `frozen` | 5 | 259/340 | 263/340 | -4 |
| 7 | `full_v2` | 0 | 259/340 | 263/340 | -4 |
| 7 | `full_v2` | 5 | 280/340 | 284/340 | -4 |
| 42 | `frozen` | 0 | 267/342 | 271/342 | -4 |
| 42 | `frozen` | 5 | 267/342 | 271/342 | -4 |
| 42 | `full_v2` | 0 | 267/342 | 271/342 | -4 |
| 42 | `full_v2` | 5 | 291/342 | 295/342 | -4 |

Question by question at the last round, on the clean graph:

| seed | arm | against | change | p (exact McNemar) |
|---|---|---|---|---|
| 1 | `full_v2` | `frozen` | +9.7 points | 0.0000 |
| 1 | `full_unweighted` | `full_v2` | +5.0 points | 0.0023 |
| 7 | `full_v2` | `frozen` | +6.2 points | 0.0000 |
| 7 | `full_unweighted` | `full_v2` | +6.5 points | 0.0000 |
| 42 | `full_v2` | `frozen` | +7.0 points | 0.0000 |
| 42 | `full_unweighted` | `full_v2` | +4.4 points | 0.0026 |

### MetaQA, public data, half the triples withheld

Held-out Hits@1 (the top-ranked answer is a gold answer), mean of the seeds. Questions are a stratified sample of the official test split inside a seeded region of the graph; the Mend sees only questions from the official dev split. Design and reasons: [PRD §3.3](docs/PRD.md).

| arm | round 0 | round 5 | change |
|---|---|---|---|
| `frozen` | 55.3% | 55.3% | +0.0 points |
| `full_v2` | 55.3% | 71.5% | +16.2 points |
| `plain_store` | 15.5% | 15.5% | +0.0 points |
| `random_reweight` | 55.3% | 55.6% | +0.4 points |

| seed | arm | gain over frozen | p (exact McNemar) |
|---|---|---|---|
| 1 | `full_v2` | +14.7 points | 0.0000 |
| 7 | `full_v2` | +20.0 points | 0.0000 |
| 42 | `full_v2` | +13.9 points | 0.0000 |
| 1 | `random_reweight` | +0.3 points | 1.0000 |
| 7 | `random_reweight` | +0.8 points | 0.2500 |
| 42 | `random_reweight` | +0.0 points | 1.0000 |

Captured share of the gain the oracle ladder says was reachable:

| seed | round 0 | last round | gained | reachable | captured |
|---|---|---|---|---|---|
| 1 | 55.6% | 70.3% | +14.7 points | 43.6 points | 34% |
| 7 | 54.2% | 74.2% | +20.0 points | 43.9 points | 46% |
| 42 | 56.1% | 70.0% | +13.9 points | 40.3 points | 34% |

#### Hypotheses, fixed before any MetaQA question was answered

| id | claim | verdict |
|---|---|---|
| M1 | on MetaQA the full Mend beats the frozen graph on the same held-out questions, every seed | **PASS** |
| M2 | random reweighting does not beat the frozen graph | **PASS** |
| M3 | the plain-store arm is flat across rounds | **PASS** |
| M4 | the held-out wrong-answer rate falls by at least 40% | **FAIL** |
| M5 | at most 2% of held-out hits are lost from one round to the next | **PASS** |

### The same loop with unweighted search

`full_unweighted` is the full Mend with a search that ignores cost and takes the fewest hops. The first extension (below) ran at a later commit than run 2 and its frozen arm did not reproduce run 2's, so it was provisional. On the clean replication, the same loop with unweighted search goes from 83.3% to 89.9%, 5.3 points above the loop that searches on cost on the same graph (significantly higher on 3 of 3 seeds, significantly lower on 0).

| arm | round 0 | round 5 | change |
|---|---|---|---|
| `frozen` | 77.0% | 77.0% | +0.0 points |
| `full_unweighted` | 83.3% | 89.9% | +6.7 points |

<!-- run3:start -->
### Run 3: abstain instead of guessing

Generated Northwind v2, run `v3-9fe1e3a-aab4f1f7`, seeds [1, 7, 42]; 5 rounds. Training-only cutoffs were frozen before held-out scoring. The table shows means across seeds; refusals count as neither correct nor wrong, and remain in the denominator.

| arm | accuracy r0 → r5 | wrong/n r0 → r5 | refused/n r0 → r5 | coverage r0 → r5 |
|---|---|---|---|---|
| `frozen_abstain` | 77.0% → 77.0% | 13.6% → 13.6% | 0.0% → 0.0% | 90.6% → 90.6% |
| `full_v2_abstain` | 77.0% → 80.0% | 13.6% → 9.3% | 0.0% → 5.4% | 90.6% → 89.3% |
| `full_v2` | 77.0% → 84.6% | 13.6% → 9.5% | 0.0% → 0.0% | 90.6% → 94.1% |

Preregistered verdicts: **R1 FAIL**; **R2 FAIL**; **R3 PASS**.
R1 tests the wrong-answer reduction; R2 limits accuracy lost against the concurrent non-abstaining full Mend. This variant did not meet those safeguards. R3 only checks that frozen is not significantly better; it is not an equivalence or improvement claim. H6' and M4 remain failed in their original experiments.

**MetaQA run 3: not_run.** Northwind was prioritized in the preregistered time box; MetaQA needs roughly one hour per seed for three arms in addition to Northwind. No MetaQA run-3 results were measured.

Sources: [curve](evidence/curve_v3_northwind.jsonl), [training calibration](evidence/calibration_v3.json), [hypotheses](evidence/hypotheses_v3.json), [paired questions](evidence/paired_v3.json), [summary](evidence/summary_v3.json), [manifest and receipts](evidence/run_manifest_v3.json).
<!-- run3:end -->

<!-- run4:start -->
### Run 4: preserve feedback and complete answer sets

Generated Northwind v2, run `v4-b65058c-8b296c04`, seeds [1, 7, 42]; 5 rounds. Training-only cutoffs were frozen before held-out scoring. The table shows means across seeds; full_v4 and full_v4_no_gate share exactly the same learner trajectory. They are paired answer policies, not independent training interventions. Refusals count as neither correct nor wrong, and remain in the denominator.

| arm | accuracy r0 → r5 | wrong/n r0 → r5 | refused/n r0 → r5 | coverage r0 → r5 |
|---|---|---|---|---|
| `frozen_v4` | 83.3% → 83.3% | 7.3% → 7.3% | 0.0% → 0.0% | 90.6% → 90.6% |
| `full_v4` | 83.3% → 89.7% | 7.3% → 2.8% | 0.0% → 1.3% | 90.6% → 92.6% |
| `full_v4_no_gate` | 83.3% → 91.0% | 7.3% → 2.8% | 0.0% → 0.0% | 90.6% → 93.8% |
| `full_v2` | 77.0% → 84.6% | 13.6% → 9.5% | 0.0% → 0.0% | 90.6% → 94.1% |

At the final round the matched no-gate policy has the same wrong-answer counts and higher accuracy. This run shows no extra end-of-run benefit from the refusal gate itself; the repaired learner drives the gain.

Preregistered verdicts: **R1 PASS**; **R2 PASS**; **R3 PASS**.
R1 tests the wrong-answer reduction; R2 limits accuracy lost against both the matched ungated hybrid and the independent weighted full Mend. Each preregistered verdict is reported as measured. R3 only checks that frozen is not significantly better; it is not an equivalence or improvement claim. Run 3 R1/R2, H6' and M4 remain failed in their original experiments.

**MetaQA run 4: not_run.** Northwind was prioritized in the preregistered time box; MetaQA needs roughly one hour per seed for three arms in addition to Northwind. No MetaQA run-4 results were measured.

Sources: [curve](evidence/curve_v4_northwind.jsonl), [training calibration](evidence/calibration_v4.json), [hypotheses](evidence/hypotheses_v4.json), [paired questions](evidence/paired_v4.json), [summary](evidence/summary_v4.json), [manifest and receipts](evidence/run_manifest_v4.json).
<!-- run4:end -->

### Run 1, which failed and stays published

Its headline hypothesis asked for a lift larger than the spread between seeds and did not get one. It is kept here exactly as it was published, next to run 2. The two runs use different generated data, so only comparisons inside a run are claims. Why it failed is measured in [docs/RUN1_DIAGNOSIS.md](docs/RUN1_DIAGNOSIS.md).

| arm | round 0 | round 5 | change |
|---|---|---|---|
| `frozen` | 83.9% | 83.9% | +0.0 points |
| `full` | 83.9% | 84.2% | +0.4 points |
| `gapfill_only` | 83.9% | 86.1% | +2.2 points |
| `plain_store` | 24.6% | 24.6% | +0.0 points |
| `promote_only` | 83.9% | 83.9% | +0.0 points |
| `quarantine_only` | 83.9% | 83.9% | +0.0 points |
| `random_quarantine` | 83.9% | 81.3% | -2.5 points |
| `random_reweight` | 83.9% | 76.2% | -7.6 points |
| `reweight_only` | 83.9% | 82.0% | -1.9 points |

Document-only baseline on run 1's data: 24.6%.

| id | claim | verdict |
|---|---|---|
| H1 | held-out accuracy after round N exceeds round 0 by more than the seed spread, every seed | **FAIL** |
| H2 | random controls do not rise beyond seed spread | **PASS** |
| H3 | the plain-store arm is flat across rounds | **PASS** |
| H4 | quarantine recall on planted wrong edges >= 0.7 with false-quarantine rate <= 0.1 | **FAIL** |
| H5 | net regressions on previously-correct held-out questions <= 2% per round | **FAIL** |

### Evidence files

MetaQA:

| file | what it is | sha256 (first 16) |
|---|---|---|
| [`evidence/curve_metaqa.jsonl`](evidence/curve_metaqa.jsonl) | MetaQA: held-out Hits@1, exact-set and wrong-answer rate per seed, arm and round | `a981c9d80598b22d…` |
| [`evidence/paired_metaqa.json`](evidence/paired_metaqa.json) | MetaQA: every held-out question as a pair against the frozen arm, with its p-value | `ca3a70ff05a63bea…` |
| [`evidence/captured_share_metaqa.json`](evidence/captured_share_metaqa.json) | MetaQA: what the full arm gained over what the ladder says was reachable | `7b131e169539f67a…` |
| [`evidence/oracle_metaqa.json`](evidence/oracle_metaqa.json) | MetaQA: the oracle ladder on held-out, answered through HydraDB | `db6646364a4dafc9…` |
| [`evidence/non_regression_metaqa.json`](evidence/non_regression_metaqa.json) | MetaQA: hits kept and lost per round, each break traced to receipts | `7f6923cbc2c32ee6…` |
| [`evidence/plain_store_metaqa.json`](evidence/plain_store_metaqa.json) | MetaQA: the document-only baseline and the top_k sweep it was tuned by | `e8c72d824a89b792…` |
| [`evidence/hypotheses_metaqa.json`](evidence/hypotheses_metaqa.json) | MetaQA: M1 to M5 with the rule each was decided by | `d610151912558bc3…` |
| [`evidence/metaqa/dataset_s1.json`](evidence/metaqa/dataset_s1.json) | MetaQA seed 1: sizes, region, sample and digests (seeds 7 and 42 beside it) | `6e52fd8ac4e8ceec…` |
| [`evidence/metaqa/faults_s1.json`](evidence/metaqa/faults_s1.json) | MetaQA seed 1: every planted wrong triple with its kind (seeds 7 and 42 beside it) | `36f3984ec7f811a7…` |

The unweighted-search extension and the benchmark paragraph:

| file | what it is | sha256 (first 16) |
|---|---|---|
| [`evidence/curve_v2_unweighted.jsonl`](evidence/curve_v2_unweighted.jsonl) | run 2 data, later commit: the same loop with search that ignores cost | `938d599e7e50fc6c…` |
| [`evidence/paired_v2_unweighted.json`](evidence/paired_v2_unweighted.json) | the unweighted loop against run 2's weighted loop and frozen graph, paired | `738afeb09414ebb4…` |
| [`evidence/curve_v2_clean.jsonl`](evidence/curve_v2_clean.jsonl) | the clean replication of run 2, with the unweighted arm on the same graph | `4ca38754eec2efca…` |
| [`evidence/replication_v2_clean.json`](evidence/replication_v2_clean.json) | the clean replication against run 2, and both searches paired on one graph | `8225f187e6411735…` |
| [`evidence/dataset_summary_v2.json`](evidence/dataset_summary_v2.json) | run 2: nodes, edges and planted faults per generated company | `2f35abf89db8f442…` |
| [`evidence/benchmark.json`](evidence/benchmark.json) | the benchmark paragraph, one sentence per row with its sources | `ca88fd9754aeb96c…` |
| [`evidence/benchmark_facts.json`](evidence/benchmark_facts.json) | every number the benchmark paragraph uses | `9733e3f8f56f369f…` |

Run 2:

| file | what it is | sha256 (first 16) |
|---|---|---|
| [`evidence/curve_v2.jsonl`](evidence/curve_v2.jsonl) | run 2: held-out and training accuracy per seed, arm and round | `f443cd566b5953a2…` |
| [`evidence/mechanisms_v2.json`](evidence/mechanisms_v2.json) | run 2: one row per arm, from round 0 to the last round | `9b41b56e92310b2f…` |
| [`evidence/paired_v2.json`](evidence/paired_v2.json) | run 2: every held-out question counted as a pair against the frozen arm, with its p-value | `e2bf423b690173aa…` |
| [`evidence/captured_share_v2.json`](evidence/captured_share_v2.json) | run 2: what the full arm gained over what the oracle says was reachable | `e711a1c763cc6158…` |
| [`evidence/oracle_v2.json`](evidence/oracle_v2.json) | run 2: the ceiling of each repair, measured by applying it perfectly | `cdaf8d536af75918…` |
| [`evidence/changes_v2.json`](evidence/changes_v2.json) | run 2: change counts per seed, arm and round, every control beside the full arm | `6a93789cf0328241…` |
| [`evidence/non_regression_v2.json`](evidence/non_regression_v2.json) | run 2: newly fixed, newly broken and net per round, each break traced to receipts | `43ea610d10d79c0c…` |
| [`evidence/quarantine_v2.json`](evidence/quarantine_v2.json) | run 2: quarantine precision and recall against the planted faults | `1e696a446dabaec4…` |
| [`evidence/hypotheses_v2.json`](evidence/hypotheses_v2.json) | run 2: H1' to H8' with the rule each was decided by | `0ed5c1c99fd749d9…` |
| [`evidence/plain_store_v2.json`](evidence/plain_store_v2.json) | run 2: the document-only baseline, re-tuned on v2 to its own best score | `ffb5b6dcdde73a9a…` |
| [`evidence/fault_recoverability_v2.json`](evidence/fault_recoverability_v2.json) | run 2: where the truth behind each planted fault is, by fault kind | `deaa67c20abbc6c8…` |
| [`evidence/run_manifest_v2.json`](evidence/run_manifest_v2.json) | run 2: commit, HydraDB digest, config hash, data version, seeds and every digest | `9fcad8626e0e01a9…` |

Run 1, and the two files that describe the deployment both runs used:

| file | what it is | sha256 (first 16) |
|---|---|---|
| [`evidence/curve.jsonl`](evidence/curve.jsonl) | held-out and training accuracy per seed, arm and round | `eb886008a2906f65…` |
| [`evidence/round_zero.json`](evidence/round_zero.json) | the frozen-graph baseline before any judging | `5639023839538d87…` |
| [`evidence/plain_store.json`](evidence/plain_store.json) | the document-only baseline, tuned to its own best score | `e651fd53aec26236…` |
| [`evidence/mechanisms.json`](evidence/mechanisms.json) | one mechanism per arm, against full and against the random controls | `d80402a162f79b14…` |
| [`evidence/changes.json`](evidence/changes.json) | change counts per seed, arm and round, full and every control side by side | `6ebbc0facb6233c1…` |
| [`evidence/non_regression.json`](evidence/non_regression.json) | newly fixed, newly broken and net per round, each break traced to receipts | `a850cf278565d52d…` |
| [`evidence/quarantine.json`](evidence/quarantine.json) | quarantine precision and recall against the planted faults | `dedd1780b2273e19…` |
| [`evidence/hypotheses.json`](evidence/hypotheses.json) | H1-H5 with the rule each was decided by | `920ee235e0130614…` |
| [`evidence/anatomy.json`](evidence/anatomy.json) | run 1 diagnosed: every failing train question by what broke its path | `409fada1c2cb94a3…` |
| [`evidence/oracle.json`](evidence/oracle.json) | run 1 diagnosed: the ceiling of each repair on run 1's data | `21ddd7cbf2535ffa…` |
| [`evidence/fault_recoverability.json`](evidence/fault_recoverability.json) | run 1 diagnosed: whether the truth behind a planted fault exists anywhere | `58158001b487e3fd…` |
| [`evidence/run_manifest.json`](evidence/run_manifest.json) | commit, HydraDB image digest, config hash, seeds, and every file's sha256 | `a0c4e5cec36e2834…` |
| [`evidence/load.json`](evidence/load.json) | loading G0 into HydraDB, and that a re-load adds nothing | `ef1c00b3507de398…` |
| [`evidence/latency.json`](evidence/latency.json) | p50/p95/p99, QPS and errors by code under concurrent clients | `87a2921754f7ed09…` |
<!-- numbers:end -->

## Why run 1 failed and what run 2 changed

**What run 1 showed, and why it failed.** The full Mend ended round 5 at 84.2% held-out, 0.4 points above its own
round 0, and one of the three seeds did not move at all. That is well inside the 2.9-point spread between seeds at
round 0, so **H1 failed**: the lift was not bigger than the noise the seeds already carried. Three results survived
that. Gap-fill was the only mechanism that moved accuracy on its own, +2.2 points with every seed positive. Targeted
change beat random change by a wide margin on both levers measured separately — reweight −1.9 points against −7.6 for
random reweight, quarantine 0.0 against −2.5 for random quarantine — where the controls made the same number and size
of changes in the same round (`evidence/changes.json`). And the graph answered 83.9% of held-out questions against
24.6% for the document-only baseline, a 59-point gap. **H4 failed** on the false-quarantine rate (0.118, 0.188, 0.071
against a budget of 0.1) with recall at 0.92 or better on every seed, and **H5 failed** on one round where 3.25% of
previously-correct answers broke against a 2% budget. The failures are published with the rule each was decided by in
`evidence/hypotheses.json`, and the diagnosis is in
[docs/RUN1_DIAGNOSIS.md](docs/RUN1_DIAGNOSIS.md).

**What run 2 changed, and why.** The diagnosis found the headline was capped by the data, not by the mechanism: every
planted wrong edge destroyed its correct competitor, so reweighting and quarantine could only turn a wrong answer into
a refusal, never into the right answer. An oracle that quarantined every planted wrong edge scored no better than the
frozen graph. Run 2 therefore generates the faults so that repair is possible: 40% of them keep the correct edge in the
graph but better-documented on the stale side, 30% withhold the correct edge into the pool with documents that describe
it, 30% destroy it as before. Initial cost comes from one ingest rule applied to every edge — `1 / (1 + ln(support))`
over the number of documents asserting it — so the frozen graph prefers the stale fact because it is better supported,
not because anything labelled it. Blame now moves cost further than confirmation (0.35 against 0.10) with a floor at
0.5, and gap-fill runs two waves and also fires on wrong answers, not only unreachable ones. The whole design,
including every hypothesis and constant, was written into [PRD §3.2](docs/PRD.md) and `DECISIONS.md` before run 2 was
built. Run 1 stays published beside it, failed, with its own evidence files untouched.

## Limitations

These bound what the numbers can show. The first two were measured after run 1 failed, and the
whole measurement is written up in **[docs/RUN1_DIAGNOSIS.md](docs/RUN1_DIAGNOSIS.md)**: what the errors actually
were, whether each planted fault could be repaired at all, which mechanisms ran, and an oracle ceiling that shows
how much of the repairable damage the Mend left on the table. Run 2 is preregistered in
[PRD §3.2](docs/PRD.md) and is a response to it; run 1 stays published as FAIL either way.

- **A planted wrong edge has no recoverable truth in the corpus.** When a fault points a link at the wrong target,
  the true link is removed and no document describes it. Quarantining the wrong edge therefore turns a wrong answer
  into a refusal, never into a correct one. Only withheld edges (the missing-edge faults) have a document that
  gap-fill can find.
- **That was run 1's data.** Run 2 keeps 30% of its wrong edges exactly like that, on purpose, so a refusal stays
  the honest outcome for them; the rest have a true link the Mend can find, and gap-fill follows a second wave.
- **Run 2's frozen baseline carried stray edges.** The unweighted extension found residual edges outside G0 in run 2’s frozen answer paths, which put its frozen arm a few questions per seed above a clean graph. Run 2's scores and verdicts stay published as recorded. A clean replication on an emptied HydraDB (`3dbcdf3-580ae8dc`, same config digest) has no edges outside G0 and reproduces the gain; it decides nothing preregistered. See [`replication_v2_clean.json`](evidence/replication_v2_clean.json) and the diagnostic in [`paired_v2_unweighted.json`](evidence/paired_v2_unweighted.json).
- **Run 2 still failed two of its eight hypotheses.** Quarantine recall and its false-quarantine rate missed their
  thresholds (H4'), and the wrong-answer rate fell by about 30%, not the 40% that was preregistered (H6').
- **MetaQA is a sample inside a region, not the whole benchmark.** 360 held-out questions per seed, drawn from a
  seeded neighbourhood of 300 movies so that training answers and held-out answers share links; the numbers are not
  comparable to published full-test-set MetaQA results, and gold answers are not always exactly what a walk of the
  full knowledge base returns ([PRD §3.3](docs/PRD.md)).
- **Weighted search returns the cheapest answer, not the whole set.** For questions whose answer is a set, costs
  derived from document support rarely tie, so the weighted search misses members that a hop-count search returns.
  The unweighted-search extension measures this instead of hiding it.
- **`quarantine_only` is weaker than it sounds.** It applies the quarantines the full Mend planned but not the cost
  changes, so the `recent` window never fills across rounds and it can only quarantine on blame concentrated inside
  a single round.
- **The data is generated.** The entities, documents and faults come from a seeded generator, not from a real
  catalogue.
- **The live demo's receipt list empties when the service redeploys.** It is a file inside the API container, so a
  new deployment starts it empty while the graph keeps the changes those receipts describe. The recorded evaluation
  runs are not affected: their journals are in this repo under `evidence/runs/`.
- **The hosted API's p95 is connection setup, not the graph.** The first request on a fresh connection to the Railway
  edge costs about 6 s; later requests on the same connection answer in about 0.53 s, and so does a question with no
  path. The load test opens one connection per client, so 8 of its 56 requests pay that.
- **The plain-store baseline is tuned in its own favour** and the Mend's constants are frozen, which makes the gap
  between them a conservative estimate of the gap.

## Reproduce it

Each command writes into `evidence/` and prints the sha256 of what it wrote. They need a running HydraDB
(`make hydra-up`) and take hours; [JUDGING.md](JUDGING.md) lists faster checks.

```bash
uv run python -m trailmend.eval.round_zero 1 7 42       # run 1: the frozen-graph baseline
uv run python -m trailmend.eval.plain_run  1 7 42       # run 1: the document-only baseline
uv run python -m trailmend.eval.run        1 7 42       # run 1: every arm, every seed
uv run python -m trailmend.eval.analyse                 # run 1: hypotheses and manifest
uv run python -m trailmend.eval.run --v2 1 7 42 && bash scripts/run2_finish.sh   # run 2 and H1' to H8'
uv run python -m trailmend.metaqa.files                 # check a MetaQA download against the pinned sha256
uv run python -m trailmend.metaqa.run 1 7 42            # MetaQA: frozen, full_v2, random_reweight, the ladder
uv run python -m trailmend.metaqa.plain_run 1 7 42      # MetaQA: document-only baseline
uv run python -m trailmend.metaqa.analyse               # M1 to M5
uv run python -m trailmend.eval.run --unweighted 1 7 42 # the same loop, search ignoring cost
uv run python -m trailmend.eval.analyse_unweighted
uv run python -m trailmend.eval.run --clean 1 7 42      # clean replication of run 2 + unweighted, emptied HydraDB
uv run python -m trailmend.eval.analyse_replication
uv run python -m trailmend.eval.replay 1                # the landing-page replay, from run 2's seed-1 tapes
uv run python -m trailmend.eval.v3.run && uv run python -m trailmend.eval.v3.analyse   # run 3 (PRD §3.4)
uv run python -m trailmend.eval.v4.run && uv run python -m trailmend.eval.v4.analyse   # run 4 (PRD §3.5)
uv run python -m trailmend.eval.report                  # this file's numbers and the README headline
```

Run 3 was measured at commit `9fe1e3a` (tag `run3-measured`) and run 4 at `b65058c` (tag `run4-measured`); master
carries the same changes, rebased. `git checkout run4-measured` gives you the exact code a run id names.
