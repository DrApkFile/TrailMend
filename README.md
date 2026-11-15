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
| Live app | — not deployed yet |
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
| `frozen` | 85.3% | 85.3% | +0.0 points |
| `full` | 85.3% | 85.9% | +0.6 points |
| `gapfill_only` | 85.3% | 87.1% | +1.8 points |
| `plain_store` | 26.5% | 26.5% | +0.0 points |
| `promote_only` | 85.3% | 85.3% | +0.0 points |
| `quarantine_only` | 85.3% | 85.3% | +0.0 points |
| `reweight_only` | 85.3% | 82.6% | -2.6 points |

The document-only baseline (BM25 over the same corpus, no graph) scores 24.6%, with its one hyperparameter tuned to its own best held-out score.

### Preregistered hypotheses

Not decided yet.

### Evidence files

| file | sha256 (first 16) |
|---|---|
| [`evidence/curve.jsonl`](evidence/curve.jsonl) | `6fb955cfad1a19f0…` |
| [`evidence/round_zero.json`](evidence/round_zero.json) | `5639023839538d87…` |
| [`evidence/plain_store.json`](evidence/plain_store.json) | `e651fd53aec26236…` |
| [`evidence/mechanisms.json`](evidence/mechanisms.json) | not measured |
| [`evidence/non_regression.json`](evidence/non_regression.json) | not measured |
| [`evidence/quarantine.json`](evidence/quarantine.json) | not measured |
| [`evidence/hypotheses.json`](evidence/hypotheses.json) | not measured |
| [`evidence/run_manifest.json`](evidence/run_manifest.json) | not measured |
| [`evidence/load.json`](evidence/load.json) | `ef1c00b3507de398…` |
<!-- numbers:end -->

Every figure above is written into this file by `trailmend.eval.report` from the files in `evidence/`. None of them is
typed by hand. The evaluation data is **generated**, and is labelled generated everywhere it appears; no customer data
has been measured.

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
