# BUILD_CONTRACT

## Frozen decisions (change only with a DECISIONS.md entry)
- Track 1. HydraDB OSS 0.4 is the only graph store on the answer path.
- No LLM writes to the graph or scores answers. Scoring is exact-match against gold ids.
- Our code (core, search, loop, eval) lives in our own packages. SelfGraph, if kept, sits only behind `trailmend/ingest`, pinned to one exact version.
- Mend constants are fixed in `config/mend.toml` before the first evaluation run; changing them starts a new run id.
- Python 3.12, uv, FastAPI, Pydantic v2, pytest + hypothesis, ruff, pyright strict. Web: Next.js on Vercel, server components only call the API (BFF).
- Hosting: Railway for HydraDB + bucket + API; Vercel for web.

## Never fabricate
- No placeholder data shown as real; show `—` until a real value exists.
- No fallback that returns fake success. Graph down → 503 `graph_unavailable`.
- No metric, test count or curve point reported before it is produced by a run on record.
- Generated data is labelled "generated" everywhere it appears (UI, README, evidence).

## No silent fallback
- Config validated at startup by one settings object; missing required value → process exits with the name of the variable.
- No bare `except`, no empty `except`, no `or default` on values that matter.

## Traceable numbers
Every number in README/UI/Loom records: dataset, seed(s), arm, round, n, run id, git commit, HydraDB commit/digest, classification (measured / provisional / not_run). README numbers link to the evidence file that holds them.

## Failures stay on record
Failed hypotheses, failed runs and not_run items are published with the verbatim reason. Claims that don't replicate are demoted, not deleted.

## Protected critical path
`trailmend/core/*`, `trailmend/search/*`, `trailmend/loop/*`, `trailmend/graph/queries.py`, `trailmend/eval/arms.py`, `trailmend/eval/curve.py`. No change merges without the gate passing.

## Load-bearing invariants (each has a named test)
1. One confirmation never outweighs k_q blames.
2. Quarantine never fires on an edge that is on a gold path confirmed in the same round.
3. rollback(apply(change)) restores the exact prior edge state (property test, and live in `make verify`).
4. A quarantined edge is never used by search, including after a HydraDB restart.
5. A shortcut is retired when any hop on its `via_path` is quarantined.
6. Random controls make the same number and magnitude of changes as `mend_full` in the same round.
7. Gap-fill never selects documents by the gold answer.
8. Held-out questions never feed the Mend.

## Gate
`make gate` from a clean clone: ruff check + format check, pyright strict, pytest (unit), web typecheck + lint + build, evidence manifest check (every README number resolves to an evidence row). `make verify` runs the live HydraDB checks.

## Proof priority
1. Curve: mend_full vs frozen vs random controls, 3 seeds, held-out.
2. Plain-store ablation flat.
3. Non-regression per round, traced to receipts.
4. Quarantine precision/recall on planted faults.
5. Live rollback.
6. Concurrent load test.
7. Mechanism decomposition.
8. Second dataset.
