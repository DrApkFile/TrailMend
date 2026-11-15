# Submission

Deadline: **2026-11-16 09:00 IST** (03:30 UTC). Nothing here is ticked from intention — each line names the command
or the file that shows it is true.

## Mapping (PRD §18)

| What | Where | State |
|---|---|---|
| Live app | Vercel URL | not deployed — needs `vercel login` (A2) |
| API | Railway URL | not deployed — needs `railway login` (A1) |
| Repo | public GitHub | — |
| Loom | linked at the top of README.md | script in `docs/LOOM_SCRIPT.md`, not recorded |
| Posts | `evidence/posts.md` with URLs | drafted, blanks unfilled, not posted |

## Definition of finished (PRD §17)

| # | Requirement | How it is shown | State |
|---|---|---|---|
| 1 | Clean clone → `make gate` passes | `scripts/presubmit.sh` clones HEAD and runs it | PASS at 7fb58dc, `SKIP_LIVE=1` |
| 2 | Live link works from a fresh browser | open the Vercel URL | blocked on A1/A2 |
| 3 | Curve and controls published for 3 seeds | `evidence/curve.jsonl`, `evidence/curve.svg` | seeds 1 and 7 of 3 recorded; sweep running |
| 4 | Every README number links to an evidence file | the block between `numbers:start`/`numbers:end`, written by `trailmend.eval.report` | fills when the sweep ends |
| 5 | Loom recorded | the link at the top of README.md | pending |
| 6 | Posts live and logged | the "Posted" table in `evidence/posts.md` | pending |
| 7 | Submitted before 09:00 IST | the submission form | pending |

## The order the rest has to happen in

1. The E1 sweep finishes (3 seeds × 9 arms × 6 rounds into `evidence/curve.jsonl`).
2. Re-run the two contaminated seed-arms. Seed 7 `random_quarantine` as well as seed 1 `reweight_only`: the live
   and API suite was run against the same graph while that arm was in flight (02:11-02:16 on 2026-11-15), because a
   hand-written lock carried a pid that had already exited. Every other arm resets the graph when it starts, so the
   damage is confined to the arm that was running.
   `uv run python -m trailmend.eval.rerun 7 random_quarantine "the live and API tests ran against this graph while this arm was in flight"`
3. Re-run seed 1 `reweight_only`: its rows were written while the API tests wrote judge receipts and a rollback into
   the same graph. One command, which keeps the contaminated rows on record under `evidence/superseded/` with the
   reason and reuses the arm index the sweep used so the RNG stream is the same:
   `uv run python -m trailmend.eval.rerun 1 reweight_only "the API tests wrote judge receipts and a rollback into the same graph during this arm"`
4. `uv run python -m trailmend.eval.analyse` → curve.svg, non_regression.json, quarantine.json, mechanisms.json,
   hypotheses.json, run_manifest.json. It refuses any seed-arm whose held-out tape is missing.
5. `uv run python -m trailmend.eval.report` → the README numbers block.
6. `railway login`, then A1: bucket, HydraDB service on the pinned digest, API service, `GET /v1/ready` →
   `graph_writable: true`, restart HydraDB and check again. Steps in `deploy/railway/README.md`.
7. `vercel login`, then A2: deploy `apps/web` with `TRAILMEND_API=<railway api url>`; check in a fresh browser and
   at 390px wide; confirm no API URL appears in `.next/static`.
8. E6 against the deployment, both passes. It needs the deployment's admin token in the environment and never
   prints it: put it in `.env.prod` (gitignored) as `TRAILMEND_ADMIN_TOKEN=...`, then
   `set -a; . ./.env.prod; set +a; uv run python -m trailmend.eval.load https://trailmend-production-ee2e07ff.up.railway.app`
   → `evidence/latency.json`, then re-run report. Afterwards reset the demo graph with
   `set -a; . ./.env.prod; set +a; ./scripts/demo_reset.sh` so judges start from the loaded graph.
9. Record the Loom from `docs/LOOM_SCRIPT.md`; put the link at the top of the README.
10. Fill the blanks in `evidence/posts.md` from the evidence files, check HydraDB's handle, post, log the URLs.
11. `bash scripts/presubmit.sh` with the live tests on (needs `make hydra-up`), expect every check to pass.
12. Submit.

## What is published as a failure, not hidden

The preregistered hypotheses are decided by the rules in `evidence/hypotheses.json`, and the ones that fail stay on
the site with their numbers. On seed 1's finished rows, H4 fails on the false-quarantine rate (0.1176 against a
threshold of 0.1, at recall 1.0) and H5 fails on the worst round's break share (0.0314 against 0.02). The final
verdicts are over three seeds and are whatever the run says.

The limitation that bounds H1 is in the README: when a planted fault points a link at the wrong target, the true
link is not in the corpus, so quarantining the bad edge turns a wrong answer into a refusal rather than a correct
one.
