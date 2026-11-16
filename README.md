# TrailMend

> Your service catalogue is quietly wrong. TrailMend finds out from its own answers and fixes it, with a receipt for every change.

**The graph that repairs its own relationships.** Built on [HydraDB OSS](https://github.com/hydra-db/hydradb) for the
HydraDB hackathon (Track 1: self-improving graph).

Your service catalogue is wrong in ways nobody can see: a service points at a team that no longer owns it, a rota
entry is stale, two people are the same person. The page goes to the wrong human and the incident runs long.

TrailMend answers "who do I page for this alert?" as a **weighted path search inside HydraDB**, then learns from
whether the answer was right. Confirmed links get cheaper. Blamed links get costlier. Links that keep misleading are
**quarantined** into a type the search cannot traverse. Paths confirmed again and again are **compressed** into
shortcut edges. Questions nothing could reach pull in **documents that mention the entity asked about**. Every single
change writes a **receipt before** it touches the graph, and every receipt can be rolled back.

No LLM is on the answer path, and no LLM scores an answer.

| | |
|---|---|
| Live app | https://trail-mend.vercel.app |
| API | https://trailmend-production-ee2e07ff.up.railway.app — `GET /v1/ready` |
| Loom | — |
| Repo | this one |

## The benchmark in one paragraph

<!-- benchmark:start -->
I tested TrailMend on 3 generated company graphs (1,165 nodes, 124 to 126 planted faults each) and on MetaQA, a public movie knowledge graph (134,741 triples, 360 held-out questions per seed, 3 seeds, half the triples withheld). The company-graph results are provisional: the extension did not reproduce run 2's frozen baseline, whose recorded paths include edges outside the intended G0 graph. The historical scores and verdicts remain published; this is not a clean replication. After 5 rounds of learning from its own answers, held-out accuracy on the company graphs rose from 77.9% to 85.7% (p < 0.001 on a paired test, every seed), and held-out Hits@1 on MetaQA rose from 55.3% to 71.5% (p < 0.001 on a paired test, every seed). It captured 69% of the gain that perfect repairs would give on the company graphs and 38% on MetaQA. Random reweighting, matched to its own targeted plan's number and size of cost changes each round, ends at 76.6% on the company graphs against 77.9% for the untouched graph, and at 55.6% on MetaQA against 55.3% for the untouched graph, and random reweighting did not significantly beat the untouched graph on any seed. The random arm reads no new documents; gap-fill alone, with no reweighting, reaches 82.9% on the company graphs. A plain document store over the same corpus stays flat at 28.3% (15.5% on MetaQA) because it has no links for the loop to repair, and with unweighted search the same loop goes from 83.3% to 89.9%, 4.2 points above the loop that searches on cost (provisional comparison: the frozen baselines differ, so the difference cannot be attributed to search alone). Wrong answers fell 30% on the company graphs and fell 9% on MetaQA, and 1,386 of 1,393 held-out questions that were right at the start were still right at the end, with every break along the way traced to a receipt. The graph did get bigger, but only by reading: the company graphs gained 158 links (3.2%), each from a withheld document and each under a receipt, and MetaQA read back 5,684 withheld triples. Reweighting and quarantine also change the graph; these results do not isolate their gain from gap-fill.
<!-- benchmark:end -->

That paragraph is written by `trailmend.eval.benchmark` from the evidence files and from nothing else: each sentence
is a row of [`evidence/benchmark.json`](evidence/benchmark.json) with the files it was read from, and every number in
it is in [`evidence/benchmark_facts.json`](evidence/benchmark_facts.json). Where a claim did not hold, the sentence
says what happened instead.

## The three judging criteria, and the file that proves each

| What the judges ask | What was measured | Evidence |
|---|---|---|
| **The right metrics** | Held-out exact-match accuracy on the company graphs and held-out Hits@1 on MetaQA, both fixed before the runs, with the wrong-answer rate and exact-set beside them. No LLM scores anything. Every hypothesis was written down first and the failed ones are published. | [`hypotheses_v2.json`](evidence/hypotheses_v2.json) · [`hypotheses_metaqa.json`](evidence/hypotheses_metaqa.json) · [`hypotheses.json`](evidence/hypotheses.json) (run 1, failed) · [PRD §3](docs/PRD.md) |
| **Continual learning against a baseline** | The same held-out questions after each of 5 rounds, against the frozen graph, question by question (exact McNemar), on 3 seeds; and how much of the oracle-reachable gain was captured. | [`curve_v2.jsonl`](evidence/curve_v2.jsonl) · [`paired_v2.json`](evidence/paired_v2.json) · [`captured_share_v2.json`](evidence/captured_share_v2.json) · [`curve_metaqa.jsonl`](evidence/curve_metaqa.jsonl) · [`paired_metaqa.json`](evidence/paired_metaqa.json) · [`non_regression_v2.json`](evidence/non_regression_v2.json) |
| **The graph does real work, and it falls apart on a plain store** | Random reweighting with the same number and size of changes; the same corpus in a BM25 document store with no graph; and the same loop with a search that ignores the learned costs. | [`changes_v2.json`](evidence/changes_v2.json) (matched controls) · [`plain_store_v2.json`](evidence/plain_store_v2.json) · [`plain_store_metaqa.json`](evidence/plain_store_metaqa.json) · [`curve_v2_unweighted.jsonl`](evidence/curve_v2_unweighted.jsonl) · [`paired_v2_unweighted.json`](evidence/paired_v2_unweighted.json) |

## Judge it in 60 seconds

1. `/ask` — ask **"Who is on call for the Delta team?"** It answers *Selin Tadesse* over an edge costing 0.477,
   because three documents say so. The truth is *Bao Maeda*, asserted by one document, so that edge costs 1.000.
2. Press **wrong**. The edge on the path gets more expensive and you are handed a receipt id. Ask again: 0.677.
   Wrong again: 0.960. On the third, the edge has been blamed often enough to be **quarantined**, and the answer
   becomes *Bao Maeda* — the correct person, reached over the link the stale one was outranking.
3. Nothing else moved: every change wrote its receipt before touching the graph, and each one can be rolled
   back. The demo graph is shared, so if someone judged before you the answer may already be *Bao Maeda*; the
   costs on the page tell you which state you are in, and an admin reset puts it back.
4. `/mend` — how often quarantine was right on the recorded runs, against the planted faults, and every change
   the live demo graph has made. Each one has a **roll this back** button that undoes it and leaves its own receipt.
5. `/truth` — every fault planted in the demo graph, read back from HydraDB as it is now: still wrong, quarantined,
   corrected, or restored by gap-fill, with the receipts that changed it. The Delta on-call fault moves from
   *still wrong* to *quarantined* after step 2.
6. `/evidence` — every number on the site, with the file that produced it and that file's sha256.

## The numbers

<!-- numbers:start -->
### Run 2, on dataset v2

**Provisional conclusions:** the later extension failed to reproduce this run's frozen baseline. Its recorded paths include edges outside the intended G0. Historical scores and hypothesis outputs are preserved; see [the replication diagnostic](evidence/paired_v2_unweighted.json).

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

### The same loop with unweighted search (extension, not part of any preregistered verdict)

Run 2's data and constants at a later commit. `full_unweighted` is the full Mend with a search that ignores cost and takes the fewest hops. **Provisional:** the frozen arm does not reproduce run 2; the diagnostic records edges outside G0 in run 2's frozen tape. No controlled paired comparison is claimed.

| arm | round 0 | round 5 | change |
|---|---|---|---|
| `frozen` | 77.0% | 77.0% | +0.0 points |
| `full_unweighted` | 83.3% | 89.9% | +6.7 points |

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
| [`evidence/dataset_summary_v2.json`](evidence/dataset_summary_v2.json) | run 2: nodes, edges and planted faults per generated company | `aec631ed06e31b33…` |
| [`evidence/benchmark.json`](evidence/benchmark.json) | the benchmark paragraph, one sentence per row with its sources | `77b40db5822d5572…` |
| [`evidence/benchmark_facts.json`](evidence/benchmark_facts.json) | every number the benchmark paragraph uses | `d556d35371a48963…` |

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

Every figure above is written into this file by `trailmend.eval.report` from the files in `evidence/`. None of them is
typed by hand. The evaluation data is **generated**, and is labelled generated everywhere it appears; no customer data
has been measured.

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

## How HydraDB is used

HydraDB OSS 0.4 is the only store on the answer path. It is run unmodified as a separate service.

- **Answering** is `algo.SSpaths` from the question's seed entity over the relationship types that template allows,
  `weightProp: 'cost'`, `maxLen` 3. The answer is the cheapest reachable node of the expected kind. A tie refuses
  rather than guesses, unless the question's gold is a set.
- **Learning** writes back to the same edges: `cost`, `confirms`, `blames` and a `recent` window of judgement codes
  live as relationship properties, so blame survives a round and a restart.
- **Quarantine** moves an edge to a mirror type `Q_<TYPE>` (copy, then delete). `require_searchable` makes it
  impossible to build a query that searches a `Q_` type, so a quarantined edge cannot come back through a code path
  that forgot about it.
- **Shortcuts** are new edges of type `SC_<TEMPLATE>` carrying the `via_path` they compress, created at the summed
  cost of the hops they replace, and retired when any hop is quarantined.
- **Gap-fill** creates the edge a withheld document describes, with `origin: gapfill`.

Facts about HydraDB 0.4 that are not in any model's training data, each verified live before being relied on, are in
[docs/REALITY_SPIKES.md](docs/REALITY_SPIKES.md) — among them: `UNWIND $rows` only feeds a write, never a `RETURN`;
an `UNWIND` write cannot `SET` a literal; `count(n)` is rejected but `count(*)` works; a `relTypes` entry that no edge
carries is accepted and ignored; relationship properties do come back inside returned paths; and a repeated
`query_id` is silently dropped after a restart.

## Who this is for, and what it costs

**Buyer.** The person who owns the on-call rota and the service catalogue: a platform or SRE lead at a company with
enough services that nobody holds the whole map in their head.

**Pain.** The catalogue is wrong in ways nobody notices until an incident. A service points at a team that no longer
owns it, a rota entry is stale, two entries describe the same person. The page goes to the wrong human and the
incident runs long. The map is maintained by hand, so it decays between audits.

**Status quo.** A catalogue in a wiki or a Backstage entry plus a quarterly audit. Correctness depends on someone
remembering to edit it, and nothing uses the one signal that is always available: whether the answer it just gave
was right.

**Price.** $4 per service in the catalogue per month, minimum $400 / month.

**Pilot.** 6 weeks, $2,000, capped at 250 services. Judged on one number agreed up front: the share of "who owns
this / who do I page" questions answered correctly on a held-out set your team writes, measured before and after six
weeks of judging. If it does not improve, the pilot is refunded.

**What it is not.** Not an incident-response tool, not a replacement for the catalogue as the place humans edit, and
there is no LLM on the answer path. The same terms are on [/pricing](apps/web/app/pricing/page.tsx).

## Limitations

These are real and they bound what the numbers can show. The first two were measured after run 1 failed, and the
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
- **Run 2 did not replicate on a fresh baseline.** The unweighted extension found residual edges outside G0 in run 2’s frozen answer paths. Its historical scores and verdicts remain published with provisional conclusions; the reset was tightened between runs. See [`paired_v2_unweighted.json`](evidence/paired_v2_unweighted.json).
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

## Questions judges usually ask

**"Isn't this Cognee?"** Cognee adjusts weights from sentiment over text. TrailMend repairs the graph's structure —
quarantine, shortcut compression, gap-fill — and answers by weighted path search inside HydraDB, with the lift
measured against random controls that make the same number and size of changes.

**"Would a dictionary do this?"** The `plain_store` arm answers that: the same questions over the same documents with
no graph, BM25-ranked, its one hyperparameter tuned in its own favour. Its curve is flat by construction because it
cannot learn.

**"You tuned it until it went up."** The Mend's constants are in `config/mend.toml` and were fixed before the first
run; the run id in every evidence file is `<commit>-<config digest>`, so a changed constant changes the run id. The
hypotheses were written before the run and the failed ones are published with their rules.

**"Does it break what used to work?"** `evidence/non_regression.json` has newly fixed, newly broken and net per
round, with each break traced to the receipt ids on the path it used to take.

**"Is it just SelfGraph?"** SelfGraph turns text into a graph and does not learn from answers; it is not on the
answer path (`docs/SELFGRAPH.md`). The loop, the search and the evaluation are in `src/trailmend/{loop,search,eval}`.

**"The data is synthetic."** Yes, deliberately: the faults have to be known for precision and recall on them to mean
anything. It is labelled generated everywhere it appears, and no customer data has been measured.

## Run it locally

```bash
uv sync --frozen
make gate                     # ruff, ruff format, pyright strict, unit tests, web build
make hydra-up                 # moto_server as the S3 stand-in, then the pinned HydraDB image
make verify                   # live contract tests against a real HydraDB
make hydra-down
```

To reproduce the measurements (each writes into `evidence/`, and each prints the sha256 of what it wrote):

```bash
uv run python -m trailmend.eval.round_zero 1 7 42   # the frozen-graph baseline
uv run python -m trailmend.eval.plain_run  1 7 42   # the document-only baseline
uv run python -m trailmend.eval.run        1 7 42   # every arm, every seed, N rounds
uv run python -m trailmend.eval.analyse             # curve, regressions, quarantine, hypotheses, manifest
uv run python -m trailmend.eval.report              # fill the numbers block in this file
```

Run 2, MetaQA and the unweighted-search extension:

```bash
uv run python -m trailmend.eval.run --v2 1 7 42 && bash scripts/run2_finish.sh   # run 2 and H1' to H8'
uv run python -m trailmend.metaqa.files                 # check a MetaQA download against the pinned sha256
uv run python -m trailmend.metaqa.run 1 7 42            # frozen, full_v2, random_reweight and the ladder
uv run python -m trailmend.metaqa.plain_run 1 7 42      # the document-only baseline on MetaQA
uv run python -m trailmend.metaqa.analyse               # M1 to M5
uv run python -m trailmend.eval.run --unweighted 1 7 42 # the same loop, search ignoring cost
uv run python -m trailmend.eval.analyse_unweighted
uv run python -m trailmend.eval.report                  # numbers block and the benchmark paragraph
```

`make hydra-up` needs Docker. Without it, build `graph-node` from the HydraDB repo and run it against any
S3-compatible endpoint; see [docs/REALITY_SPIKES.md](docs/REALITY_SPIKES.md) S1, S10 and S12.

## How it is put together

```
src/trailmend/core/    pure Mend: credit, bounded update, quarantine rule, promotion, receipts, rollback
src/trailmend/graph/   the only place a Cypher string exists; client, schema, state, loader, reset
src/trailmend/search/  seeding a question to entities, and turning paths into an answer
src/trailmend/loop/    a round: judge, credit, plan, apply, promote, gap-fill, journal, tape
src/trailmend/eval/    splits, the arms, the runs, and every evidence file
src/trailmend/api/     the product API
apps/web/              the site, server components calling that API
```

`trailmend/core` does no I/O, reads no clock and touches no global randomness. Held-out questions are made only by
`trailmend/eval/splits.py`, and the round runner's signature takes `TrainQuestion`, so handing it a held-out question
is a type error.

## Docs

- Plan: [docs/PRD.md](docs/PRD.md) · Build order: [docs/TASKS.md](docs/TASKS.md) · Rules:
  [docs/BUILD_CONTRACT.md](docs/BUILD_CONTRACT.md)
- HydraDB facts verified live: [docs/REALITY_SPIKES.md](docs/REALITY_SPIKES.md)
- What is left before submission, in order: [docs/SUBMISSION.md](docs/SUBMISSION.md) · Demo script:
  [docs/LOOM_SCRIPT.md](docs/LOOM_SCRIPT.md)
- Every design decision and why: [DECISIONS.md](DECISIONS.md) · What is deliberately not built:
  [ROADMAP.md](ROADMAP.md)
- Why run 1's headline failed, measured on the train split only: [docs/RUN1_DIAGNOSIS.md](docs/RUN1_DIAGNOSIS.md)

## Attribution

MetaQA is from Zhang, Dai, Kozareva, Smola and Song, *Variational Reasoning for Question Answering with Knowledge
Graph*, AAAI 2018 (https://github.com/yuyuz/MetaQA), released under a Creative Commons licence. Its files are not
redistributed here: [`data/external/metaqa.manifest.json`](data/external/metaqa.manifest.json) pins the sha256 of
each file the run used and [`data/external/README.md`](data/external/README.md) says where they go. The incomplete-KG
setting (half the triples withheld) follows `MetaQA_half` in Saxena, Tripathi and Talukdar, *Improving Multi-hop
Question Answering over Knowledge Graphs using Knowledge Base Embeddings* (EmbedKGQA), ACL 2020, re-drawn per seed.

HydraDB is AGPL-3.0 and runs here as a separate, unmodified service, pulled by digest. TrailMend's own code is
Apache-2.0. [SelfGraph](docs/SELFGRAPH.md) was evaluated and is **not** on the answer path.
