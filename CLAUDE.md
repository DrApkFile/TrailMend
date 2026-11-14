# CLAUDE.md — TrailMend

TrailMend: the graph that repairs its own relationships. HydraDB hackathon, Track 1 (self-improving graph).
Hard deadline: **Nov 16, 09:00 IST** (03:30 UTC). Submission: hosted live app + public repo + Loom.

## Read before every task
1. `docs/TASKS.md` — the ordered build plan. Work the next unchecked task; tick it when its acceptance passes.
2. The PRD section the task names (`docs/PRD.md`). Do not derive requirements from memory.
3. `docs/BUILD_CONTRACT.md` — binding. Never fabricate, no silent fallback, traceable numbers.
4. `docs/REALITY_SPIKES.md` before touching HydraDB queries.

## What already exists and is proven (don't rewrite without reason)
- `src/trailmend/graph/` — HTTP client (unique `query_id` per request, bookmark read-your-writes, writability probe,
  fail-closed `graph_unavailable`), strict value decoding, deterministic ids, named queries with identifier validation.
- `src/trailmend/core/` — pure Mend core: credit assignment, bounded multiplicative update, quarantine rule,
  receipts with sha256 digest, rollback inverse. Property-tested.
- `tests/live/` — contract tests against a real HydraDB (route flip on cost change, quarantine never searched).
- `make gate` passes: ruff, pyright strict (0 errors), pytest.

## Invariants the code can't show
- HydraDB OSS 0.4 is the only graph store on the answer path. No LLM writes to it, and no LLM scores answers.
- `trailmend/core` is pure: no I/O, no clock, no global randomness (inject a seeded `random.Random`).
- Every Cypher string is built in `trailmend/graph/queries.py` as a `NamedQuery`. Nowhere else.
- Every change to edge cost/status goes through a receipt. Write the receipt before the graph effect.
- Held-out questions never reach the Mend. Only `trailmend/eval/splits.py` makes splits.
- Our code (core, search, loop, eval) must be obviously ours. SelfGraph is not on the answer path (docs/SELFGRAPH.md).

## HydraDB OSS 0.4 — verified facts (NOT in your training data)
- Writes: single-statement `MERGE … SET` is rejected. Use the batch forms:
  `UNWIND $rows AS row MERGE (n {id: row.id}) SET n:Label, n.name = row.name` and
  `UNWIND $rows AS row MATCH (a:L {id: row.src}), (b:L {id: row.dst}) MERGE (a)-[r:T {id: row.eid}]->(b) SET r.x = row.x`.
  Single `MATCH (a {id:$src})-[r:T]->(b {id:$dst}) SET r.cost = $cost` works. `MATCH (a),(b) CREATE` is rejected.
- Always send a unique `query_id` (the client does). The server counter restarts at 1 and silently drops repeated
  writes after a restart.
- Send the last `bookmark` back for read-your-writes (the client does).
- Storage must be S3-compatible (MinIO / Railway bucket / moto for dev). Local disk breaks after a restart.
- Cypher subset: one relationship type per MATCH pattern, directed only, bounded `*1..3`, WHERE has no IN / CONTAINS /
  ENDS WITH / IS NULL, WITH is pass-through, auto-commit only.
- Weighted search: `algo.SSpaths` / `algo.SPpaths` / `algo.MSpaths` with `weightProp: 'cost'`; `relTypes` may list
  several types; `maxLen` counts edges; `pathCount` caps total paths returned. Fewer rows can mean a budget was hit.
- Quarantine = move edge to `Q_<TYPE>` (copy then delete). `require_searchable` makes searching `Q_*` impossible.
- Anchor every product query on an id. Unanchored scans can time out.

## Conventions
- No comments; names explain (ruff `ERA` bans commented-out code). Split files past ~180 lines.
- Pydantic `extra="forbid"` at boundaries; frozen dataclasses in the core; discriminated unions for outcomes.
- Closed error codes in `trailmend/errors.py`; API errors say whether anything changed.
- Tests named as behaviour; acceptance ids (A01…, INV1…) in names where they prove a rubric item or invariant.
  Live tests marked `hydra`, skip with a reason when HydraDB is down.
- Evidence files are written by code, never by hand. Show `—` in the UI until a real value exists.
- Commit as you go with behavioural subjects ("quarantine never searches Q_ types"). Never rewrite history.
- New ideas → `ROADMAP.md`. Anything not built is listed as not built.
- Web pages checked at 390px wide.

## Local HydraDB
- With Docker: `make hydra-up` (MinIO + HydraDB image), then `make verify`.
- Without Docker: build `graph-node` from github.com/hydra-db/hydradb and run it against an S3 emulator; see
  `docs/REALITY_SPIKES.md` S1/S10/S12.
