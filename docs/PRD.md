# PRD: TrailMend — the graph that repairs its own relationships

Status: draft v1, 2026-11-14. Product: TrailMend. Core operation: the Mend.
Track: 1 (self-improving graph). Engine: HydraDB OSS 0.4 (self-hosted). SelfGraph: not on the answer path (spike S-SG1); optional at ingest only.
Inputs: EVENT.md, IDEA_CHECK.md, STAKEHOLDERS.md, SELFGRAPH.md, PRIOR_ART_CANON.md, UPGRADES.md.

## 1. Goals and non-goals

Goals
- G1. A graph search system whose held-out accuracy rises over rounds because it repairs its own graph from the outcomes of its own answers.
- G2. Prove it against matched baselines and controls, with deterministic scoring and ≥3 seeds.
- G3. Show the graph is necessary: the same loop on a plain store cannot improve.
- G4. Every graph change has a receipt and can be rolled back.
- G5. A hosted app a judge can use in 60 seconds, holding up under concurrent load.
- G6. A credible paid-product pitch with a named buyer.

Non-goals
- Not a general agent-memory platform. Not a replacement for HydraDB Cloud.
- No LLM writes to the graph, ever. No LLM in scoring.
- No claims about production traffic; evaluation is on a generated org graph and (if the spike passes) one public multi-hop KG benchmark.
- No temporal-truth / supersession feature (CANON's ground).

## 2. Hook, loop, boundary

Hook: "Your knowledge graph is wrong in ways nobody can see. TrailMend finds and fixes its own bad links, and shows you a receipt for every fix."

Loop: ingest → ask → traverse → answer → judge → mend → (next round) … including the step others skip: undo.

Boundary
- Search proposes paths. Judgements come from ground truth (eval) or a user (product).
- Deterministic code decides every graph change.
- The model never: writes or deletes edges, changes costs, merges entities, or scores answers. (Optional LLM use: phrasing the final answer sentence in the UI only.)

## 3. Preregistered hypotheses

### 3.1 Run 1 — fixed before the first run, decided, published

H1. On held-out questions, accuracy after round N of the Mend exceeds round 0 (frozen graph) by a margin larger than the spread across seeds, for every seed.
H2. Random-reweight and random-quarantine controls, making the same number and size of changes for the same rounds, do not rise beyond seed spread.
H3. The plain-store arm is flat across rounds.
H4. Quarantine recall on planted wrong edges ≥ 0.7 with false-quarantine rate ≤ 0.1 by round N.
H5. Net regressions on previously-correct held-out questions ≤ 2% per round.

Primary metric (chosen now, not post hoc): held-out answer accuracy = exact match of the answer entity id set (Hits@1 for single-answer, set-F1 reported alongside for multi-answer).
Any hypothesis that fails is published as failed.

**Decided on run `01f1f6f-06b10c13`: H1 FAIL, H2 PASS, H3 PASS, H4 FAIL, H5 FAIL.** Published in `evidence/hypotheses.json`,
in the README and on `/evidence`, and they stay there whatever run 2 shows. Why they came out that way is measured in
`docs/RUN1_DIAGNOSIS.md`.

### 3.2 Run 2 — preregistered 2026-11-15, before anything was built or run

Every line below is fixed before the generator, the update rule or the arms are touched, and each is traced to the
finding in `docs/RUN1_DIAGNOSIS.md` that motivates it. Run 1 is not re-run and not withdrawn. The two runs use
different data (v1 and v2), so **only within-run arm comparisons are claims**; absolute accuracy across runs is not.

**Versioning, so run 1 stays reproducible.** A dataset is never stored: it is regenerated from its seed, and the run
manifest records the sha256 of the generated graph, faults, documents, questions and split. `data_version` ("v1",
"v2") therefore lives in the generation call, in the run manifest and in the config digest, not in a path. v1
generation is left exactly as it is, so run 1's digests still reproduce; run 1's evidence files are not regenerated,
not overwritten and not re-scored. Both runs are served, each with its run id and its data version.

**Dataset v2 — what changes and why.** Diagnosis §2 and §5: all three structural fault classes are unrepairable, the
corpus corroborates the wrong version, and perfect quarantine is worth +0.0. The planted wrong edges are therefore
split into three declared kinds, in the fault file, so that the mechanisms under test have something they can
actually repair and something they provably cannot:

| kind | share of planted wrong edges | what G0 holds | which mechanism can repair it |
|---|---|---|---|
| `contradicted` | 0.4 | the stale wrong edge **and** the true edge, both priced by the ingest rule below | reweight alone |
| `recoverable` | 0.3 | the wrong edge; the true edge is withheld into the pool with its documents | gap-fill |
| `destroyed` | 0.3 | the wrong edge only, exactly as in run 1 | none — it can only become a refusal |

A `contradicted` fault is a fact that *was* true and is now stale: the service was handed over, and the catalogue
still carries the old owner. The stale edge wins at round 0 because it is better documented, not because anything
labelled it. That is the ingest rule's job, not a constant:

**One ingest rule, applied to every edge, knowing nothing about labels, faults or questions.** An edge's initial cost
is derived from how many ingested documents assert it:

> `cost(e) = INGEST_BASE / (1 + ln(support(e)))`, `INGEST_BASE = 1.0`, `support(e) ≥ 1`

which gives 1.000, 0.591 and 0.477 for support 1, 2 and 3: better-attested links are cheaper to walk, by one monotone
rule with no special case anywhere in it. Support is drawn for **every** edge in the graph from one declared
distribution — P(1) 0.55, P(2) 0.25, P(3) 0.20 — and the corpus renders that many documents per edge, each from a
different template. Support stops at 3 because there are exactly three document templates per relation type, and a
fourth supporting document could only be the same sentence twice; the rule itself is defined for any support. A
`contradicted` fault's stale edge draws from the top of that same distribution while the true edge it contradicts
draws 1, so the frozen graph prefers the stale owner by the rule and needs three blames to be talked out of it.
Support 3 is not a fault detector: 20% of ordinary edges have it. Gap-fill ingests at the same rule, from the number
of pool documents supporting the edge it adds, where run 1 ingested everything at a flat 1.0.

Two consequences, stated now rather than discovered later: round 0 is a different and stronger baseline than run 1's,
where every edge cost 1.0; and the cost ties that the C3a tie rule was written for mostly disappear, since two routes
now only tie when their support agrees exactly.

Everything else about the data is unchanged: missing-edge, alias-duplicate and conflation shares, sizes, templates,
split share, and the rule that documents are rendered from G0 plus the pool.

**Update rule v2 — what changes and why.** Diagnosis §6: 43 of 44 receipts behind the round-1 breaks carry only
`confirm` signals, 31% of touched edges sit on the 0.05 floor by round 5 and 89% are below 0.2, and nothing is
quarantined after round 3. The step becomes asymmetric and the floor rises: `eta_blame` 0.35, `eta_confirm` 0.10,
`cost_floor` 0.5, `cost_ceiling` 20.0 unchanged. The old rule is kept as its own arm so the change is measured, not
assumed.

**Gap-fill v2 — what changes and why.** Diagnosis §5: +9.8 points are available and `gapfill_only` took +2.2.
Gap-fill triggers on **wrong** answers as well as unreachable ones, and follows one extra wave from the nodes the
first wave reached (REALITY_SPIKES S25 measured one wave reaching 35 of seed 1's 96 unreachable questions and two
reaching 43). Kept as its own arm against the narrow rule.

**Arms (7).** `frozen`, `plain_store`, `full_v2`, `full_v1_rule` (v2 data, run-1 update rule and narrow gap-fill),
`gapfill_wide_only`, `random_reweight`, `random_quarantine`. The two random controls keep INV6: the same number and
size of changes as the arm they mirror, in the same round. Run 1's mechanism-ablation arms are not in this sweep, so
what each random control mirrors is **`full_v2`**'s plan: it plans with the same update rule as `full_v2` on its own
graph, then applies exactly as many changes as that plan contains, of the single mechanism it controls, to edges
drawn at random. `check_inv6` verifies that equality round by round before any curve is written, and a test pins the
rule identity, so the pairing cannot drift to a rule the headline arm does not use.

**Seeds and rounds.** Seeds 1, 7, 42; 5 rounds. Seeds 101 and 404, and the mechanism-ablation arms
(`reweight_only`, `quarantine_only`, `gapfill_only`, `promote_only`), run **only if the main sweep finishes early**
and are published as a clearly separated extension. No extension row may enter a preregistered verdict: H1'–H8' are
decided on seeds 1, 7, 42 and the seven arms above, whatever an extension shows.

**Constants fixed now** (changing any of them changes the config digest and therefore the run id): `eta_blame` 0.35,
`eta_confirm` 0.10, `cost_floor` 0.5, `cost_ceiling` 20.0, `window` 6, `quarantine_min_blames` 3,
`quarantine_blame_share` 0.8, `quarantine_confirm_ceiling` 1, `promote_min_questions` 3, `max_len` 3,
`result_limit` 200, `rounds` 5, `gapfill_waves` 2, `stale_true_edge_cost` 2.0, fault shares `wrong_edge_share` 0.08
split 0.4 / 0.3 / 0.3, `missing_edge_share` 0.06, `alias_duplicate_share` 0.05, `conflated_people` 1.
`plain_store_top_k` is tuned to the baseline's own best held-out score, as in run 1.

**Primary metric.** Unchanged: held-out answer accuracy, exact match of the answer entity id set.
**Secondary metric, preregistered now:** the held-out **wrong-answer rate** (wrong / n), because a refusal and a
wrong page are not the same thing to the person being paged, and run 1 could only express the difference as a loss.

**Hypotheses.**

H1'. On **all 3 of 3 seeds**, `full_v2` beats `frozen` on the same held-out questions at round 5 under a two-sided
exact McNemar test at p < 0.05, with a gain of ≥ 2.0 points. (Replaces run 1's H1, which compared a per-seed delta
against the spread *between seeds* at round 0 — that spread measures how different three generated companies are, not
the noise in the delta. Diagnosis finding 5.)
H2'. Neither random control beats `frozen` under the same paired test on any seed.
H3'. The `plain_store` arm is flat across rounds.
H4'. Quarantine recall on planted wrong edges ≥ 0.7 with a false-quarantine rate ≤ 0.1, every seed. Unchanged from
run 1, where it failed on the false-quarantine rate.
H5'. Net regressions on previously-correct held-out questions ≤ 2% in every round. Unchanged from run 1, where it
failed at 3.25%.
H6'. In `full_v2`, the held-out wrong-answer rate falls by ≥ 40% from round 0 to round 5, on every seed.
H7'. `full_v2` ingests ≥ 60% of the withheld edges its own rule can reach, every seed.
H8'. `full_v2` beats `full_v1_rule` under the same paired test on at least 2 of the 3 seeds. This is the test of the
update-rule and gap-fill changes together, on identical data.

**The ladder is run on v2 too, and the captured share is published.** `trailmend.eval.oracle` walks the same
cumulative ladder on dataset v2 into `evidence/oracle_v2.json`, and the analysis publishes, beside the curve,
`full_v2`'s **captured share of the reachable gain**: (`full_v2` at round 5 − round 0) ÷ (the ladder rung that
repairs every fault the arm's mechanisms can reach — contradicted, recoverable and withheld — minus round 0). Run 1
captured 4% of its reachable gain and nothing on the page said so. This number is reported whatever it is, and it is
not a hypothesis.

Any hypothesis that fails is published as failed, beside run 1's.

### 3.3 MetaQA — preregistered 2026-11-15, before any MetaQA question was answered through HydraDB

A second dataset the project did not generate: MetaQA (Zhang et al., AAAI 2018), a movie knowledge base of 134,741
`subject|relation|object` lines (133,582 distinct triples, 43,234 entities, 9 relations) with 1-, 2- and 3-hop
questions whose topic entity is the `[bracketed]` span. The files are not redistributed; `data/external/metaqa.manifest.json`
pins their sha256 and `trailmend.metaqa` loads them. Everything below is fixed now. The only things measured before
writing it were offline counts on the files, never an answer from HydraDB, and each is stated where it is used.

**Graph.** Each triple is one typed edge `MQ_<RELATION>` from the movie to its object and one edge of a separate
type `MQ_<RELATION>_REV` back. The two directions carry their own cost, counters and receipts. Entities are typed by
the position they hold (movie, person, year, language, genre, tag, votes, rating), so a title that is also a tag is
two nodes.

**Incomplete-KG setting.** A seeded random 50% of the distinct triples is G0 and the other half is the gap-fill
pool — the `MetaQA_half` setting of EmbedKGQA (Saxena et al., ACL 2020), re-drawn per seed rather than taken from
their file. A document asserts a triple, so ingesting a pool document adds both directions.

**Faults, by the Northwind v2 rule.** 8% of G0's triples get a wrong object of the same type that is not a true
object of that movie and relation, split 0.4 `contradicted` / 0.3 `recoverable` / 0.3 `destroyed` exactly as in §3.2,
and every one is declared in `evidence/metaqa/faults_s<seed>.json`. Support and initial cost use the same ingest
rule and the same distribution; a contradicted fault's stale triple draws 3 and the true one 1. Alias duplicates and
conflations are not planted: MetaQA has no alias table to draw them from.

**Questions.** Train is a sample of the official **dev** split and held-out a sample of the official **test** split,
each stratified by hop and qtype (largest-remainder allocation). Both are drawn from one seeded *workload region*:
300 movies grown breadth-first through shared people from a seeded start movie, plus the people in them; a question
is eligible when its topic entity is in the region. A held-out question never shares (topic, qtype) with a train
question. Sizes: **480 train, 360 held-out per seed**, 5 rounds, seeds 1, 7, 42 — chosen so three seeds of three
graph arms and the ladder fit the time box. Why a region: a uniform sample of 480 of the 39,138 dev questions shares
a topic entity with 8 of 360 uniformly sampled test questions (measured offline), so there would be almost no edge a
train answer could teach a held-out answer through and the run could neither pass nor fail. A region is what usage
looks like — questions cluster — and it is the same for every arm. `tag_to_movie` has no eligible question because
its topic is a tag.

**Search.** `algo.SSpaths` from the topic entity over the relation types on the question's qtype path, `maxLen` =
hops, `weightProp: 'cost'`, `pathCount` 500; a path counts only if its relation sequence equals the qtype's and it
visits no node twice. Answers are ranked by cheapest path cost, ties by entity id. 500 or more rows is a refusal
(`budget_exceeded`), never a truncated answer.

**Metrics.** Primary: held-out **Hits@1** (the top-ranked answer is a gold answer), the field's standard for MetaQA.
Reported beside it: exact-set (every answer the graph supports equals the gold set) and the wrong-answer rate
(top-ranked answer is not gold) / n. An unreachable or refused question is not a hit and not a wrong answer.
Known ceiling, measured offline: walking the *full* knowledge base along the qtype path reproduces the gold set
exactly for 81% of questions and as a strict superset for the rest (3-hop paths that pass back through the topic
movie, and same-titled films merged under one name), so a perfect graph does not score 100%.

**Arms (4).** `frozen`; `plain_store` (BM25 over the documents G0 was ingested from, its `top_k` swept on seed 1's
held-out questions and fixed at its own best Hits@1); `full_v2` (update rule v2 with quarantine, and gap-fill on wrong and unreachable train
answers); `random_reweight` (INV6: as many reweights as `full_v2`'s rule plans on its own graph each round, with the
same signals, on edges drawn at random from the G0 edges that lie on a qtype path of some train question — the
edges the Mend itself could have touched — and nothing else). Constants are `config/mend.toml` unchanged plus
`config/metaqa.toml`; both digests are in the run id.

**Two adaptations of the loop, declared.** (1) Gap-fill follows the failed question's own relation path: wave *i*
ingests the pool documents that mention an entity reached so far and assert the relation the question needs at hop
*i*, for as many waves as the question has hops. Northwind's rule (every pool document mentioning the entity, then
one more wave) would pull in a year's or a genre's whole pool the first time a movie was a gap. Documents are still
chosen by the topic entity and the question's relations, never by the gold answer (INV7). (2) Promotion is off:
shortcut types are per template and MetaQA has 49 qtypes.

**Hypotheses.**

M1. On all 3 seeds, `full_v2` beats `frozen` on the same held-out questions at round 5 under a two-sided exact
McNemar test at p < 0.05, with a gain of at least 2.0 points of Hits@1.
M2. `random_reweight` does not beat `frozen` under the same test on any seed.
M3. `plain_store` is flat across rounds.
M4. In `full_v2` the held-out wrong-answer rate falls by at least 40% from round 0 to round 5, on every seed. Stated
knowing it may fail here: gap-fill makes unreachable questions answerable, and some of the new routes run over
planted wrong triples.
M5. In `full_v2`, at most 2% of the held-out questions that were hits after one round are not hits after the next,
in every round and seed.

**The ladder.** The same cumulative oracle ladder runs on held-out through HydraDB — G0; contradicted stale triples
removed; recoverable triples restored; the whole pool ingested; destroyed wrong triples removed — and `full_v2`'s
captured share of the reachable gain (round 5 − round 0, over the "whole pool ingested" rung − round 0) is published
whatever it is. It is not a hypothesis.

Any hypothesis that fails is published as failed, beside the Northwind runs.

### 3.4 Run 3 — abstain instead of guessing, preregistered 2026-11-16

This is a new experiment. H6' and M4 remain failed; no published evidence is overwritten.
Northwind v2 runs first, seeds 1, 7, 42, five rounds, with independent resets before
`frozen_abstain`, `full_v2_abstain` and the non-abstaining `full_v2` reference. Same Mend,
search, splits, document corpus and gap-fill rules as run 2; only the refusal policy changes.
MetaQA is **not_run in this time box**: its three-arm measurement needs roughly an hour
per seed, in addition to Northwind, while the owner records at 08:00 Lagos. No MetaQA
run-3 verdict will be inferred from Northwind. It requires a separately recorded run.

Before any held-out answer is scored, calibrate on each seed's **training split only**,
on G0 through the unchanged weighted search. For each question template separately,
collect costs of correct exact-set training answers. Fix the cutoff to the nearest-rank
95th percentile: sorted costs at index ceil(0.95*n)-1. Empty strata explicitly get cutoff
0 and are recorded as such, not replaced by another stratum. Freeze each cutoff for all
arms and rounds of that seed; persist counts, training question ids and calibration costs.
No held-out score, prior published metric, or hypothesis verdict selects a cutoff.

The gated answer refuses with `low_confidence` if its chosen best path costs **strictly
more** than its template cutoff, or any selected answer path traverses a pool/gap-filled
edge whose graph confirmation count is zero. For shortcuts, inspect their constituent
`via_path` edges too. Equality at the cost cutoff is accepted. Existing unreachable,
ambiguous and budget refusals keep their reasons. This gate applies to training as well
as held-out answers; a refusal contributes no feedback under the existing loop. It may
therefore leave ingested edges unconfirmed indefinitely; no oracle bypass is added to
rescue accuracy. Gold remains available only in the existing training judge and credit
assignment. Neither the gate nor pool selection receives held-out gold.

Record accuracy, wrong/n, refused/n, unreachable/n, coverage (correct+wrong)/n,
low_confidence/n and receipts per round. Primary hypotheses, decided separately on every
measured dataset and requiring all three seeds:

- R1: full_v2_abstain wrong/n at round 5 is at most 0.60 times round 0, every seed.
  A zero baseline with a zero final rate is INCONCLUSIVE (no reduction to measure);
  a zero baseline followed by a positive rate fails.
- R2: round-5 exact-match accuracy of full_v2_abstain is no more than 0.02 below the
  concurrently measured full_v2, every seed. This exposes gains bought by refusing right answers.
- R3: frozen_abstain does not beat full_v2_abstain at round 5 under a two-sided exact
  McNemar test at p < 0.05 on the same held-out questions, every seed. A tie satisfies this
  weak non-superiority claim; it is not evidence of improvement or equivalence.

Also report the paired full-vs-frozen differences and accuracy/coverage tradeoff without
additional success claims. Run id includes the committed code and digests of mend.toml
and run3.toml. New outputs only: curve_v3_northwind.jsonl, calibration_v3.json,
hypotheses_v3.json, paired_v3.json and run_manifest_v3.json; receipts and held-out tapes
use the new run id and arm names. Original full_v2, run-2 and MetaQA files remain immutable.
Preregistration and calibration provenance are published whatever the verdicts.

### 3.5 Run 4 — retain training feedback and return complete sets

Preregistered after run 3 completed and before implementing this follow-up. Run 3's
R1/R2 failures remain published unchanged. This experiment repairs two identified
design limitations without retuning run 3's cutoff from held-out results.

Northwind v2, seeds 1, 7, 42, five rounds. Same Mend constants and gap-fill rule.
Single-answer templates keep weighted search. Multi-answer templates use hop-count
search, returning all eligible endpoints tied at minimum depth. This structural
choice follows the declared set-answer semantics; no gold cardinality is supplied
to search. It also applies to training candidates and training gold-path lookup.

Training feedback comes from an ungated internal candidate audit, scored against
training gold by the existing exact judge. A public refusal no longer suppresses
that audit. Held-out questions never supply training credit. The published gate
still refuses above its fixed cost cutoff or on an unconfirmed gap-filled link,
including shortcut constituents. Per-template cutoffs use the same nearest-rank
95th percentile rule on correct round-0 training answers, now through the hybrid
search, so set-answer costs and thresholds both use hop-count units. No held-out
score selects the rule or its cutoff.

Four reported arms, three independent graph trajectories: frozen_v4; full_v4;
full_v4_no_gate; and existing weighted full_v2. The full_v4 and full_v4_no_gate
outputs are paired read-only evaluations of the EXACT SAME hybrid learner after
each round. Both share its receipt journal and changes; their held-out outputs
have separate tapes. They are not independent learner interventions. This matched
control isolates the cost of the answer gate. The weighted full_v2 reference and
frozen_v4 start from independently reset G0 graphs. Frozen uses the same calibrated
hybrid answer gate and receives no updates.

Hypotheses, all three seeds required:

- R1: full_v4 held-out wrong/n at round 5 <= 0.60 times its own round 0 rate.
  Zero-to-zero is INCONCLUSIVE; zero-to-positive fails.
- R2: full_v4 round-5 accuracy is no more than two points below BOTH its matched
  full_v4_no_gate output and the concurrent weighted full_v2 reference.
- R3: frozen_v4 does not significantly beat full_v4 on the paired exact McNemar
  test, p < 0.05. This remains a weak check, not equivalence or proof of improvement.

Publish accuracy, wrong/n, refused/n, unreachable/n, coverage and low-confidence
refusals by seed, arm and round. Publish whatever the fixed rule produces; do not
change the gate or select another quantile after inspecting held-out performance.
MetaQA is not_run in this time box. Measurement may finish after the Loom UI cutoff;
keep the already published run-3 landing line stable during recording. New run-4
curves, calibration, hypotheses, summary and provenance files only. All run-3 and
historical evidence files remain immutable.

## 4. Datasets

D1 "Northwind" (generated, seeded, deterministic, no LLM)
- A fictional 300–500 person SaaS company: Person, Team, Service, Alert, Customer, Incident, Runbook, Repo.
- Relations (directed; every one points the way a question is answered, because HydraDB path search is `relDirection: 'outgoing'` and one type per MATCH pattern — S4/S5): ALERTS_ON (Alert→Service), OWNED_BY (Service→Team), ON_CALL (Team→Person, exactly one per team), MEMBER_OF (Person→Team), DEPENDS_ON (Service→Service, acyclic), AFFECTS (Incident→Service), SERVES (Service→Customer), ESCALATES_TO (Person→Person), MAINTAINS (Team→Repo), DOCUMENTED_BY (Service→Runbook). This replaces the earlier draft list `OWNS / ON_CALL_FOR / CUSTOMER_OF`, which pointed against the direction of travel; see DECISIONS 2026-11-14.
- Truth graph T. Rendered into text documents (Slack-like threads, runbooks, tickets) from templates; documents are what gets ingested.
- Planted faults, declared in `data/<seed>/faults.json`:
  - wrong edges (e.g. stale or swapped OWNS) — rendered in some documents as the fault would really appear;
  - missing edges — their documents held back in a "not yet ingested" pool;
  - duplicate entities via aliases ("payments-api", "PaySvc");
  - one conflated entity (two people named Alex rendered as one) for split.
- Questions: templated 1–3 hop, with gold answer ids, e.g. "Who do I page for the checkout-latency alert?" (Alert→Service→Team→Person).
- Split by question into train / held-out (≈60/40), stratified by template and hop count. Held-out questions share graph regions with train questions but never the same (seed entity, template) pair.
- 3 seeds = 3 different companies + fault sets.

D2 public multi-hop KG QA (spike S-D2 decides which: MetaQA preferred; 1/2/3-hop questions with gold entities). Faults planted the same way. If no dataset is reachable and usable, D2 is recorded as not_run with the reason.

## 5. Architecture

```
Vercel (Next.js, server components = BFF) ──HTTPS──▶ Railway: API (FastAPI, Python 3.12)
                                                        │  Bolt / HTTP
                                                        ▼
                                              Railway: HydraDB OSS 0.4 graph-node
                                                        │
                                              Railway bucket (S3-compatible)
```

Packages (downward imports only; ours are the top four):
- `trailmend/core` — pure, no I/O: credit assignment, the update rule, quarantine/promotion/merge/split decisions, receipts, rollback inverse. Property-tested.
- `trailmend/search` — weighted bounded path search via `algo.SSpaths` / `algo.SPpaths` / `algo.MSpaths` with `costProp`; entry-entity seeding; answer selection.
- `trailmend/loop` — rounds, policy seam (`MendPolicy`: full, reweight_only, quarantine_only, promote_only, gapfill_only, random_reweight, random_quarantine, frozen).
- `trailmend/eval` — datasets, splits, scorers, arms, evidence writers, run manifest, load test.
- `trailmend/graph` — HydraDB client (named queries in one module, unique query_id per request, writability gate), schema, ids.
- `trailmend/ingest` — document → facts → our typed edges, deterministic. SelfGraph's HydraDB layout (single `RELATES` edge type, revisions as edges) can't carry typed weighted search (S-SG1), so it is not used on the answer path; optional P1 use for extracting gap-fill documents, behind our interface, pinned.
- `services/api`, `apps/web`.

## 6. Graph schema (ours)

- Nodes: entity labels above, plus `Doc`. Every node: `id` (deterministic 64-bit from natural key), `name`, `aliases`, `kind`.
- Relationship properties on every edge: `cost` (float, init 1.0), `status` (`active` | `quarantined`), `confirms`, `blames`, `origin` (`ingest` | `shortcut` | `gapfill`), `doc_ids`, `receipt_ids`.
- Shortcut edges: type `SC_<TEMPLATE>` per question template, carrying `via_path` (the hop list) and `origin: shortcut`. Search for a template lists its base types plus its `SC_` type.
- Quarantine (decided by spike S5): a quarantined edge moves to the mirror type `Q_<TYPE>` with all its properties plus `was: <TYPE>`; search never lists `Q_*` in `relTypes`. Order: MERGE the mirror first, then DELETE the original (auto-commit only, so a crash leaves both; replay finishes the move). Restore is the reverse. Both directions write a receipt first.
- Edges between existing nodes are written with a full-pattern `MERGE (a:Label {id})-[:TYPE {...}]->(b:Label {id})`; `MATCH (a),(b) CREATE` is rejected by the 0.4 mutation engine (S5).

## 7. The Mend (core engine, ordered steps per judged answer)

1. Seed: map question text to entry entities (exact name/alias match first, then BM25 over names/aliases). Zero seeds → `no_seed` outcome, recorded; ambiguous (>1 equal-best) → `ambiguous_seed`, refused.
2. Search: `algo.SSpaths` from seed over the template's allowed relTypes (learned recipe, P1; fixed per template in P0), `maxLen` ≤ 3, `costProp: cost`, answer = lowest-cost reachable node of the expected label. Ties → refuse (`ambiguous_answer`).
3. Judge: compare with gold (eval) or user verdict (product). Outcome ∈ {correct, wrong, unreachable, refused}.
4. Credit: correct → confirm edges on the chosen path. Wrong → blame edges on the chosen path that are not on any gold path; confirm edges on the cheapest gold path if reachable (contrastive). Unreachable → gap record {seed, expected label, template}.
5. Update (pure): `cost ← clamp(cost · e^{−η})` on confirm, `cost ← clamp(cost · e^{+η})` on blame, bounds [0.05, 20]. η fixed per run.
6. Quarantine: an edge with blames ≥ k_q and blame share ≥ 0.8 over its last w judgements, and confirms below c_max, is quarantined. Invariant: one confirmation never outweighs repeated blame; repeated blame never quarantines an edge that is on a confirmed gold path in the same round.
7. Promote (path compression): a multi-hop path confirmed in ≥ m distinct questions becomes a shortcut edge from first to last node, with `via_path`; if any hop is later quarantined, the shortcut is retired.
8. Gap-fill (gap-driven ingestion): for each gap, fetch from the not-yet-ingested pool only documents mentioning the seed entity (never the gold), ingest them, record what was added.
9. Merge/split (P1): merge two entities when they share an alias and confirmations route through both interchangeably ≥ m times; split an entity when its confirmed paths partition into two disjoint neighbourhoods. Every merge/split is reversible.
10. Receipt: every change in 5–9 writes one receipt (append-only) with cause, before, after, query ids, hash, and inverse. Rollback applies the inverse and writes its own receipt.

All constants (η, k_q, w, c_max, m) are fixed in config before the first evaluation run and recorded in the run manifest.

## 8. Arms (same data, same splits, same rounds)

| Arm | What changes |
|---|---|
| frozen | round 0 graph every round |
| plain_store | BM25 over documents; answer = most frequent entity of expected label in top-k docs; no graph |
| mend_full | all mechanisms |
| reweight_only / quarantine_only / promote_only / gapfill_only | one mechanism |
| random_reweight | same count and magnitude of cost changes per round, random edges, seeded |
| random_quarantine | same count of quarantines per round, random edges, seeded |
| vector_store (P1) | embedding top-k instead of BM25; needs an embedding model reachable from the host |

## 9. Metrics (all deterministic)

Per (dataset, seed, arm, round): held-out accuracy (primary), set-F1, newly fixed / newly broken / net (each break traced to receipt ids), edges touched, quarantine precision/recall vs planted faults, false-quarantine rate, gaps found / filled / spurious ingests, shortcuts created/retired, mean path length, search latency p50/p95.
Load: concurrent clients on the product query mix, p50/p95/p99, QPS, error rate by code, with and without the Mend writing concurrently.

## 10. Evidence

- `evidence/curve.jsonl`: `dataset, seed, arm, round, n_heldout, correct, accuracy, set_f1` — appended by the loop, never edited. Run 1 only: once published, its 162 rows are fixed and their sha256 is the one `run_manifest.json` records.
- `evidence/curve_v2.jsonl`: the same rows for run 2, plus `data_version`, `rules` and the cumulative gap-fill counts. A row is written to the file its `data_version` names, and a v2 row offered to run 1's file is refused, so the two runs cannot mix.
- `evidence/<claim>.json` per claim, each with `measured_at`, `design` string, per-row data.
- `evidence/run_manifest.json`: git commit, HydraDB image digest/commit, dataset hashes, config, SHA-256 of every evidence file.
- Failed or skipped items: `not_run` with the verbatim reason.

## 11. API (product contract)

- `POST /v1/ask {question}` → answer, path, cost, receipt-relevant edge ids, refusal codes.
- `POST /v1/judge {ask_id, verdict, correct_answer_id?}` → receipts written.
- `POST /v1/mend/round` (admin) → runs one round on the demo graph.
- `GET /v1/receipts`, `GET /v1/receipts/{id}`, `POST /v1/rollback/{id}`.
- `GET /v1/evidence/curve`, `GET /v1/graph/neighbourhood/{id}`.
Closed error codes: `no_seed`, `ambiguous_seed`, `ambiguous_answer`, `unreachable`, `graph_unavailable` (503, never degrade silently), `budget_exceeded`, `invalid_request`, `rate_limited`.

## 12. Web app pages

1. `/` — the curve (all arms, seed bands), the one-line hook, the 60-second path.
2. `/ask` — ask a question, see the path drawn, judge it, watch receipts appear.
3. `/mend` — the planted bad link: round-by-round blame building up, quarantine, accuracy rising; one-click rollback.
4. `/evidence` — tables per claim, controls, mechanism decomposition, non-regression, load test, not_run items.
5. `/pricing` — the pitch.

## 13. Demo script (Loom, ~3–4 min)

1. 0:00 Problem: one wrong ownership link sends every page to the wrong team.
2. 0:30 Ask the question live; wrong answer; path shown.
3. 1:00 Run rounds; blame accumulates; quarantine fires; receipt opened.
4. 1:40 Same question now correct; shortcut edge shown.
5. 2:10 The curve vs frozen, plain store and random controls.
6. 2:50 Rollback a fix live; then re-apply.
7. 3:10 Load test numbers. 3:30 Who pays and pricing.

## 14. Tests (mirror the claims)

- `core`: update rule is monotone and bounded; one confirm never outweighs k blames; quarantine never fires on an edge on a same-round confirmed gold path; rollback(apply(x)) == x (property test); shortcut retired when a hop is quarantined; receipts are append-only.
- `search`: ties refuse; maxLen respected; quarantined edges never used.
- `eval`: splits are disjoint and stable per seed; scorers deterministic; controls make the same count and size of changes as the real arm; curve rows match the run manifest.
- `graph` (marked `hydra`, skip with reason if unreachable): re-ingest is idempotent (0 new nodes/edges); a quarantine survives a restart; writes after restart are not deduped.

## 15. Priorities

P0: HydraDB hosted and writable; D1 generator + faults + questions; weighted search; core update + quarantine + receipts + rollback; loop with policy seam; frozen, plain_store, mend_full, random_reweight, random_quarantine arms; curve with 3 seeds; non-regression; quarantine P/R; web `/`, `/ask`, `/mend`; README judge path; Loom; posts.
P1: promote + gap-fill arms; mechanism decomposition; concurrent load test; D2; vector arm; merge/split; `/evidence`, `/pricing`.
Never tonight: auth beyond a shared token and rate limit; multi-tenant; connectors to real apps.

## 16. Build order (record each demo step when it works)

1. Spikes S1–S6 + S-SG1 + S-D2. 2. HydraDB on Railway, writability gate. 3. D1 generator. 4. Graph loader + search. 5. Core + receipts. 6. Loop + arms + curve. 7. API. 8. Web. 9. Measurements P1. 10. README, evidence, Loom, posts.

## 17. Definition of finished

Clean clone → `make gate` passes; live link works from a fresh browser; curve and controls published for 3 seeds; every README number links to an evidence file; Loom recorded; posts live and logged; submission sent before 09:00 IST Nov 16.

## 18. Submission mapping

Live link → Vercel URL. Repo → public GitHub. Loom → linked at top of README. Posts → `evidence/posts.md` with URLs.

## 19. Judge Q&A

- "Isn't this Cognee?" Cognee adjusts weights from sentiment. TrailMend repairs the graph's structure (quarantine, shortcuts, gap-fill), executes as weighted path search inside HydraDB, and proves the lift against random controls.
- "Would a dict do this?" The plain-store arm answers that with a flat curve.
- "You tuned until it went up." Constants fixed before the first run; random controls get the same number of changes for the same rounds.
- "Does it break what worked?" Per-round newly broken counts, each traced to a receipt.
- "Is it just SelfGraph?" SelfGraph turns text into a graph; it doesn't learn from answers. The loop, search and evaluation are ours, in separate packages.
- "The data is synthetic." Yes, by design so faults are known; D2 is public (or recorded as not_run).

**Time boxes (Lagos time, 2026-11-15 into 16).** H1–H4 built and `make gate` green by **19:00**; the sweep finished
by **23:30**; analysis, README numbers and live verification by **00:30**. A missed box is reported immediately with
what is left, and scope is never cut silently to make one.
