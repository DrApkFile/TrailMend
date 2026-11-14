# Prior art: CANON (Enoch208/canon) — teardown for the HydraDB Track 1 build

Source: `github.com/Enoch208/canon`, cloned read-only to `~/ref/canon` at commit `edeafb1`. Nothing was executed. All
line references are to that commit. 156 files, ~38k lines (most of it evidence JSON). Python backend + Next.js
console; 77 commits, all dated 2026-08-20/21 (`git log --format=%ad --date=short`), i.e. the history is a curated
replay, not a live build log.

## 1. Summary

**Hook** (`README.md:16`): *"Canon performs a Temporal Cut: BM25 decides what is relevant, HydraDB decides what is
still allowed to ground the answer."* **Problem** (`README.md:18-22`, `102-116`): a superseded claim is still
*semantically* relevant, so retrieval keeps surfacing it as present tense — measured, plain BM25 puts the superseded
gold document into context in 14/20 official conflict questions.

**The narrow claim.** Exactly one thing: inserting a claim-history graph between retrieval and generation changes
*which documents are allowed into a fixed-size context*, and that change alone moves the official scorer. Corpus, BM25
retriever, `top_k=10`, prompt, model and document count are all held constant (`README.md:279-283`). The slogan is
boxed in the README (`:41-44`): "Same model. Same prompt. Same corpus. Same context budget. Only the context topology
changes."

**What it explicitly does NOT claim** — an eleven-item limitations section (`README.md:481-510`): verified structured
residue is **0** and reported as 0 rather than relaxed (`:483-487`); verified resurrection is **0** because the
dataset has no metadata timestamps to order reassertions against (`:488-490`); temporal quality `T1/T2/T3` is
*inherited from a human-inspected inventory*, not derived (`:491-493`); answer-level rows are model-judged and
everything else is deterministic and labelled (`:494-496`); question→claim matching is lexical and embedding matching
"is not implemented" (`:497-499`); the mechanism-decomposition answer scores are `not_run` because credit ran out
mid-judging and the harness scores a failed judge call as *incorrect*, so publishing them would publish an
infrastructure artifact (`:500-504`, `evidence/mechanism.json`); identity links people, not claim authorship, since
only 2/20 conflict gold docs carry a `Name <email>` binding (`:505-508`); candidate retrieval is lexical BM25
(`:509-510`).

That list is the most judge-visible asset in the repo: it pre-empts most attacks and makes the surviving numbers
believable.

## 2. Architecture

**Data flow** (`README.md:118-143`, mermaid at `:147-159`): `Question → BM25 candidates (SQLite FTS5) → claim lookup
(HydraDB) → state {CANON | CONTESTED | UNKNOWN} → filter superseded + backfill from the same ranking → pin graph
evidence BM25 missed → context → same model/prompt`.

**Packages** (`README.md:522-540`, uv workspace at `pyproject.toml:20-28`), downward-only imports: `graph/canon_graph`
(HydraDB client, schema, ids, canonize, ingest, resolve, grounding, verify, perf), `retrieval/canon_retrieval` (SQLite
FTS5 + BM25 — `store.py:22-39` schema, `:204-215` search), `extraction/canon_extraction` (values, structured-field
parsing, conflict bundles, corpus-wide residue sweep, identity), `evaluation/canon_evaluation` (answering boundary,
context builder, metrics, arm runner, safety envelope, judging), `services/api/canon_api` (FastAPI, `app.py:50-199`),
`apps/web` (Next.js console), and `scripts/` — thin CLIs only, every one a `main() -> int` with exit codes.

**Where HydraDB sits.** Directly on the critical path of every answer. Document *text* lives in SQLite; the *truth
topology* lives only in HydraDB (`README.md:178-181`). `/v1/ground` returns 503 if the graph is unreachable rather
than degrading to plain retrieval (`app.py:98-111`, `README.md:435-437`).

**Graph schema** (`schema.py:61-80`, diagram `README.md:163-176`): Node labels: `Entity`, `ClaimKey`, `Proposition`,
`Assertion`, `Artifact`, `CanonEvent`, `Person`, `Alias`. Edges (`schema.py:72-79`, endpoint table `:178-188`):
`HAS_CLAIM`, `HAS_VALUE`, `ASSERTS`, `IN_ARTIFACT`, `SELECTS`, `SUPERSEDES`, `RESOLVES_TO`. Closed vocabularies are
`StrEnum`s — `TruthState`, `TemporalQuality`, `PropositionStatus`, `Stance`, `ResidueClass`, `Transition`,
`Discovery`, `ExtractionMethod` (`schema.py:5-58`) — and records are `@dataclass(frozen=True, slots=True)`
(`:85-176`). Node ids are deterministic 64-bit ints: `(namespace << 4 | kind) << 56 | blake2b56(key)`
(`ids.py:28-35`), with `kind_of`/`namespace_of` decoders (`:38-47`) and a per-kind natural-key function (`:50-83`) —
this is what makes re-ingest idempotent across machines and lets three namespaces (`CANON`, `VERIFY`, `BENCH`) share
one database (`ids.py:10-14`).

**Every Cypher string lives in one module**, `queries.py`, behind a `NamedQuery(name, operation, cypher)` record
(`hydra.py:37-41`). That record is what later becomes a user-visible "query card". The read queries that decide
answers:

| Purpose | Query | Location |
|---|---|---|
| Claim neighborhood | `MATCH (c:ClaimKey {id})-[:HAS_VALUE]->(p:Proposition) RETURN p.value, p.status` | `queries.py:232-239` |
| Supersession lineage | `MATCH (ev:CanonEvent {id})-[:SUPERSEDES*1..10]->(old)-[:SELECTS]->(p)` | `queries.py:252-265` |
| Residue reverse traversal | `MATCH (p:Proposition {id})<-[:ASSERTS]-(a:Assertion)-[:IN_ARTIFACT]->(d:Artifact)` | `queries.py:267-275` |
| Doc → claims (grounding) | `MATCH (d:Artifact {doc_id})<-[:IN_ARTIFACT]-(a)-[:ASSERTS]->(p)<-[:HAS_VALUE]-(c)` | `queries.py:277-289` |
| Proof path (5 hops) | `Assertion -ASSERTS-> retired <-SELECTS- old <-SUPERSEDES- new -SELECTS-> current` | `queries.py:300-315` |
| Events + what supersedes them | `CLAIM_EVENTS` with `OPTIONAL MATCH (newer)-[:SUPERSEDES]->(ev)` | `queries.py:241-250` |

**Verdict: HydraDB does real work, but the traversals are shallow.** The 4-hop `ARTIFACT_CLAIMS` join and the 5-hop
`PROOF_PATH` are genuine graph work a KV store cannot do without hand-rolled joins. But the loaded graph is tiny:
`evidence/graph_stats.json` records 20 `ClaimKey`, 40 `Proposition`, 43 `Assertion`, 38 `CanonEvent` and **19
`SUPERSEDES` edges** in the `canon` namespace. With ~1 supersession per claim, `SUPERSEDES*1..10` resolves at depth 1
in production — capability, not exercised load. The only large subgraph is identity (`Person` 35,703 / `Alias` 4,193 /
`RESOLVES_TO` 42,999) and it is **not on the answering path**. A judge reading `graph_stats.json` can say "the graph
that decides every answer has 19 edges". That is the clearest gap we can beat.

## 3. The hard core: the Temporal Cut

The named operation has two halves, and the repo insists on naming and separating them (`README.md:358-375`).

### 3a. Canonization — which value is current (`canonize.py:77-90`)

A pure function `canonize(ClaimBundle) -> CanonDecision`: no I/O, no model, fixed priority order. (1) No value with a
`CURRENT` stance → `UNKNOWN` (`:79-80`, `:93-103`). (2) One value → `CANON`, no transition (`:81-82`, `:106-117`). (3)
**Explicit supersession language** (`:83-85`, impl `:136-169`): collect signals whose `from_value` and `to_value` are
both candidates, require exactly one *sink* (a value nothing supersedes) and require the ordered chain to cover every
candidate, else bail; the `why` string literally records `"corroboration count was not consulted"` (`:166-168`). (4)
**Reliable temporal ordering**, only at `T1` (`:86-89`, impl `:205-263`): order by latest `asserted_at` per value; a
same-date tie falls back to support count and is labelled `CORROBORATION_TIEBREAK`; if all winners are structured
fields it is relabelled `STRUCTURED_TRANSITION`; an unresolvable tie returns `None` → contested. (5) Otherwise
`CONTESTED` at `T3` — never manufacture an ordering (`:90`, `:120-133`).

The load-bearing invariant — *majority never beats proven supersession* — is a unit test (`tests/test_canonize.py:48`:
8 artifacts at `$0.08` vs one explicit update to `$0.06`) **and** is re-proven live on every `make verify`
(`verify.py:72-90` builds the bundle, `:179-190` asserts `CURRENT == $0.06` and `transition is
EXPLICIT_SUPERSESSION`).

### 3b. Supersession *detection* — where the honesty gap is

`canonize` consumes `SupersessionSignal`s; it does not find them. They are built in `conflicts.py:116-147`
(`bundle_for`): if `record.explicit_supersession` is true — a boolean **read from the hand-curated
`research/conflict_inventory.json`** (loaded at `conflicts.py:45-70`, field `explicit_supersession_in_text`) — one
signal is synthesised from the recorded spans. The spans themselves *are* verified against the real document text
(`conflicts.py:85-95` `span_line` → `find_all` → `match_at`, falling back to value variants), and structuredness and
`source_field` are derived from the real line (`:97-113`). `timestamp_quality` (`T1/T2/T3`) is likewise read from the
inventory.

So the pipeline is: **human judgment (20 rows) → deterministic code → graph**. There is *no* model anywhere in
extraction (grep for `anthropic` in `packages/extraction/` returns nothing). The README states this (`:491-493`), but
understates it: the sharpest attack on CANON is *"the Temporal Cut does not detect supersession; a person did, and the
algorithm records it."*

### 3c. The cut and the backfill (`grounding.py`, `context.py`)

`ground()` (`grounding.py:162-201`): for each retrieved `doc_id`, `reader.artifact_claims(doc_id)` runs the 4-hop
Cypher — one query per document, so 10 graph round trips per question. `ALL_CLAIM_KEYS` is then matched lexically:
`match_claim_keys` (`:106-118`) requires >=3 shared terms **and** >=50 % coverage of the claim key's own terms
(`:17-18`), and `best_claim_key` (`:121-129`) returns `None` on a tie, i.e. refuses to guess (measured 20/20 conflicts
matched, 0/20 unanswerables — `README.md:195-198`). `reader.resolve()` per touched claim key (`resolve.py:212-242`)
gives `CANON` when exactly one non-superseded `CanonEvent` exists, `CONTESTED` when zero or several, `UNKNOWN` when
there are no propositions. Each document then gets one of five dispositions (`grounding.py:26-31`, logic `:132-159`):
`current_evidence`, `superseded_for_current_grounding`, `historical_evidence`, `contested_evidence`,
`not_in_claim_graph`. `KEPT_FOR_MODE` (`:34-50`) inverts the keep-set for historical mode, so the same machinery
answers "what does it say now" and "what did it used to say". `pinned_evidence` (`:204-220`) adds current-evidence
documents BM25 missed, restricted to `Discovery.CONFLICT_PAIR`.

**Backfill with exact parity** — `context.py:112-127`, the part a judge should check and the part CANON got wrong
first (`README.md:248-255`): kept docs, then pins, then the next BM25 candidates, capped at `target_docs`; crucially,
when a pin is added `kept` is truncated (`:118-119`) so the pin *evicts the lowest-ranked candidate* instead of
creating an 11th slot. `target_docs` comes from the baseline's own document count (`runner.py:230-231`), so parity is
measured, not assumed. Tested at `tests/test_evaluation.py:174`, `:182`.

### 3d. Model boundary

Exactly one place calls a model for answers (`answering.py:51-80`) and one for judging (`judge.py:243-266`). The
system prompt is shared by every arm (`answering.py:20-24`) and a unit test asserts prompt and rendering are identical
across arms (`tests/test_evaluation.py:77`). `GuardedAnswerModel` (`answering.py:139-164`) catches the first API
error, *keeps the answers already produced*, records the verbatim failure and disables itself, so a provider dying
mid-run degrades to a partial labelled result instead of zeros. Model output is validated: `parse_verdict`
(`judge.py:289-301`) extracts the JSON substring and hard-requires the three boolean keys (`KeyError` if absent — fail
loud), and three judge passes are combined by field-wise majority with a `unanimous` flag (`judge.py:269-286`,
`judge_answers.py:53-62`).

## 4. Evaluation design

**Dataset.** `onyx-dot-app/EnterpriseRAG-Bench`, 511,962 docs → 511,958 indexed (4 duplicate `doc_id`s) in 177 s,
recorded in `evidence/corpus_index.json` (`README.md:406`). Questions load as `question_id, question_type, question,
expected_doc_ids, gold_answer, answer_facts` (`questions.py:125-149`); the exact ids run are frozen in
`eval/question_ids.json` and a unit test asserts the result files match it (`tests/test_evaluation.py:91`).

**Arms.** `baseline` (BM25 top-10), `canon` (filtered + a one-line graph note), `canon_filtered` (filtered, **no
note**), plus controls. `canon_filtered` is declared the production behaviour because `/v1/ground` never returns an
answer hint (`README.md:310-315`) — which converts the obvious objection *"you told the model the answer"* into the
headline, since the no-note arm scores highest (82.5 % vs 77.5 %). **Held fixed** (`runner.py:205-255`): corpus,
retriever, `top_k`, prompt, model, and document count (200/200/200 across 20 questions).

**Metrics, and why each is not a vanity number:**

| Metric | Where | Why it is the right metric |
|---|---|---|
| Superseded gold doc in context 14/20 → 1/20 | `metrics.py:56-72`, `runner.py:93-98` | Deterministic, no model, names the failure mode directly. The remaining 1 is the contested claim where dropping would be *wrong* (`README.md:294-295`). |
| Current gold doc in context 18/20 → 20/20 | `runner.py:99-104` | Catches the opposite failure (over-filtering). Pairing the two forbids winning by deleting everything. |
| Official correctness / completeness / recall | `evidence/official_eval.json` | Scored by the benchmark's *own* harness (`metrics_based_eval --no-correction`, judge `claude-sonnet-4-6`) — not their judge. |
| Document recall **falling** 80 % → 52.5 % | `README.md:313-315` | Published as a *cost*, with the reason (the harness counts both conflicting gold docs as expected; Canon drops one on purpose). Publishing the metric you lose is what makes the rest credible. |
| Answer states current value 14.7 → 19/20 | `eval/results/summary.json` | Mean **with observed range** over 3 runs, labelled "model-judged". |
| `info_not_found` → `UNKNOWN` 20/20 | `runner.py:283-311` | Abstention measured separately, so the cut cannot be bought with hallucination. |
| Grounding p50/p95 latency | `runner.py:153-159` | In every result file, so the intervention's cost is visible. |

**Random-removal control** (`random_control.py`): per question remove the *same number* of documents Canon removed,
chosen uniformly at random with a per-question seed from `blake2b(question_id)` (`:26-28`), backfilled from the same
ranking (`:60-68`); the design string is stored in the evidence file (`:96-101`). Random removal hit the superseded
doc 1/20 and scored **70.0 %, exactly the baseline**. This isolates *knowing which document to cut* as the causal
variable and kills "you just shrank the context".

**Non-regression / safety envelope** (`envelope.py:66-95`, `safety_envelope.py`): the deterministic grounding layer
sweeps **all 500 questions**, no model. 471/480 non-conflict contexts left **byte-identical**, **0** expected
documents removed outside the conflicts, 1 removed, 8 pinned (`README.md:389-394`). Each of those 9 interventions is
traced back to its origin (`envelope.py:98-119` maps a dropped/pinned doc to "retired gold of qst_XXXX") and the
summary is bucketed by question type (`:52-63`). The claim earned is "**fail-narrow**".

**Mechanism decomposition** (`mechanism.py`, `evidence/mechanism.json`): cut-only = 1/20 leak but 18/20 current gold;
pin-only = 14/20 leak but 20/20 current gold; both = 1/20 and 20/20 — cleanly separable, neither half sufficient.
**top_k sweep** (`evidence/topk_sweep.json`): at k = 5/10/20 the baseline leaks 13/14/15 while Canon stays at 1, so
the effect is not an artifact of retrieval depth and the baseline degrades as retrieval widens. **Second model**
(`second_model.py`): identical contexts answered by `claude-haiku-4-5`, same official harness, 75.0 % → 80.0 %
(`evidence/second_model.json`), design string stored beside the number.

**Seeds and variance.** Three full end-to-end runs in `eval/results/runs/run-{1,2,3}.json`, aggregated to mean/min/max
per arm per metric (`aggregate_runs.py:126-180`). Canon was 19/20 in all three with zero variance; the other arms
moved. Note this is run-to-run variance of a stochastic model, not multiple data seeds — the only seeding is the
random-control RNG.

**Reproducibility.** `evidence/run_manifest.json` (`run_manifest.py:134-204`) fingerprints the git commit, the HydraDB
**image digest**, the dataset revision hash and SHA-256 of all 25 result files. `make export-answers`
(`export_answers.py:13-60`) writes official-format JSONL so a judge can re-score without trusting the repo; every
Makefile target is one line (`Makefile:25-59`) and the judge path is four commands (`README.md:66-71`).

**Failure honesty inside the harness.** `run_benchmark.py:74-84` refuses to overwrite `latest.json` if it holds graded
answers and this run produced none, and `--limit` writes to `partial.json`. `BenchmarkReport.not_run` (`runner.py:82`,
`:329-340`) carries a verbatim reason string into the result JSON, rendered in a UI panel titled *"Not run — Reported,
never simulated"* (`apps/web/app/results/page.tsx:278`).

## 5. Proof and honesty

**README section order** (`README.md:81-98`) is the argument: demo video → *Judge it in 90 seconds* → TOC → problem →
what I built → architecture → resolution loop → how I integrated HydraDB → engineering decisions and hard problems →
the numbers → use it as a component → identity → the live console → **Honesty: limitations** → stack → layout → run it
locally → tests → attribution → licence. The 90-second block (`:48-77`) is the whole submission on one screen: the
live URL with one sentence on what is actually running behind it, four headline numbers in a 2-column table, four
shell commands, and a pointer to `evidence/run_manifest.json`.

**Claims ledger.** There is no `CLAIMS.md`; the ledger is `evidence/` — 16 JSON files, one per claim, each with
`measured_at`, a prose `design` string stating exactly what was held fixed, and per-question rows (e.g.
`random_control.json:96-110`, `mechanism.json`, `second_model.json`), plus `run_manifest.json` hashing all of them.
Naming is flat and predictable: `evidence/<claim>.json`, `eval/official/<arm>.jsonl`,
`eval/official/results-<arm>.json`, `eval/results/runs/run-N.json`.

**How failures are recorded** — three patterns worth stealing: (1) `not_run` strings with the verbatim provider error
(`runner.py:329-340`), surfaced in the UI; (2) `evidence/mechanism.json` records un-judged arms as `not_run` *with the
reason* (credit exhausted; the harness scores a failed judge call as incorrect) rather than publishing the number
(`README.md:500-504`); (3) near-miss postmortems written into the README as engineering decisions — the judge
rate-limiting incident that nearly published 7.5 % instead of 77.5 % (`:256-261`), the 1024-row truncation caught
because two counts were suspiciously powers of two (`:262-267`), and the document-count parity bug whose headline
numbers were **re-measured rather than assumed** after the fix (`:248-255`).

**Threat model / limits** live in `Honesty: limitations` (`README.md:481-510`) plus
`research/conflict_inventory.json`, which carries explicit `"surrounding_old_value_matches": "uninspected"` and
`"inspection_limits"` fields — the curation declares what was not looked at.

**The judge path**: `canon-bay.vercel.app` → `/cut` (one real conflict, same ranking twice, the cut document, the
graph path that justifies it, both answers side by side) → `/results` (500-question safety envelope, deterministic
rows, official harness scores, four-arm answers). Page inventory at `README.md:470-479`. The 60-second version is the
README's four-number table.

## 6. Code quality

**Stack**: Python 3.12+ (`pyproject.toml:5`), uv workspace, Pydantic v2, FastAPI, SQLite FTS5, pytest, ruff; Next.js
16 / React 19 / Tailwind v4 with `strict: true` (`apps/web/tsconfig.json:11`).

**Type/schema strictness**: closed `StrEnum` vocabularies and frozen slotted dataclasses everywhere
(`schema.py:5-176`); row decoding raises on type surprises (`resolve.py:68-72` `_int` rejects bools and non-ints); the
API boundary is Pydantic. **But** there is no mypy/pyright, and `select = ["E","F","I","UP","B","SIM","N"]`
(`pyproject.toml:34-35`) has no type rules — type discipline is convention, not enforced.

**Error handling / fail-closed**: `HydraError` carries `code`, `message`, `query_name` (`hydra.py:24-29`); a named set
of transient codes is retried for 60 s and everything else raises immediately (`:17-20`, `:134-148`); unreachable is
its own exception type (`:32-35`). `/v1/ground` 503s rather than degrading (`app.py:98-111`); batch deletes back off
on `query_timeout` by quartering down to 1 (`ingest.py:44-55`); the web layer swallows errors only for optional panels
(`lib/api.ts:226`, `:242` → `null`) and `/api/ask` returns 502 with the cause (`app/api/ask/route.ts:13-16`). **Config
validation** is thin — `.env.example` is well-commented (`:1-19`) and every script checks preconditions before
spending money (`client.healthy()`, corpus exists, claim keys exist), each returning exit code 2 naming the exact
`make` target (`run_benchmark.py:47-60`) — but there is no settings object and no env schema.

**Tests**: 69 (56 unit, 15 marked `hydra`), per package in `packages/*/tests/` and `services/api/tests/`. Names are
sentences, not labels: `test_majority_cannot_override_explicit_supersession`,
`test_pinned_doc_evicts_lowest_rank_instead_of_growing_context`,
`test_guarded_model_keeps_earlier_answers_and_records_the_failure`. Integration tests **skip with a reason** when the
graph is down (`tests/conftest.py:10-15`), each gets a purged-namespace fixture (`:18-23`), and
`test_reingest_is_idempotent` asserts a second write creates **0 nodes, 0 edges** (`test_graph_roundtrip.py:85-99`).
**CI** (`.github/workflows/verify.yml`): `unit` runs `ruff check`, `ruff format --check`, `pytest -m "not hydra"`;
`hydra` boots the real HydraDB OSS image + MinIO via `docker compose`, waits for *writability*, runs `pytest -m hydra`
and `make verify`, and **uploads `evidence/verify.json` as a build artifact** (`:39-42`). **Pinning**: `uv.lock` and
`pnpm-lock.yaml` committed, CI uses `uv sync --frozen`; direct deps are floors, the lockfile pins.

**Commit style**: conventional prefixes, but the subject states the *engineering claim*, not the file touched —
`feat(benchmark): random-filter control isolates knowing-which-document-to-cut as the causal variable`;
`fix(evaluation): pinned graph evidence evicts the lowest rank so every arm answers from exactly 10 documents`;
`feat(evaluation): single LLM boundary with not_run instead of fake answers`. `git log --oneline` reads as the
argument.

**Weak spots**: no type checker; `.python-version` says `3.14` while `requires-python` and the README say 3.12; `/ask`
has no auth, no rate limit and an unbounded `top_k` (`models.py:178-182`); CORS is hardcoded to localhost
(`app.py:51-56`) and works in production only because the Next app fetches server-side; caches are single-value 60 s
TTLs with no invalidation (`cache.py:8-27`); grounding issues one `ARTIFACT_CLAIMS` query per document (N+1 against
the graph); all 77 commits land in a 2-day window, so the history is replayed, not lived.

## 7. Hosting (most relevant to us — be specific)

- **Frontend**: Vercel, `canon-bay.vercel.app` (`README.md:50`, `apps/web/.gitignore:6`).
- **Backend + graph**: a **dedicated server** (not serverless, not a laptop) running HydraDB OSS
against its S3 backend, the FastAPI service, and the full 511,958-doc SQLite index on local disk (`README.md:50-55`,
`:465-467`). There is a commit whose entire purpose is to say this: `3cc2292 docs: the live console runs on dedicated
infrastructure, not a laptop`.
- **There is no deployment config in the repo.** No Dockerfile for the API, no nginx/Caddy, no
systemd unit, no Vercel JSON, no Terraform. Only `docker-compose.yml` for the datastore and a `make api` line running
`uvicorn --reload --port 8000` (`Makefile:58-59`). The deploy was manual.
- **`docker-compose.yml:1-60`** — three services. `minio` with an `mc ready local` healthcheck, data bound to
`./hydradb-data/minio`; `minio-bucket`, a one-shot `mc mb --ignore-existing canon/hydradb` that the DB `depends_on:
service_completed_successfully`; `hydradb` from `ghcr.io/hydra-db/hydradb:latest` with `user: "${UID}:${GID}"`
(exported in `Makefile:3-4`, with a CI fix because `UID` is readonly in the runner shell — commit `641b248`), ports
`7687` Bolt / `8443` HTTP / `9090` metrics, volume `./hydradb-data`, and env `CLOUD_PROVIDER=aws`, `AWS_BUCKET_NAME`,
`AWS_DEFAULT_REGION`, `AWS_ENDPOINT` (→ MinIO), `AWS_ALLOW_HTTP=true`, key/secret, `GRAPH_NAMESPACE`, `GRAPH_ID`,
`GRAPH_CELL_ID`, `GRAPH_CELLS`, `GRAPH_NODE_ID`, `GRAPH_BOLT_NODE_ADDRESSES`, `GRAPH_ADVERTISED_BOLT_ADDR`,
`GRAPH_DATA_CACHE_DIR`, `GRAPH_AUTH_TOKEN_FILE`, `GRAPH_ALLOW_PLAINTEXT=true`, `RUST_MIN_STACK=33554432` (32 MB — deep
traversals blow the default stack). **S3/MinIO rather than a local path is mandatory**: HydraDB's writer-lease and
manifest paths need conditional writes a plain filesystem does not implement (`README.md:178-181`; commit *"run
HydraDB OSS against MinIO so writer leases survive compaction"*). Plan for MinIO from hour one.
- **Startup contract**: `make hydra-up` creates `hydradb-data/cache` + `minio`, writes the
auth token file, `docker compose up -d`, then blocks on `scripts/verify/wait_for_hydra.py`, which waits for
**writability** (a real `CREATE` probe + cleanup, `hydra.py:229-252`), not just `/healthz`. Readiness ≠ writable on
this engine.
- **Env shape** (`.env.example:1-19`): `ANTHROPIC_API_KEY` (the only thing that costs money, and
only for the answer/judge arms), `CANON_LOCAL_ENDPOINT` (any non-`claude-*` model id routes to an OpenAI-compatible
local server — `answering.py:183-191`), `HYDRA_HTTP`, `HYDRA_METRICS`, `HYDRA_TOKEN`, `CANON_CORPUS_DB`, `CANON_API`.
Client reads them via `HydraClient.from_env()` (`hydra.py:122-128`).
- **Frontend→backend wiring**: `apps/web/lib/api.ts:1` — `process.env.CANON_API ?? localhost:8000`.
All page data is fetched in **server components** with `{ cache: "no-store" }` (`lib/api.ts:195-201`), and the only
browser-initiated call goes to the app's own route handler `/api/ask` (`app/api/ask/route.ts:5-17`, clients at
`ask-client.tsx:34`, `cut-client.tsx:53`). **This BFF shape is the key hosting trick**: the API box is never called
from a browser, so there is no CORS, no mixed-content/TLS requirement on the backend, and no API key in client JS.
- **Cost control at the API**: a background thread warms the four expensive caches at lifespan
start and silently gives up if the graph is down (`app.py:29-47`); each cached endpoint is a 60-second `TimedCache`
(`cache.py:8-27`). Expensive counts are precomputed into `evidence/graph_stats.json` rather than counted per request
(`README.md:222-224`) — because unanchored scans exceed HydraDB's 30 s query timeout once a subgraph is loaded.

**Four HydraDB integration facts learned the hard way** (`README.md:214-226`) — all four cost real debugging time and
all four apply to us:
1. Write idempotency keys derive from the request `query_id`, and the server's default counter
restarts at 1 on process restart → post-restart writes silently dedupe against old results. Fix: a globally unique
`query_id` per request (`hydra.py:116-120`), and `make verify` restarts the DB mid-suite to prove it.
2. **`MERGE` does not exist**, and `MATCH` on an unknown id returns a phantom row of nulls. Fix:
check a real property (`n.kind`) before every create (`ingest.py:79-81`, `queries.py:187-191`).
3. Unanchored edge scans exceed the 30 s timeout — every product query starts from a vertex id or
a namespace predicate.
4. Deletes are asymmetric: edges tear down at thousands/s, vertices at ~1/s (`perf.py:12-22`).

**The "load test"** (`perf.py:139-244`, `evidence/hydra_perf.json`): write 10,011 vertices / 29,760 edges via `UNWIND`
batches of 1,024, measure 20 sequential runs of the three traversals Canon depends on, then tear down. Results: 5,119
edges/s write, reverse traversal (fan-in 41) p50 2.2 ms / p95 2.9 ms, `SUPERSEDES*1..10` p50 3.3 / p95 4.5, two-hop
(123 rows) p50 15.0 / p95 17.7, teardown 3,174 edges/s. **It is a latency benchmark, not a load test** — one client,
sequential, no concurrency, no sustained QPS, no error-rate-under-load, and on a synthetic subgraph rather than the
product graph.

## 8. GTM

Thin, and on a 50/50 rubric that leaves points on the table.
- **Positioning**: an infrastructure component, not an app — *"Put it between your retriever and your LLM"*
(`README.md:411-437`), one contract (`POST /v1/ground`) returning a **Temporal Context Receipt**: input ranking, cut
set with a reason per cut, final context, `context_sha256`, and the HydraDB query ids that decided it
(`app.py:98-148`). The pitch is auditability — "an auditor can replay the decision without trusting the service."
- **Buyer**: never named. Implied by the corpus (Confluence/Jira/Drive/Gmail) and the failure mode (retired
pricing quoted as current), but there is no ICP, no persona, no "who writes the cheque".
- **Pricing**: none. No tiers, no usage model, no cost per grounded call.
- **Distribution**: one X thread (`README.md:7`, `:24`, linked twice with an SVG badge), a demo video embedded
as a GitHub asset (`:30-39`), a cover image, five shields badges (CI / MIT / 69 tests / HydraDB OSS / benchmark /
stack), and the live console.
- **Sponsor credit**: HydraDB in the hook, in a dedicated *"How I integrated HydraDB"* section, in a badge, and
in `Attribution` with its licence (`README.md:600-601`).
- **Craft as GTM**: the console leads with a truth dashboard, not a chat box, and "zeros are shown as zeros"
(`README.md:468`); page titles are claims — *"BM25 tells us what is relevant. HydraDB decides what may ground the
answer."* (`apps/web/app/cut/page.tsx:16`).

## 9. Weaknesses a sharp judge could attack — and where we beat it

1. **Supersession is hand-labelled.** `explicit_supersession` and `timestamp_quality` come from
`research/conflict_inventory.json`; `bundle_for` (`conflicts.py:128-137`) converts a boolean into a graph edge. The
system cannot find a new conflict on its own. → *Our repair signals come from answer outcomes the system generates
itself, round after round.*
2. **n = 20.** Every headline rests on 20 conflict questions; a 2-question swing is ±10 points. The
500-question envelope is deterministic-only and measures absence of harm, not accuracy. → *We report an accuracy curve
on a held-out set with >=3 seeds and state n.*
3. **One-shot, not learning.** The graph is built once and frozen; nothing improves with use. Against Track 1's
bar — *an accuracy curve rising over iterations* — CANON scores zero. → *This is our whole project.*
4. **The decisive graph is 19 edges** (`evidence/graph_stats.json`); `SUPERSEDES*1..10` runs at depth 1 in
production. "Would a dict of doc_id → status do this?" has force for the cut itself; the 4-hop `ARTIFACT_CLAIMS` join
is the real defence and is undersold. → *We run weighted bounded path search (`algo.SPpaths`/`algo.MSpaths` with
`costProp`) over thousands of edges, where the path is the answer.*
5. **No real load test** — sequential, single-client, synthetic subgraph, no concurrency or error rates (§7). →
*Concurrent load on the product query mix, with the repair loop writing at the same time.*
6. **No plain-store ablation.** There is no "same pipeline without HydraDB" arm, so the graph's necessity is
argued, not measured. → *We ship that arm.*
7. **No second dataset.** Second *model* yes, second corpus no — domain-specificity untested.
8. **Model-judged rows** are the softest tier; mitigated by 3 passes + majority + a unanimity rate, and the
repo says so.
9. **Operational surface**: no auth, no rate limit, unbounded `top_k`, single-value TTL caches, N+1 graph
queries per question, no deploy config in-repo, no type checker.
10. **GTM is a thread.** No buyer, no pricing, no paid-product framing — on a 50 % GTM rubric, the cheapest gap
to close and the easiest place to outscore a technically excellent entry.

## 10. Translation table to TrailMend

| CANON pattern | Our equivalent | Verdict | Reason |
|---|---|---|---|
| Single named core operation — "the Temporal Cut" — with two separable halves, each measured alone (`README.md:358-375`) | **"the Mend"**: one named operation = *reweight + quarantine + promote + gap-fill*, decomposed into four single-mechanism arms (reweight-only, quarantine-only, promote-only, gapfill-only) | Adopt | A named operation is what judges repeat back. The decomposition table is what proves no single trick carries it, and it is cheap because the arms are deterministic. |
| Static before/after on 20 questions | **Accuracy curve over rounds** on a held-out set, ≥3 seeds, mean ± range per round, plus round-0 = frozen graph | Adapt | Track 1's stated bar is a rising curve. CANON has no equivalent; this is our headline and it must be the first chart in the README. |
| Random-removal control, same count, seeded per question (`random_control.py:26-68`) | **Random reweighting** (same number of edges, same magnitude, random targets) and **random quarantine** (same count, random edges), both seeded per round, run for the same number of rounds | Adopt | Exactly the right shape of control. It kills "you just perturbed the graph until it fit". Ours must run the full loop, not one step, or a judge will say the control was given fewer chances. |
| 500-question safety envelope, byte-identical contexts, 0 expected docs harmed (`envelope.py:66-119`) | **Non-regression on already-correct questions**: for every question correct at round *n*, assert it is still correct at round *n+1*; report net gain *and* per-round regressions, with each regression traced to the repair receipt that caused it | Adopt | This is CANON's most convincing single artifact and the natural answer to "does learning break what worked?". Tracing each regression to a receipt is strictly stronger than CANON's tracing to a supersession chain. |
| No plain-store ablation (absent) | **Plain-store ablation arm**: same ingest, same judge, same loop, but entry entities → flat top-k over a KV/vector store with no path search; show the loop cannot improve because there is no path to reweight | Adopt (new) | Directly answers the "would fall apart on a plain store" criterion, which CANON only asserts. Cheap: it is the baseline we already need. |
| Deterministic doc-level metrics (superseded in context 14→1) with the counter-metric (current gold 18→20) | **Edge precision/recall against a known-truth graph with planted wrong + missing edges**, reported as a pair: edges correctly quarantined vs good edges wrongly quarantined; plus gaps correctly ingested vs spurious ingests | Adopt | A planted-error ground truth is a deterministic, model-free metric — the same tier as CANON's strongest rows — and it is the only way to show the repair is *right*, not just that accuracy moved. |
| Second *model* replication (`second_model.py`) | **Both**: second answering/judging model **and** a second corpus/QA set | Adopt + extend | CANON's second model is cheap and we should copy it verbatim. The second dataset is the gap they left open; closing it pre-empts "it only works on your toy domain". |
| Latency benchmark labelled as perf (`perf.py:139-244`) | **Real load test**: concurrent clients against the production query mix, p50/p95/p99, sustained QPS, error rate, *and* a run with the repair loop writing concurrently | Adapt | Steal the structure (named queries, p50/p95, written to `evidence/`, notes about engine quirks); fix the gap (concurrency, writes under read load). "Holds up under load" is an explicit judging line. |
| Temporal Context Receipt: input ranking, cut set with reason, context hash, query ids (`app.py:98-148`) | **Repair receipt**: cause (which answer, which judgment), before/after edge weight or status, the HydraDB query ids that decided it, a content hash, and a **rollback** handle; `GET /receipts`, `POST /rollback/{id}` | Adopt + extend | The receipt is CANON's best product idea. Rollback is ours and is strictly more impressive: it turns an audit log into an undo, which is what makes a self-modifying graph shippable. |
| `evidence/*.json` per claim + `run_manifest.json` with git commit, image digest, dataset revision, SHA-256 of every file (`run_manifest.py:134-204`) | Same, one file per claim, plus manifest | Adopt verbatim | Highest proof-per-hour in the repo. Copy the *structure* (design string + measured_at + per-row data in every evidence file). |
| `not_run` recorded verbatim, never simulated (`runner.py:329-340`, UI panel) | Same: any round that fails (model error, budget, timeout) is recorded as `not_run` with the verbatim error and shown in the UI | Adopt | Cheap, and it is the single clearest honesty signal available. |
| `make verify` — 7 live checks incl. a DB restart mid-suite, exported as CI artifact (`verify.py:127-140`) | **`make verify`** with our invariants: write/read, persistence across restart, *a repair applies and rolls back cleanly*, *a quarantined edge stays out after restart*, *a promoted shortcut matches the multi-hop path it replaced*, fail-closed on graph down | Adopt | Live checks beat unit tests for judges. The adversarial check (majority vs supersession) has a direct analogue: *a single confirmed answer must not outweigh repeated blame* — pick our own and make it the load-bearing one. |
| Three arms incl. the "no hint" arm that defeats the obvious objection (`README.md:244-247`) | **No-LLM-writes arm is our equivalent**: state and prove that no model ever writes to the graph; the repair loop is deterministic given the judgments | Adapt | Our analogue of "you told the model the answer" is "the LLM rewrote your graph". Make the boundary explicit in code (one module, one test) and in the README. |
| Hand-curated inventory as the hard core's input (`conflict_inventory.json`) | Derive signals from the system's own answers; curate only the *ground-truth* QA set and the planted-error list, and say so | Skip the pattern, adopt the disclosure | Their curation is the attack surface. Ours must be confined to evaluation ground truth, declared in the limitations section. |
| Vercel frontend + dedicated box, all fetching in server components, only `/api/ask` client-side (`lib/api.ts:195-201`, `app/api/ask/route.ts`) | Same BFF shape | Adopt verbatim | No CORS, no TLS on the backend, no keys in client JS. Fastest safe path to a hosted judge-usable app. |
| `docker compose` MinIO + HydraDB with writer-lease-safe S3 backend, `wait_until_writable` probe (`docker-compose.yml`, `hydra.py:229-252`) | Same compose file shape, same writability gate before any ingest | Adopt verbatim | Saves hours. Plan for MinIO, `RUST_MIN_STACK`, no `MERGE`, unique `query_id` per request, and anchored queries only. |
| GTM = one thread, no buyer, no price | Named buyer, a one-page pitch with pricing, and social posts tagging HydraDB | Adopt + beat | Half the rubric. Lowest effort, highest marginal score. |
