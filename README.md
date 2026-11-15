# TrailMend

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

## Judge it in 60 seconds

1. `/ask` — run one of the listed questions. You see the path the graph walked and the cost of every hop.
2. Press **wrong**. The edges on that path get more expensive and you are handed receipt ids.
3. Ask again. If another route is now cheaper, the answer changes. Nothing else moved.
4. `/mend` — watch blame build up on a planted bad link until it is quarantined, then roll it back.
5. `/evidence` — every number on the site, with the file that produced it and that file's sha256.

## The numbers

<!-- numbers:start -->
### Held-out accuracy by arm

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

The document-only baseline (BM25 over the same corpus, no graph) scores 24.6%, with its one hyperparameter tuned to its own best held-out score.

### Preregistered hypotheses

| id | claim | verdict |
|---|---|---|
| H1 | held-out accuracy after round N exceeds round 0 by more than the seed spread, every seed | **FAIL** |
| H2 | random controls do not rise beyond seed spread | **PASS** |
| H3 | the plain-store arm is flat across rounds | **PASS** |
| H4 | quarantine recall on planted wrong edges >= 0.7 with false-quarantine rate <= 0.1 | **FAIL** |
| H5 | net regressions on previously-correct held-out questions <= 2% per round | **FAIL** |

### Evidence files

| file | what it is | sha256 (first 16) |
|---|---|---|
| [`evidence/curve.jsonl`](evidence/curve.jsonl) | held-out and training accuracy per seed, arm and round | `eb886008a2906f65…` |
| [`evidence/round_zero.json`](evidence/round_zero.json) | the frozen-graph baseline before any judging | `5639023839538d87…` |
| [`evidence/plain_store.json`](evidence/plain_store.json) | the document-only baseline, tuned to its own best score | `e651fd53aec26236…` |
| [`evidence/mechanisms.json`](evidence/mechanisms.json) | one mechanism per arm, against full and against the random controls | `1b6e39d34eaa9cdb…` |
| [`evidence/changes.json`](evidence/changes.json) | change counts per seed, arm and round, full and every control side by side | `b14b4d9431df9f8b…` |
| [`evidence/non_regression.json`](evidence/non_regression.json) | newly fixed, newly broken and net per round, each break traced to receipts | `ddc8dd735fbac782…` |
| [`evidence/quarantine.json`](evidence/quarantine.json) | quarantine precision and recall against the planted faults | `469a904d687f9a53…` |
| [`evidence/hypotheses.json`](evidence/hypotheses.json) | H1-H5 with the rule each was decided by | `adda1c68bb594490…` |
| [`evidence/run_manifest.json`](evidence/run_manifest.json) | commit, HydraDB image digest, config hash, seeds, and every file's sha256 | `b17958ea0db6a340…` |
| [`evidence/load.json`](evidence/load.json) | loading G0 into HydraDB, and that a re-load adds nothing | `ef1c00b3507de398…` |
| [`evidence/latency.json`](evidence/latency.json) | p50/p95/p99, QPS and errors by code under concurrent clients | `87a2921754f7ed09…` |
<!-- numbers:end -->

Every figure above is written into this file by `trailmend.eval.report` from the files in `evidence/`. None of them is
typed by hand. The evaluation data is **generated**, and is labelled generated everywhere it appears; no customer data
has been measured.

**What this run showed.** The full Mend ends round 5 at 84.2% held-out, 0.4 points above its own round 0, and one of
the three seeds did not move at all. That is well inside the 2.9-point spread between seeds at round 0, so **H1
fails**: the lift is not bigger than the noise the seeds already carry. Three results survive that. Gap-fill is the
only mechanism that moves accuracy on its own, +2.2 points with every seed positive. Targeted change beats random
change by a wide margin on both levers measured separately — reweight −1.9 points against −7.6 for random reweight,
quarantine 0.0 against −2.5 for random quarantine — where the controls made the same number and size of changes in
the same round (`evidence/changes.json`). And the graph answers 83.9% of held-out questions against 24.6% for the
document-only baseline, a 59-point gap. **H4 fails** on the false-quarantine rate (0.118, 0.188, 0.071 against a
budget of 0.1) with recall at 0.92 or better on every seed, and **H5 fails** on one round where 3.25% of
previously-correct answers broke against a 2% budget. The three failures are published with the rule each was decided
by in `evidence/hypotheses.json`.

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

These are real and they bound what the numbers can show.

- **A planted wrong edge has no recoverable truth in the corpus.** When a fault points a link at the wrong target,
  the true link is removed and no document describes it. Quarantining the wrong edge therefore turns a wrong answer
  into a refusal, never into a correct one. Only withheld edges (the missing-edge faults) have a document that
  gap-fill can find.
- **Gap-fill is one wave.** It reads only pool documents that mention the seed entity of the question that failed.
  Measured on seed 1, that reaches 35 of 96 unreachable questions; following the newly reached nodes for one more
  wave would reach 43, and is not built.
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

## Attribution

HydraDB is AGPL-3.0 and runs here as a separate, unmodified service, pulled by digest. TrailMend's own code is
Apache-2.0. [SelfGraph](docs/SELFGRAPH.md) was evaluated and is **not** on the answer path.
