> Historical handoff. Both inherited runs have now completed; see `docs/SUBMISSION.md` for current results, replication limitations and remaining owner actions. Technical handoff completed: deployment checked, screenshots saved, hosted demo reset, and clean-clone acceptance passed at `a1b997a`. Recording the Loom, posting and submitting remain owner actions.

# Handoff — TrailMend, 2026-11-15 ~22:35 Lagos

Deadline: Nov 16 04:30 Lagos (09:00 IST). Repo: `/home/kingghidorah/Documents/projects/bounties/trailmend/trailmend`,
branch `master`, push with `git push origin master` (Railway API and Vercel web redeploy on push; never reconfigure
them). Read `CLAUDE.md` and `docs/BUILD_CONTRACT.md` first. Rule: publish whatever the runs produce; never hand-type a
number; no code changes are needed for what is left unless something below breaks.

## Two runs are executing right now — do not start anything else on HydraDB, do not kill them

1. **MetaQA** (run id `ddf430f-2260187b`, pid in `evidence/.measuring.json`), on the local HydraDB at :8443.
   Seeds 1, 7, 42 in sequence; expected to finish around 01:15 Lagos.
   Log: `/home/kingghidorah/.claude/jobs/2d5df787/tmp/metaqa_run.log`.
   It writes `evidence/curve_metaqa.jsonl`, `evidence/metaqa/`, `evidence/runs/ddf430f-2260187b-*` and, at the very
   end, `evidence/oracle_metaqa.json`. It is finished when that last file exists and the process has exited.
2. **Unweighted-search arm** on Northwind v2 (run id `9ae6601-580ae8dc`), on a second HydraDB at :8444
   (container `trailmend-hydradb-2`, its S3 stand-in is `moto_server` on :5001), running inside a git worktree at
   `/home/kingghidorah/.claude/jobs/2d5df787/tmp/wt-unweighted`. Expected to finish around 23:10.
   Log: `/home/kingghidorah/.claude/jobs/2d5df787/tmp/unweighted.log` (done when it prints `wrote 36 rows`).
   **Its output is in the worktree, not in the repo.** When it is done, copy into the repo:
   `evidence/curve_v2_unweighted.jsonl` and every `evidence/runs/9ae6601-580ae8dc-*` directory.
   Do not delete Claude job `2d5df787` before that copy.

**Check first whether they are still alive**: `pgrep -af 'trailmend.metaqa.run|trailmend.eval.run'` and
`cat evidence/.measuring.json`. At 22:35 both were (MetaQA seed 1 `full_v2` round 2, Hits@1 55.6% → 70.3%; unweighted
on seed 7). If they are alive, wait for them. If they are gone and their outputs are incomplete, run them yourself,
one after the other on the HydraDB at :8443 (`make hydra-up` if it is down):

- MetaQA (about 3 hours): delete `evidence/curve_metaqa.jsonl`, `evidence/metaqa/` and `evidence/runs/ddf430f-*`,
  then `uv run python -m trailmend.metaqa.run 1 7 42`. Complete = 54 rows in `evidence/curve_metaqa.jsonl` and
  `evidence/oracle_metaqa.json` exists. The run id will carry the commit you start it from; that is fine.
- Unweighted arm (about 50 minutes): delete any partial `evidence/curve_v2_unweighted.jsonl`, then
  `uv run python -m trailmend.eval.run --unweighted 1 7 42`. Complete = 36 rows. Run this way it writes straight
  into the repo, so skip the copy in step 1.

If time runs out before MetaQA can complete, publish it as `not_run` with that reason in the README, `DECISIONS.md`
and `docs/SUBMISSION.md`, and still do every other step; the benchmark paragraph already says "has not been run".

If either dies mid-way, restart the same command from the same place (MetaQA: `uv run python -m trailmend.metaqa.run 1 7 42`
after deleting `evidence/curve_metaqa.jsonl` and `evidence/runs/ddf430f-*`; partial rows must never be published) and
record the restart in `DECISIONS.md`.

## State

Pushed (HEAD `9ae6601`): run 2 published beside run 1 (H1' H2' H3' H5' H7' H8' PASS, H4' H6' FAIL; no arm dropped —
six graph arms plus `plain_store` are the planned seven); `GET /v1/truth` and `/truth`; new landing page; MetaQA
loader, manifest and preregistration (PRD §3.3); `full_unweighted` arm. Live API verified serving run 2 with the
manifest's run id and sha.

Uncommitted in the working tree, lint- and type-clean, unit tests passing:
`README.md` (benchmark block markers, three-criteria table, MetaQA credit, limitations),
`src/trailmend/eval/benchmark.py` (the paragraph generator), `src/trailmend/eval/report.py` (MetaQA and unweighted
sections), `src/trailmend/eval/analyse_unweighted.py`, `.gitignore`. Commit these first.

Known result to report honestly: the unweighted loop scores **higher** than the weighted one on Northwind v2
(seed 1: 83.2% at round 0, ~90% after, against 76.8% → 87%). Cause: for questions whose answer is a set, support-derived
costs rarely tie, so weighted search returns only the cheapest member. `analyse_unweighted` measures that split and the
benchmark sentence already says "above" or "below" from the data. Do not soften or drop it.

## Remaining steps, in order

1. Commit the uncommitted files. When the unweighted run ends: copy its outputs in (see above), then
   `uv run python -m trailmend.eval.analyse_unweighted`. Stop the second instance:
   `docker rm -f trailmend-hydradb-2; pkill -f 'moto_server --host 127.0.0.1 --port 5001'`;
   `git worktree remove --force /home/kingghidorah/.claude/jobs/2d5df787/tmp/wt-unweighted`.
2. When MetaQA ends: `uv run python -m trailmend.metaqa.plain_run 1 7 42`, then
   `uv run python -m trailmend.metaqa.analyse` (decides M1–M5, checks INV6).
3. `uv run python -m trailmend.eval.report` — fills the README numbers block and the benchmark paragraph, writes
   `evidence/benchmark.json`, `benchmark_facts.json`, `dataset_summary_v2.json`. Read the paragraph once for sense.
4. `DECISIONS.md`: add rows for (a) the unweighted arm being an extension at commit `9ae6601` with the same config
   digest, run on a second HydraDB instance of the same pinned image, its frozen arm reproducing run 2's; (b) the
   unweighted result and its cause; (c) MetaQA's 22:00 time box missed because the session was idle 17:58–22:00.
5. Update `docs/LOOM_SCRIPT.md` with the final numbers and the demo moment: ask "Who is on call for the Delta team?",
   press wrong three times, the answer flips from Selin Tadesse to Bao Maeda, then show the fault on `/truth`.
   Update `docs/SUBMISSION.md` and tick `docs/TASKS.md` H6.
6. `make gate`; with HydraDB free, `make verify` (the two new `/v1/truth` API tests in `tests/api/test_api.py` have
   not been run live yet). Commit, `git push origin master`.
7. After deploy: check `https://trail-mend.vercel.app/` and `/truth`, and that
   `https://trailmend-production-ee2e07ff.up.railway.app/v1/evidence/benchmark` and `/v1/evidence/curve-metaqa`
   are `available: true`. Save landing-page screenshots at 1440px and 390px into `evidence/demo/`
   (a Playwright script that works here: `/home/kingghidorah/.claude/jobs/2d5df787/tmp/shots/shot.mjs`,
   `node shot.mjs <url> <out.png> <width> <height> view|full <wait_ms>`). Kill the local `next start` on :3111.
8. Reset the hosted demo graph: `set -a; . ./.env.prod; set +a; ./scripts/demo_reset.sh` (never print the token).
9. `bash scripts/presubmit.sh` from a clean clone; fix what it reports; push.

## Left for the repo owner

Record the Loom and put its URL in the README table and in the Vercel env var `TRAILMEND_DEMO_URL` (the header's
"Watch the demo" button links to the repo until then); post from `evidence/posts.md`; submit.
