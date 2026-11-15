# Submission

Deadline: **2026-11-16 09:00 IST** (03:30 UTC). Nothing here is ticked from intention — each line names the command
or the file that shows it is true.

## Mapping (PRD §18)

| What | Where | State |
|---|---|---|
| Live app | https://trail-mend.vercel.app | DEPLOYED. All five pages answer 200; screenshots at 390px in `evidence/demo/f-*.png` |
| API | https://trailmend-production-ee2e07ff.up.railway.app | DEPLOYED. `GET /v1/ready` → `{"graph_writable":true}`; serves the curve and every evidence file |
| Repo | https://github.com/DrApkFile/TrailMend | public |
| Loom | linked at the top of README.md | script in `docs/LOOM_SCRIPT.md`, NOT RECORDED |
| Posts | `evidence/posts.md` with URLs | figures filled from the evidence; NOT POSTED |

## Definition of finished (PRD §17)

| # | Requirement | How it is shown | State |
|---|---|---|---|
| 1 | Clean clone → `make gate` passes | `scripts/presubmit.sh` clones HEAD and runs it | PASS at f94a9d9, live tests on, all 14 checks clean. Run it once more with the Loom link in place |
| 2 | Live link works from a fresh browser | the Vercel URL | PASS: five pages 200, driven in Chromium at 390px, including asking, judging and rolling back |
| 3 | Curve and controls published for 3 seeds | `evidence/curve.jsonl`, `evidence/curve_v2.jsonl` and both SVGs | PASS for run 1: 162 rows, seeds 1, 7, 42, run `01f1f6f-06b10c13`. Run 2 is run `2b192cc-580ae8dc` on dataset v2, seeds 1, 7, 42, seven arms |
| 4 | Every README number links to an evidence file | the block between `numbers:start`/`numbers:end`, written by `trailmend.eval.report` | PASS: filled, each file linked with its sha256 |
| 5 | Loom recorded | the link at the top of README.md | PENDING — needs the repo owner |
| 6 | Posts live and logged | the "Posted" table in `evidence/posts.md` | PENDING — drafts are ready, the handle needs checking |
| 7 | Submitted before 09:00 IST | the submission form | PENDING |

## What is left

1. Finish run 2: the sweep, then `trailmend.eval.oracle_run`, `trailmend.eval.analyse_v2`,
   `trailmend.eval.plain_run --v2` and `trailmend.eval.report`, then push so Railway and Vercel serve the new files.
2. Reset the hosted demo graph once, so it carries dataset v2 like the published run:
   `set -a; . ./.env.prod; set +a; ./scripts/demo_reset.sh`.
3. Record the Loom from `docs/LOOM_SCRIPT.md` and put the link in the README table and in `evidence/posts.md`. The
   script's figures are run 1's and need re-reading off the page for run 2.
4. Check HydraDB's handle on the hackathon page, post both drafts from `evidence/posts.md`, log the URLs in its
   "Posted" table. Their figures are run 1's and need the same treatment.
5. `make hydra-up` if the local HydraDB is down, then `bash scripts/presubmit.sh` with the live tests on, and expect
   every check to pass.
6. Submit.

Optional, and not needed for any claim made: a larger E6 run. The one on record was sized to stay under the public
60-asks-a-minute limit; a bigger one needs `TRAILMEND_ASK_RATE_PER_MINUTE` raised on the Railway API service first,
and should be lowered again afterwards.

If a judge has been judging on the hosted site and you want it clean again:
`set -a; . ./.env.prod; set +a; ./scripts/demo_reset.sh`. The reset writes its own receipt and never touches the
evaluation evidence. If the demo graph is ever empty — a fresh HydraDB, say — the API loads G0 itself at startup,
so this is a convenience, not a dependency.

## Two runs, both published

Run 1 is on record as a failure and is not re-run, re-scored or withdrawn. Run 2 is a second run beside it, on
dataset v2, with its own hypotheses fixed in PRD §3.2 **before** any of it was built, each change traced to
`docs/RUN1_DIAGNOSIS.md`. The two runs use different generated data, so only comparisons inside a run are claims;
the front page, the README and `/evidence` all say so, and both curves are drawn.

The sweep ran at commit `2b192cc` (the commit is in the run id). Commits after it changed the website, the README
writer, the submission docs and the demo's data version — never the measurement code or the config, whose digest is
the second half of the run id.

## What is published as a failure, not hidden

Three of the five hypotheses preregistered for run 1 failed and stay on the site with the rule each was decided by,
in `evidence/hypotheses.json`, in the README and on `/evidence`:

- **H1 FAIL** — the full Mend ends round 5 at 84.2% against 83.9% at round 0, +0.4 points, inside the 2.9-point
  spread between seeds at round 0. One of the three seeds did not move at all.
- **H4 FAIL** — quarantine recall is 1.00, 0.92, 0.92, but the false-quarantine rate is 0.118, 0.188, 0.071 against
  a budget of 0.1.
- **H5 FAIL** — one round broke 3.25% of previously-correct held-out answers against a budget of 2%.

What survives: gap-fill is the only mechanism that moves accuracy on its own (+2.2 points, every seed positive);
targeted change beats random change on both levers with the controls matched on the number and size of changes per
round (reweight −1.9 against −7.6, quarantine 0.0 against −2.5); and the graph answers 83.9% where the
document-only baseline answers 24.6%.

The limitation that bounds H1 is in the README: when a planted fault points a link at the wrong target, the true
link is not in the corpus, so quarantining the bad edge turns a wrong answer into a refusal rather than a correct
one. Only the withheld-edge faults have a document that gap-fill can find.
