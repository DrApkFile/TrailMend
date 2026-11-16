# Handoff 2 — parallel work, written Mon 2026-11-16 04:00 Lagos

The owner records the Loom at **08:00 Lagos**. Anything that changes what the Loom shows (the landing page, the
replay, the wording) must be pushed and deployed by **07:30**. Measurement runs may keep going after that and are
published when they finish.

Repo: `/home/kingghidorah/Documents/projects/bounties/trailmend/trailmend`, branch `master`, HEAD `d41b5b8` (the UI
redesign is in). `git push origin master` redeploys Railway (API) and Vercel (web); never reconfigure either.
Read `CLAUDE.md` and `docs/BUILD_CONTRACT.md` first. Binding rules: never type a number by hand, publish whatever a run
produces, a failed hypothesis stays published, never overwrite a published run's files, never print `.env.prod`.

Two agents work at the same time. **They must not share a HydraDB, an evidence file, or a working tree.**

| who | task | HydraDB | where |
|---|---|---|---|
| Claude | A. clean replication of run 2 + unweighted arm | `:8443` (the compose instance, `trailmend-hydradb-1`) | the main repo, `master` |
| Claude | B. "Watch it learn" replay on the landing page | none | the main repo, `master` |
| Claude | C. polish | none | the main repo, `master` |
| Codex | D. run 3: abstain instead of guessing | a second instance on `:8444` | a git worktree on branch `run3` |

Current published state: run 1 (FAIL, stays), run 2 `26b5469-580ae8dc` (H1' H2' H3' H5' H7' H8' PASS, H4' H6' FAIL),
MetaQA `ddf430f-2260187b` (M1 M2 M3 M5 PASS, M4 FAIL; Hits@1 55.3% → 71.5%), unweighted extension `9ae6601-580ae8dc`
(marked provisional because its frozen arm did not reproduce run 2's: 1–4 fewer correct per seed of 340 — run 2's
shared graph carried stray edges from earlier runs; see DECISIONS 2026-11-16).

---

## A (Claude). Clean replication of run 2, then the unweighted arm — start this first, it is ~5 h of machine time

Goal: remove "provisional". Run 2 stays published as it is; the clean run is published **beside** it as a
replication, never in place of it.

1. Add a DECISIONS row first: why the replication exists (stray edges in the shared graph made run 2's frozen arm
   1–4 questions per seed higher than a clean graph), that run 2 stays published, that the replication uses the same
   config digest and arms, that it decides nothing preregistered and is reported as a replication.
2. Code (small): give the replication its own curve file, `evidence/curve_v2_clean.jsonl`, the same way
   `CURVE_V2_UNWEIGHTED` is done in `src/trailmend/eval/curve.py` (`EXTENSIONS`) and `src/trailmend/eval/run.py`
   (`--unweighted` → `main(..., out=...)`). Add a `--clean` flag that runs `RUN2_ARMS` **plus** `full_unweighted`
   with `plain_store`, writing to the new file. Commit before running (the commit is in the run id).
3. Empty the store so nothing from earlier runs exists: `./scripts/hydra_down.sh`, `rm -rf hydradb-data/cache`,
   `./scripts/hydra_up.sh`. (Confirm with Codex's instance that you are only touching `:8443`/`:5000`.)
4. `nohup uv run python -m trailmend.eval.run --clean 1 7 42 > /tmp/clean.log 2>&1 &`. Complete = 3 seeds × 8 arms
   × 6 rounds = **144 rows**. Do not poll in a loop that spends tokens; check every ~30 min.
5. When done: run the v2 oracle ladder against the clean graph if `analyse_v2` needs it for the captured share
   (`trailmend.eval.oracle_run` writes `oracle_v2.json` — do **not** overwrite run 2's; give it a `_clean` name),
   then a small analysis that writes `evidence/replication_v2_clean.json`: per seed, frozen and full_v2 against run 2,
   the paired test of full_v2 vs frozen on the clean run, and full_unweighted vs full_v2 **on the same clean graph**.
   That last comparison is the one that replaces the provisional one.
6. Update `trailmend.eval.report` and `trailmend.eval.benchmark` so the README and the benchmark paragraph use the
   clean comparison for the unweighted sentence and drop "provisional". Serve the new files from
   `src/trailmend/api/routes_evidence.py` (`SERVABLE` / `CURVES`). Expect the honest finding to stand: unweighted
   search scored **higher** than weighted on run 2's data (set answers rarely tie under support-derived costs).
   Report it as it comes out.

## B (Claude). "Watch it learn" replay — build while A runs; must be live by 07:30

A button in the landing page (a section right after the hero) that replays a recorded run round by round, reading
only recorded evidence, writing nothing:
- Source: run 2's `full_v2` and `frozen` held-out tapes and receipts for one seed (seed 1), or MetaQA seed 1. Add an
  API route `GET /v1/replay/{dataset}/{seed}` that returns, per round: held-out accuracy (frozen and full_v2), counts of
  reweights / quarantines / gap-fills, and up to ~6 example receipts (edge names, before → after cost, kind). Names
  come from the dataset the app already builds (`Live.built` for Northwind); keep MetaQA out if it needs the raw
  files on Railway (they are not deployed).
- UI: a client component — play/pause, a round scrubber 0→5, a big accuracy number that counts up, the frozen line
  staying flat beside it, receipt cards popping in, a red link turning green when a quarantine or a correction lands.
  Respects `prefers-reduced-motion` (then it shows the final round statically). Works at 390px. `—` until data loads.
- Style: match the canon-capture look already on the landing page (`canon-captures/` for reference, rounded
  bordered cards, mono labels, green `mend` / red `bad` tokens in `apps/web/app/globals.css`).
- Check with `npm run typecheck && npm run lint` in `apps/web`, and one Python unit test for the route's shape.

## C (Claude). Polish — 30 min, before 07:30

- One-line pitch, the same everywhere (landing subtitle, README top, `layout.tsx` description, pricing):
  *"Your service catalogue is quietly wrong. TrailMend finds out from its own answers and fixes it, with a receipt
  for every change."*
- Landing: the first stat card the eye hits should be the MetaQA gain (public data). It is already read from
  the API; just reorder.
- Header "Watch the demo" links to the repo until the Loom exists; the owner sets `TRAILMEND_DEMO_URL` on Vercel
  after recording.
- Push. Confirm `https://trail-mend.vercel.app/` renders and the replay plays.

## D (Codex). Run 3 — abstain instead of guessing

Goal: make wrong answers fall while right answers hold, honestly, as a **new preregistered run**. M4 and H6' stay
failed; run 3 does not rewrite them.

1. Work in a separate tree: `git worktree add ../trailmend-run3 -b run3`, copy `.env` in, symlink
   `data/external/metaqa` in. Never edit files in the main tree; merge `run3` into `master` only when done, after
   Claude's commits (rebase on `origin/master`, resolve, push).
2. Own HydraDB, so Claude's clean run is untouched: a second container on `:8444` with its own S3 stand-in on
   `:5001` and its own data dir `hydradb-data-run3/` (gitignored). The exact `docker run` used last time:
   ```
   mkdir -p hydradb-data-run3/cache && printf 'local-development-token-32-bytes' > hydradb-data-run3/auth-token
   nohup uv run moto_server --host 127.0.0.1 --port 5001 > hydradb-data-run3/moto.log 2>&1 &
   curl -X PUT http://127.0.0.1:5001/hydradb
   docker run -d --name trailmend-hydradb-run3 --network host --user "$(id -u):$(id -g)" -v "$PWD/hydradb-data-run3:/data" \
    -e CLOUD_PROVIDER=aws -e AWS_BUCKET_NAME=hydradb -e AWS_DEFAULT_REGION=us-east-1 -e AWS_ENDPOINT=http://127.0.0.1:5001 \
    -e AWS_ALLOW_HTTP=true -e AWS_ACCESS_KEY_ID=dev -e AWS_SECRET_ACCESS_KEY=devsecret123 -e GRAPH_NAMESPACE=default \
    -e GRAPH_ID=default -e GRAPH_CELL_ID=cell-0 -e GRAPH_CELLS=cell-0 -e GRAPH_NODE_ID=node-0 \
    -e GRAPH_HTTP_ADDR=127.0.0.1:8444 -e GRAPH_BOLT_ADDR=127.0.0.1:7688 -e GRAPH_ADMIN_ADDR=127.0.0.1:9091 \
    -e GRAPH_BOLT_NODE_ADDRESSES=node-0=127.0.0.1:7688 -e GRAPH_ADVERTISED_BOLT_ADDR=127.0.0.1:7688 \
    -e GRAPH_DATA_CACHE_DIR=/data/cache -e GRAPH_AUTH_TOKEN_FILE=/data/auth-token -e GRAPH_ALLOW_PLAINTEXT=true \
    -e GRAPH_USAGE_REPORT_ENABLED=false -e RUST_MIN_STACK=33554432 \
    ghcr.io/hydra-db/hydradb@sha256:ab71d651fefee13ebb23eb56d72316065bdca563ff7587442e07be663f2bf880
   ```
   Run with `TRAILMEND_HYDRA_URL=http://127.0.0.1:8444`. The measuring lock `evidence/.measuring.json` is per tree,
   so the worktree has its own.
3. **Preregister before any code that answers**: add PRD §3.4 and a DECISIONS row. The mechanism: the answer path
   refuses (`low_confidence`, counted as a refusal, not a wrong answer) when the best path's cost exceeds a threshold,
   or when it uses a gap-filled edge that has never been confirmed. Fix the threshold now from **training data only**
   (e.g. a quantile of the costs of correct train answers at round 0), never from held-out. Hypotheses, e.g.:
   R1 held-out wrong-answer rate falls ≥ 40% from round 0 to round 5 on every seed/dataset; R2 held-out accuracy at
   round 5 is no more than 2 points below the non-abstaining `full_v2` of the same run; R3 the abstaining frozen graph
   is not better than the abstaining full Mend (paired). Arms: `frozen_abstain`, `full_v2_abstain` (and the existing
   `full_v2` for R2) on Northwind v2 seeds 1 7 42 and MetaQA seeds 1 7 42, 5 rounds.
4. Own evidence files only: `curve_v3*.jsonl`, `hypotheses_v3.json`, etc. Never write `curve_v2*`, `curve_metaqa*`,
   `hypotheses_v2/metaqa`. Wire them into the report, API `SERVABLE`, and one landing-page line ("Run 3: ...")
   only after the runs finish, with `—` until then.
5. Timing: MetaQA is ~1 h per seed for three arms; if run 3 cannot finish both datasets, do Northwind only and say
   so. Publish whatever comes out, pass or fail.

## Both

- `make gate` before each push; `make verify` only on your own HydraDB, and only when your measuring lock is free.
- Commit small, behavioural subjects; push; if the push is rejected, `git pull --rebase origin master` and retry.
- Leave the hosted demo graph as it is (Codex reset it) unless the replay needs nothing from it — it does not.
- At the end, each writes a short status at the bottom of this file: what finished, run ids, what failed.

## Codex status — run 3 completed, 2026-11-16

Separate worktree `trailmend-run3`, isolated HydraDB `:8444` and S3 `:5001`. Measured `v3-9fe1e3a-aab4f1f7`; the complete curve and training-only calibration are published with R1 FAIL; R2 FAIL; R3 PASS. MetaQA run 3 is explicitly `not_run`. No historical run files or hosted demo graph were changed. Original measurement code is preserved on `origin/run3`; integration rebases onto Claude's commits. API/report/landing-line wiring is included. The owner requested a follow-up repair of feedback starvation and set-answer selection; that requires a new preregistration and measurement, preserving this run's failures.

Run-3 integration checks: gate passed, 288 unit tests and 53 live tests on the isolated instance; original measured commit remains on `origin/run3`. Verification: `evidence/verification_v3.json`.

Run 3 is deployed: summary, hypotheses and curve API hashes match this worktree; landing line shows both failures and R3 PASS. Mobile check has no overflow or console errors. Proof: `evidence/demo_v3/`. Rebased integration gate also passes. The hosted demo was not reset.
