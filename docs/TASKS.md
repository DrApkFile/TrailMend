# TASKS — ordered build plan

Work top to bottom. Each task lists its PRD section and acceptance. Tick `[x]` only when acceptance passes and
`make gate` is green. Record each demo step as soon as it works (screenshot or short clip into `evidence/demo/`).

## Done (scaffold)
- [x] T00 Repo, pinned deps, strict lint/types, CI gate.
- [x] T01 HydraDB client: unique query_id, bookmarks, writability probe, fail-closed errors, strict decoding.
- [x] T02 Named queries: batch upserts, edge read/update/delete, move edge (quarantine), weighted paths.
- [x] T03 Pure core: credit, update rule, quarantine rule, receipts, rollback inverse; invariant tests INV1–INV3.
- [x] T04 Live contract tests: writable, route flips on cost change, INV4 quarantined edges never searched.
- [x] T05 API skeleton: `/healthz`, `/v1/ready` (verified live).

## Phase A — hosting first (PRD §5, deploy/railway/README.md)
- [x] A1 Railway: bucket + HydraDB service + API service. Acceptance: public `GET /v1/ready` → `graph_writable: true`;
  restart the HydraDB service, then `/v1/ready` still true. Record image digest in REALITY_SPIKES.md.
  DONE 2026-11-15, deployed by hand by the repo owner. `https://trailmend-production-ee2e07ff.up.railway.app/v1/ready`
  → `{"graph_writable":true}` (HTTP 200 in 1.3s, verified from this machine), `/healthz` → `{"status":"ok"}`. The
  restart test was run by the owner: the HydraDB service was restarted and `/v1/ready` still answered true with
  writes still landing — the Railway bucket gives the conditional writes a local volume cannot (S32). The image is
  the digest pinned in `docker-compose.yml` and recorded in S15. What the deployment needed that the docs did not
  say: plaintext without TLS (S27), IPv6 listen addresses (S28), `/tmp` instead of a volume with the token written by
  the start command (S29, S26), both services in one project and environment (S30), and
  `TRAILMEND_HYDRA_URL=http://hydradb.railway.internal:8443` with the token as `${{hydradb.HYDRA_TOKEN}}` (S31).
- [x] A2 Vercel: `apps/web` Next.js app (create with the current stable `create-next-app`, TypeScript strict,
  App Router). One page that server-fetches `/v1/ready` and shows the state. Acceptance: live URL works in a fresh
  browser; API never called from the browser.
  DONE 2026-11-15, deployed by hand by the repo owner: `https://trail-mend.vercel.app` answers HTTP 200 and its
  server-rendered HTML carries `graph_writable true` with `source GET /v1/ready, server-side` (verified from this
  machine with a plain HTTP client, so no browser JavaScript is involved). The deployment is from before F2-F5, so
  `/ask`, `/mend`, `/evidence` and `/pricing` are still 404 there until the next push. Built and proven locally: Next.js 16.4.6,
  App Router, TypeScript strict plus `noUncheckedIndexedAccess`; `/` is a server component that fetches
  `GET /v1/ready` through `lib/api.ts` (guarded by `server-only`); against the live API it renders
  `graph_writable true`, and with the API down it renders `—` and the code `api_unreachable`, never a fake success.
  `TRAILMEND_API` unset throws by name. No API URL appears in `.next/static`, so the browser never calls the API.
  Screenshots at 390px: `evidence/demo/a2-ready-390px.png`, `evidence/demo/a2-api-down-390px.png`.
  `make gate` now runs web typecheck + lint + build.

## Phase B — the dataset (PRD §4)
- [x] B1 `trailmend/data/northwind.py`: seeded generator for the truth graph T. `generate(seed) -> TruthGraph`.
  Sizes: ~400 Person, ~40 Team, ~120 Service, ~300 Alert, ~80 Customer, ~60 Incident. Types and relations per PRD §4.
  Deterministic: same seed → byte-identical JSON. Test: determinism, referential integrity, every Alert reaches a
  Person within 3 hops via ALERTS_ON → OWNED_BY → ON_CALL.
  Done 2026-11-14: seed 7 gives 1160 nodes / 1766 edges at exactly the planned sizes, plus 90 Runbook and 70 Repo
  (PRD §4 lists both). 13 tests in `tests/unit/test_northwind_generator.py`, including a byte-identity check run in
  a fresh interpreter under `PYTHONHASHSEED=12345`. Relation directions and names are recorded in DECISIONS.
- [x] B2 Faults (`faults.py`): from T, produce ingested graph G0 + `faults.json`: wrong edges (~8% of OWNED_BY /
  ON_CALL swapped to a plausible wrong target), missing edges (~6% withheld into the not-yet-ingested pool),
  alias duplicates (~5% of services get a second node with an alias name), one conflated person. Test: every fault
  is declared; G0 = T − missing + wrong (exactly).
  Done 2026-11-14: seed 7 gives G0 1661 edges / 1165 nodes from T 1766 / 1160, pool 105; 13 wrong, 105 missing,
  6 alias duplicates, 1 conflation. Each fault declares the exact edges it removed and added, and replaying only
  the declaration over T reproduces G0's edge set. Faults are disjoint — no edge carries two. 13 tests in
  `tests/unit/test_planted_faults.py`.
- [x] B3 Documents (`documents.py`): render every G0 edge and every pool edge into short text documents from
  templates (ticket, runbook line, chat message). Each doc lists its entity mentions. Deterministic.
  Done 2026-11-14: seed 7 renders 1661 ingested and 105 pool documents, one per edge, from 30 templates (three
  phrasings per relationship type across ticket / runbook / chat). Both endpoint names appear verbatim in every
  text, so BM25 in the plain-store arm has something to match. 8 tests in `tests/unit/test_documents.py`.
- [x] B4 Questions (`questions.py`): templates with gold answers computed on T (not G0), 1–3 hops, e.g.
  `page_owner` (Alert→Service→Team→Person), `service_owner_team`, `customer_affected_by_incident`,
  `escalation_contact`. ≥600 questions per seed. Test: gold answers come from T; each question names its seed entity.
  Done 2026-11-14: 10 templates, 850 questions for seed 7 (850 / 850 / 856 for seeds 1 / 7 / 42) — 470 one-hop,
  170 two-hop, 210 three-hop. Seven templates are single-answer, three are multi-answer. 12 tests in
  `tests/unit/test_questions.py`, including one that fails if the planted faults never change an answer.
  Dataset headroom, not a result: traversing G0 instead of T gets 16.1% / 18.4% / 20.4% of questions wrong on
  seeds 1 / 7 / 42, so a frozen round-0 graph starts about that far below the ceiling.
- [x] B5 Splits (`trailmend/eval/splits.py`): train/held-out ≈60/40 stratified by template and hops; no shared
  (seed entity, template) pair across splits. Test: INV8 held-out never reaches the loop (structural test).
  Done 2026-11-14: seed 7 splits 850 questions into 510 train / 340 held-out, exactly 60/40 inside every one of
  the 10 (template, hops) strata. Train and held-out are different types (`TrainQuestion`, `HeldOutQuestion`) with
  no conversion between them, and a structural test scans `src/trailmend/` and fails if any module other than
  `eval/splits.py` constructs a `TrainQuestion`. 13 tests in `tests/unit/test_splits.py`.
  Still to come with D2: the round runner must take `TrainQuestion` in its signature, so held-out questions cannot
  be passed to it at all. INV8 is not fully proven until that test exists.

## Phase C — load and search (PRD §6, §7 steps 1–2)
- [x] C1 Loader: write G0 into HydraDB with batch upserts (≤1000 rows per batch), every edge `cost=1.0`.
  Acceptance (live): re-load is idempotent (edge counts unchanged); load time recorded in `evidence/load.json`.
  Done 2026-11-14 against local HydraDB (`make hydra-up`). Each seed writes 1165 nodes and ~1660 edges in 18
  batches; into an empty store the first load adds exactly what it wrote and a re-load adds 0 nodes and 0 edges.
  First-load times 1.26 / 1.09 / 1.22 s for seeds 1 / 7 / 42, re-loads 0.75 / 0.86 / 0.78 s — host-local numbers,
  not the Railway figures the README will need. `evidence/load.json` is written by `make evidence-load`.
  4 live tests in `tests/live/test_loader.py`. Counting needed `count(*)` rather than `count(n)` (S19).
- [x] C2 Seeding (`search/seed.py`): question → exactly one entry entity (exact name/alias, then token match);
  0 → `no_seed`, tie → `ambiguous_seed`. Pure, tested.
  Done 2026-11-14: pure, no I/O. Longest exact name-or-alias match wins (so an alert beats the service name inside
  it), word boundaries stop `ledger` matching `ledgerbook`, then a rarity-weighted token fallback. On seed 7 all
  850 questions seed successfully and 849 land on the entity they name; the one that does not is the planted
  conflation resolving to the surviving node, which is the fault behaving as designed. 11 tests in
  `tests/unit/test_seeding.py`. Index builds in 0.2 s over 1165 nodes; 850 questions seed in 0.12 s.
- [x] C3 Search (`search/answer.py`): SSpaths from seed over the template's relTypes, `maxLen` from config,
  answer = lowest-cost node with the expected label; tie on cost → `ambiguous_answer`; returns the edge path.
  Detect truncation (result count == limit) → `budget_exceeded`. Live test on a small generated graph.
  Done 2026-11-14: the terminal node's label is read off the last relationship type, so no extra query is needed.
  SSpaths returns one cheapest path per reachable node. 8 pure tests in `tests/unit/test_search_answer.py` and
  4 live tests in `tests/live/test_search.py`, including the answer moving when the last hop's cost is raised and
  `Q_*` being unaskable. Search is ~28 ms per question against local HydraDB.
  Round 0 measured, not a claim about the Mend: seed 7 held-out (340 questions) answers 259 correct (0.762),
  17 wrong, 33 unreachable, 31 ambiguous.
- [x] C3a SETTLED 2026-11-14, before any Mend run (DECISIONS): a multi-answer template returns every answer tied
  at minimum cost (costs compared after rounding to 1e-9); correct = exact set match with gold, set-F1 alongside.
  Single-answer templates still refuse a tie. Credit for a set answer blames the chosen path of each wrong member,
  confirms the cheapest gold path of each missed gold member, and confirms the path of each correct member.
  Round 0 is re-measured under this rule for all 3 seeds; the earlier seed-7 figure of 0.762 stays in the evidence
  marked superseded, with the reason.

## Phase D — the Mend loop (PRD §7–§8)
- [x] D1 Graph state sync: read current EdgeState for edges on chosen/gold paths; apply planned changes via queries;
  receipts appended to `evidence/runs/<run_id>/receipts.jsonl` BEFORE effects. INV3 live: apply then rollback leaves
  the edge byte-identical.
  Done 2026-11-14: `graph/state.py` reads and writes EdgeState including the `recent` judgement window, which is
  now an edge property so blame survives rounds and restarts. `loop/journal.py` appends a receipt and fsyncs it
  before `loop/apply.py` touches the graph. 10 live tests in `tests/live/test_apply_and_rollback.py`, including
  INV3 for a reweight and for a quarantine (which moves the edge to `Q_*` and back).
  Reads are one round trip per edge: HydraDB rejects `UNWIND $rows` feeding a RETURN (S20).
- [x] D2 Round runner (`loop/round.py`): for each train question → answer → judge vs gold → `Outcome`; for wrong
  answers compute best gold path with SPpaths over active types; `plan_round`; apply; then evaluate held-out
  (read-only). Writes one row per (dataset, seed, arm, round) to `evidence/curve.jsonl`.
  Done 2026-11-14: `loop/round.run_round` judges the train split, turns each judgement into an `Outcome`
  (`loop/credit_round.py`, set-aware per C3a), looks up the cheapest gold path for each missed gold answer with
  SPpaths over the active types (`loop/gold.py`), plans with `core.update.plan_round`, applies through
  `loop/apply.apply` so every receipt is on disk before the graph moves, then scores held-out read-only.
  `eval/curve.py` appends the row. 3 live tests in `tests/live/test_round.py`: a full round's receipts match its
  applied changes one for one, a frozen round leaves 40 sampled edges byte-identical, and INV6 holds on a real
  plan. INV8's other half is now proven: `run_round` takes `Sequence[TrainQuestion]`, so a held-out question is a
  type error, asserted in `tests/unit/test_round_contract.py`. No curve has been produced yet.
- [x] D3 Policy seam (`loop/policy.py`): `MendPolicy` = full | reweight_only | quarantine_only | frozen |
  random_reweight | random_quarantine. Random arms use a seeded RNG, make the same number and magnitude of changes
  as `full` made in that round (INV6 test).
  Done 2026-11-14: `policy.shape` takes the plan `full` would have applied and returns what the arm applies, so
  every arm is measured against one plan built from the same credits. A random arm copies each planned change's
  signal tuple onto an edge drawn without replacement by the injected `random.Random` and prefixes its question
  ids with `random:` so a receipt can never read as real credit. INV6 passes before any curve: 11 unit tests in
  `tests/unit/test_mend_policies.py` (including a hypothesis sweep over plan shapes, and a pool too small being
  refused rather than quietly shrunk) plus the live test on a real plan. Each random arm mirrors the mechanism arm
  it controls rather than the whole plan, and `quarantine_only` cannot accumulate a `recent` window — both logged
  in DECISIONS.
- [x] D4 Shortcuts (path compression, PRD §7 step 7): promote a multi-hop path confirmed in ≥ promote_min_questions
  distinct questions to `SC_<TEMPLATE>`; retire when any hop is quarantined (INV5). Receipts for both.
  Done 2026-11-15: `core/promote.py` holds the pure rule, `loop/shortcuts.py` applies it, `loop/ledger.py` keeps
  the confirmed paths for a run in an append-only `confirmations.jsonl` so the tally spans rounds. The rule had to
  change: measured first, no whole confirmed path is ever confirmed by more than one question, so the rule as
  written can never fire — promotion now compresses any confirmed contiguous sub-path of ≥ 2 hops (REALITY_SPIKES
  S24, DECISIONS 2026-11-15). A shortcut starts at the summed cost of the hops it replaces, so promotion cannot
  change an answer in the round it happens. Promotion and retirement are receipt-bearing `Change` variants over a
  new `EdgeStatus.absent`, so INV3 covers them and rollback works. 17 unit tests in `tests/unit/test_promotion.py`
  (INV5 both ways, rollback of a promotion and of a retirement, no nested shortcuts, a hop with no live cost is
  left alone) and 2 live tests in `tests/live/test_round.py`: a real round promotes a path and the search then
  returns the shortcut at its own cost, and quarantining one hop retires it. `promote_only` added to the arms per
  PRD §8.
- [x] D5 Gap-fill (PRD §7 step 8): on `unreachable`, ingest pool documents mentioning the seed entity only (INV7:
  test that gold ids are never inspected).
  Done 2026-11-15: `loop/gapfill.py` turns each `Unreachable` gap into the pool documents that mention its seed
  entity, ingests the edge each document describes as a receipt-bearing `Fill` at cost 1.0 with `origin: gapfill`,
  and reads the edge back after the write so a receipt can never claim an ingest that did not land. Measured
  before building: the rule reaches 35 of seed 1's 96 unreachable questions (REALITY_SPIKES S25); a second wave
  would reach 43 and is in ROADMAP as not built. INV7 is proven two ways in `tests/unit/test_gapfill.py`: a pool
  document that mentions only the gold entity is left in the pool, and the unreachable path is run against a stand-in
  whose `gold` raises on access, which it never does. 2 live tests: a real gap is filled and the question it came
  from stops being unreachable, and a second pass over the same gap ingests nothing. `gapfill_only` added to the
  arms per PRD §8.
- [x] D6 Plain-store arm (`eval/plain_store.py`): BM25 over the documents (pure Python, no new service); answer =
  most frequent entity of the expected label in top-k docs; same rounds (it can't learn — that's the point).
  Done 2026-11-15: `eval/plain_store.py` is BM25 (k1=1.5, b=0.75) in pure Python over the same ingested documents
  the graph was built from, with the pool withheld from it exactly as from the graph. It returns a `Judged`, so
  `loop/evaluate.score` scores both arms the same way, ties included (C3a). `eval/plain_run.py` measured held-out
  for all 3 seeds: **0.2647 / 0.2353 / 0.2368** (evidence/plain_store.json), against the graph's round-0
  0.8529 / 0.8235 / 0.8392. top_k was swept on seed 1 and fixed at its best value, 15 — tuning that favours the
  baseline, since the Mend's constants were frozen before any run. 7 unit tests in `tests/unit/test_plain_store.py`.
  It is scored once and the same number stands for every round, because it cannot learn.

## Phase E — measurement (PRD §9–§10, docs/UPGRADES.md 1–5)
- [x] E1 Run 3 seeds × arms × N rounds (N fixed in config before the first run). Constants frozen in
  `config/mend.toml`; changing them = new run id.
  Evidence: run `01f1f6f-06b10c13` = commit `01f1f6f` + config digest `06b10c13`, seeds 1, 7 and 42, eight graph arms
  plus `plain_store`, 5 rounds, 162 rows in `evidence/curve.jsonl`, measured against the pinned local HydraDB
  (`sha256:ab71d651…`) recorded per row. Two (seed, arm) pairs were re-run with `trailmend.eval.rerun` after
  `pytest -m hydra` wrote to the same graph mid-sweep: seed 1 `reweight_only` and seed 7 `random_quarantine`. The
  contaminated rows and their journals are kept under `evidence/superseded/` with a `why.json` each, and
  `evidence/.measuring.json` now makes that collision impossible (DECISIONS.md, S31).
- [x] E2 Curve chart + `evidence/curve.jsonl` + `evidence/run_manifest.json` (commit, HydraDB digest, config hash,
  dataset hashes, sha256 of every evidence file).
  Evidence: `evidence/curve.svg` (all arms, seed bands), `evidence/curve.jsonl`, and `evidence/run_manifest.json`
  carrying the code commit, the HydraDB image and digest, the config text and its sha256, per-seed dataset/split/fault
  hashes, the sha256 of every evidence file, and `hydradb_per_evidence_file`, which shows the whole curve came from
  one HydraDB.
- [x] E3 Non-regression per round: newly fixed / newly broken / net; each break traced to receipt ids.
  Evidence: `evidence/non_regression.json`, 144 rows. Full arm over 15 measured rounds: 33 newly fixed, 29 newly
  broken, and the breaks concentrate in round 1 (9 per seed) as the first blame lands. 171 of the 172 breaks across
  all arms name the receipts written that round on the question's old correct path; 1 has none, which the file
  reports as a path that changed for another reason rather than hiding it.
- [x] E4 Quarantine precision/recall vs `faults.json`; false-quarantine rate; gaps filled vs spurious ingests.
  Evidence: `evidence/quarantine.json`. Full arm, per seed: precision 0.88 / 0.81 / 0.93, recall on planted wrong
  edges 1.00 / 0.92 / 0.92, false-quarantine rate 0.118 / 0.188 / 0.071, gaps filled 31 / 35 / 25 — every one of them
  a withheld truth edge — and 0 spurious ingests. The random control quarantines the truth graph instead:
  precision 0.09 / 0.00 / 0.00, false-quarantine rate 0.91 / 1.00 / 1.00.
- [x] E5 Mechanism decomposition table (one mechanism per arm).
  Evidence: `evidence/mechanisms.json` and the README table. Mean held-out change from round 0 to round 5:
  `gapfill_only` +2.2, `full` +0.4, `frozen` / `quarantine_only` / `promote_only` 0.0, `reweight_only` −1.9,
  `random_quarantine` −2.5, `random_reweight` −7.6. Targeted beats random on both levers measured separately, with
  the controls matched on the number and size of changes per round (`evidence/changes.json`, INV6).
- [x] E6 Load test (`eval/load.py`): concurrent clients on the product query mix, p50/p95/p99, QPS, errors by code;
  second run with a Mend round writing concurrently. Against the Railway deployment.
  Evidence: `evidence/latency.json`, measured against `https://trailmend-production-ee2e07ff.up.railway.app` and
  recording in `measured_on` that this ran against the hosted HydraDB, not the pinned local image. 8 clients x 7 asks
  a pass. **Reads only**: 56 requests in 9.97s, 5.62 qps, p50 552.9 ms, p95 6071.1 ms, p99 6099.6 ms, 52 answered and
  4 `unreachable`. **Reads while a Mend round writes to the same graph**: 56 requests in 9.63s, 5.82 qps, p50 515.7
  ms, p95 5970.1 ms, 52 answered and 4 `unreachable`, while the writer took 71.5s to apply 572 reweights and 5
  quarantines under 606 receipts. Read latency did not degrade under the writer. No request was rate-limited: the run
  was sized to stay under the public 60-asks-a-minute limit rather than raise it (DECISIONS 2026-11-15), so a larger
  run needs `TRAILMEND_ASK_RATE_PER_MINUTE` raised on the deployment first. The p95 is connection setup, not the
  graph: the first request on a fresh connection costs ~6.0s and later ones on it ~0.53s (REALITY_SPIKES S34).
- [x] E7 Preregistered hypotheses H1–H5 (PRD §3): write PASS / FAIL / INCONCLUSIVE with numbers. Failed ones stay.
  Evidence: `evidence/hypotheses.json` and the README table. H1 **FAIL** (full arm +0.0059 / +0.0000 / +0.0058 per
  seed against a round-0 seed spread of 0.0294), H2 **PASS** (both random controls fall, −0.021 to −0.088),
  H3 **PASS** (flat by construction), H4 **FAIL** (recall 1.00 / 0.92 / 0.92 but false-quarantine rate 0.118 / 0.188 /
  0.071 against a 0.1 budget), H5 **FAIL** (worst round breaks 3.25% of previously-correct answers against a 2%
  budget). The three failures are published as failures with the rule each was decided by, in the file, in the README
  and on `/evidence`. `trailmend.eval.analyse` refuses to decide H4 or H5 without per-round break rows and quarantine
  reports, and refuses to write anything if INV6 fails; this run printed `INV6 holds for 30 recorded control rounds`.

## Phase F — product surface (PRD §11–§12)
- [x] F1 API: `/v1/ask`, `/v1/judge`, `/v1/mend/round` (admin token), `/v1/receipts`, `/v1/receipts/{id}`,
  `/v1/rollback/{id}` (admin token), `/v1/evidence/curve`, `/v1/graph/neighbourhood/{id}`. Rate limit `/v1/ask`.
  Evidence: all of these answer on the deployment, plus `/healthz`, `/v1/ready`, `/v1/examples`, `/v1/evidence/{name}`
  and `/v1/demo/reset`. Every write endpoint refuses without the admin token — `/v1/judge`, `/v1/mend/round`,
  `/v1/rollback/{id}` and `/v1/demo/reset` all answer 400 `invalid_request` "Nothing was changed" with no token and
  with a wrong one, and the real cause is logged server-side only. `/v1/ask` is limited to 60 a minute per client and
  `/v1/judge` to 20, each with its own bucket, pinned by `test_f1_judging_is_rate_limited_separately_from_asking`.
  20 api tests pass under `make verify`.
- [x] F2 Web `/`: hook + curve (all arms, seed bands) + 60-second judge path.
  Evidence: `evidence/demo/f-home-390px.png`, taken from `https://trail-mend.vercel.app` at 390px. The curve is the
  live API's 162 rows, run id `01f1f6f-06b10c13`, full arm 83.9% to 84.2%, the five hypotheses with their three
  FAILs, the judge path in five steps, and `graph_writable true` read from `/v1/ready` server-side.
- [x] F3 Web `/ask`: ask, see the path drawn, judge it, see receipts.
  Evidence: `evidence/demo/f-ask-judged-390px.png`, driven in a real Chromium at 390px against the deployed site, not
  a stub: typed the listed question, pressed **Ask**, then pressed **wrong**. The page answered
  `Judged wrong. Changed anything: true.` with receipt `rcpt-9fc4f9c3d622f229`, re-asked, and drew the same path with
  the edge's cost moved from 1.000 to 1.419 (one blame at eta 0.35). `/v1/receipts` on the API shows that receipt
  against the edge `recommend-scheduler-clock-skew —ALERTS_ON→ recommend-scheduler`.
- [x] F4 Web `/mend`: the planted bad link — blame building up, quarantine, accuracy rising; rollback button.
  Evidence: `evidence/demo/f-mend-rollback-390px.png`, driven in Chromium at 390px against the deployed site. The
  page shows quarantine precision, recall and false-quarantine rate per seed from `evidence/quarantine.json`, then
  the live demo graph's own receipts. Pressing **roll this back** on `rcpt-07041ecfedc5c60c` (a reweight to 1.419)
  answered `undone by rcpt-170b29c65f65b373, changed anything true`, and the next `/v1/ask` returned that edge at
  cost 1.0 with both receipts listed, the reweight and its restore. A reset receipt has no inverse, so its button is
  disabled and says so. The live receipt list empties on a redeploy (REALITY_SPIKES S35), which the page states.
- [x] F5 Web `/evidence` and `/pricing`.
  Evidence: `evidence/demo/f-evidence-390px.png` and `evidence/demo/f-pricing-390px.png` from the deployed site at
  390px. `/evidence` shows the curve's 162 rows and its sha256 matching `evidence/run_manifest.json`, the controls
  side by side per seed, every evidence file with its claim, design, row count and sha256, and the run manifest's own
  panel (run id, commit, HydraDB image and digest, config sha256, seeds, files hashed); nothing says
  `api_unreachable` and only `latency.json` said "not produced" before E6 ran. `/pricing` carries the buyer, pain,
  status quo, unit price, pilot and what it is not. Wide tables scroll inside their own panels, so nothing overflows
  at 390px, and no API url appears in `.next/static` or `.next/server/app`.

## Phase G — submission (PRD §13, §17, §18)
- [x] G1 README: judge path in 60 seconds, the curve, how HydraDB is used, numbers each linked to evidence,
  limitations section, run-it-locally, attribution (HydraDB AGPL-3.0, used as a separate service).
  Evidence: README.md. Every figure between `<!-- numbers:start -->` and `<!-- numbers:end -->` was written by
  `trailmend.eval.report` from the finished run — the per-arm accuracy table, the H1–H5 verdicts including the three
  failures, and every evidence file with its sha256. "What this run showed" states plainly that the full Mend's lift
  is inside the seed spread, which mechanism carries it, and what the two other failures were. `latency` shows
  `not measured` until E6 runs.
- [x] G2 GTM: buyer, pain, status quo, price with a unit, pilot offer → README + `/pricing`.
  Evidence: README "Who this is for, and what it costs" and `apps/web/app/pricing/page.tsx` carry the same buyer
  (platform/SRE lead who owns the rota), pain, status quo, unit price ($4 / service / month, minimum $400) and pilot
  (6 weeks, $2,000, capped at 250 services, refunded if the agreed number does not move), plus what it is not and the
  generated-data label.
- [ ] G3 Loom (script in PRD §13). G4 Posts on X and LinkedIn tagging HydraDB → `evidence/posts.md`.
  G4 DRAFTED 2026-11-15: both posts in `evidence/posts.md` now carry the finished run's figures, each with the
  evidence file it was read from, including the three failed hypotheses and why the lift is small. Two blanks
  are left on purpose: the Loom link, and `@<hydradb-handle>`, which the file says to read off the hackathon
  page rather than guess. G3 needs a recording, which only the repo owner can make.
  SCRIPT AND DRAFTS WRITTEN 2026-11-15: `docs/LOOM_SCRIPT.md` is the shot-by-shot recording script with the page each
  spoken number is read off; `evidence/posts.md` holds the X thread and the LinkedIn post with a table saying which
  evidence file fills each blank, and `@<hydradb-handle>` to be checked rather than guessed. Recording the Loom and
  posting both need the hosted URLs (A1/A2) and the finished numbers.
- [ ] G5 Pre-submit audit from a clean clone; submit before 09:00 IST Nov 16.
  RUN CLEAN 2026-11-15 at f94a9d9 with the live tests on: all 14 checks pass — no `.env` in the clone, no
  credential-shaped strings, the README numbers block has no holes, every digest in `evidence/run_manifest.json`
  matches the file as cloned, no unfilled blanks on the site, `uv sync --frozen`, ruff, pyright strict, the unit
  tests, the web install, typecheck, lint and build, and the live contract tests against a real HydraDB. It
  found two bugs first: the digest check read a `files` key that `run_manifest.json` has never had, so it could only
  ever fail; and the manifest hashed `evidence/posts.md`, so editing the post drafts broke the audit for a file no
  number is read from. The manifest now hashes the measured files only. Ticks when it is run once more with the Loom link in the README,
  immediately before submitting.

## Phase H — run 2 (PRD §3.2, preregistered and amended 2026-11-15; nothing here starts before that section says so)

Run 1 is finished and published as FAIL. Phase H does not touch run 1's evidence, run id, data or verdicts. Every
task is traced to a finding in `docs/RUN1_DIAGNOSIS.md`. Time boxes, Lagos: H1–H4 gated by 19:00, sweep done by
23:30, analysis and live verification by 00:30. A missed box is reported at once, with what is left.

- [x] H1 The ingest rule, then dataset v2 on top of it.
  `core/ingest.py` prices every edge as `1.0 / (1 + ln(support))` from the number of ingested documents asserting it;
  the renderer draws support for every edge from the declared distribution and renders that many distinct documents;
  the loader and gap-fill both ingest at that rule. Then `data_version="v2"` splits the planted wrong edges into
  `contradicted` / `recoverable` / `destroyed` at 0.4 / 0.3 / 0.3, kind written per edge into `faults.json`, with the
  stale edge drawing support from the upper tail and the true edge it contradicts drawing 1.
  Acceptance: the recoverability check on v2 reports the true edge in G0 for every `contradicted` fault, in the pool
  for every `recoverable` one and nowhere for every `destroyed` one; v1's generated digests are unchanged, which the
  manifest proves; a test shows at least 15% of ordinary v2 edges have support ≥ 3, so support cannot be read as a
  fault flag; unit tests pin the rule's monotonicity and the three kinds. (Diagnosis §2, §5; amendment 1.)
    DONE 2026-11-15: 1/(1+ln(support)) prices every edge, support drawn from P(1) .55 / P(2) .25 / P(3) .20 and capped
  at 3 because there are three document templates per relation type. v2's 13 wrong edges split 5 contradicted / 4
  recoverable / 4 destroyed on every seed, checked per kind; v1 reproduces run 1's published faults, documents and
  split digests, which a test asserts against evidence/run_manifest.json; 21-22% of ordinary v2 edges have support 3,
  so support is not a fault flag.
- [x] H2 Update rule v2 as a measured dimension, not a replacement. `eta_blame` 0.35 and `eta_confirm` 0.10 replace
  the single `eta`, `cost_floor` rises to 0.5, and the run-1 rule stays reachable so `full_v1_rule` runs on the same
  data. Acceptance: the bound property tests pass under both rules; a test shows a confirm moving cost less than a
  blame; `config/mend.toml` carries both and the config digest changes. (Diagnosis §6.)
    DONE 2026-11-15: eta_blame 0.35, eta_confirm 0.10, cost_floor 0.5 in [mend]; run 1's symmetric rule kept in
  [run1_rule] and reachable as full_v1_rule. Bound property tests pass under both; a test shows a confirm moving cost
  less than a blame.
- [x] H3 Gap-fill v2 as its own arm. It triggers on wrong answers as well as unreachable ones and follows one extra
  wave from the nodes the first wave reached, behind `gapfill_waves`; the narrow rule stays reachable.
  Acceptance: INV7 holds for both rules in the live tests; a test shows the wide rule firing on a wrong answer the
  narrow rule ignores. (Diagnosis §5, REALITY_SPIKES S25.)
    DONE 2026-11-15: triggers on wrong answers as well as unreachable ones and follows a second wave from the entities
  the first wave reached, declared in [gapfill]. INV7 pinned for both rules; the live suite passes under the new
  config (48 tests).
- [x] H4 Analysis for the new hypotheses, written and tested before the sweep. Two-sided exact McNemar on paired
  per-question held-out verdicts, the held-out wrong-answer rate, the captured share of the reachable gain, H1'–H8'
  decided by code, and each random control checked against its own plan, which is computed under `full_v2`'s rule.
  Acceptance: unit tests give McNemar hand-checkable inputs including the zero-discordant case; the run-1 refusals
  still hold (no verdict from an empty input); `hypotheses_v2.json` is published beside `hypotheses.json`, each with
  the rule its verdicts were decided by. (Diagnosis finding 5; amendments 2 and 3.)
    DONE 2026-11-15: two-sided exact McNemar on paired per-question verdicts with hand-checkable tests including the
  zero-discordant case, the held-out wrong-answer rate, the captured share of the reachable gain, and H1'-H8' decided
  by code in analyse_v2. Every run-1 refusal kept and three added: no analysis of a curve that mixes runs or data
  versions, no captured share without a ladder.
- [x] H5 The oracle ladder on v2 → `evidence/oracle_v2.json`, giving the denominator for the captured share.
  Acceptance: the ladder's rungs repair `contradicted`, `recoverable` and withheld faults and are scored on held-out;
  the reachable-gain denominator is read from this file by code, never typed. (Amendment 2.)
    DONE 2026-11-15: oracle_run walks the ladder on v2, with a new first rung that quarantines only the contradicted
  stale edges so reweight's ceiling is separated from quarantine's. The captured share reads its denominator from
  oracle_v2.json.
- [x] H6 Run the sweep and publish it beside run 1. Seeds 1, 7, 42; arms frozen, plain_store, full_v2, full_v1_rule,
  gapfill_wide_only, random_reweight, random_quarantine; 5 rounds; under `evidence/.measuring.json`. `/`, `/evidence`
  and the README show run 2 as current and run 1 as the prior run, both with run ids, data versions and verdicts, and
  `docs/RUN1_DIAGNOSIS.md` is linked from the README. Seeds 101/404 and the ablation arms only if time is left, as a
  separately labelled extension that enters no verdict.
  Acceptance: INV6 passes on the recorded rows before any curve is written; `scripts/presubmit.sh` passes from a
  clean clone with both runs' digests matching; no run-1 evidence file changes content.

  DONE 2026-11-16: both runs and the completed MetaQA experiment are published. INV6 passes on recorded run-2 controls; every original run-1 manifest hash still matches. Clean-clone pre-submit audit at `a1b997a` passes all checks, including live tests. Evidence: `evidence/demo/final-verification.json`. The extension failed to reproduce run 2's frozen baseline; residual edges outside G0 are recorded in `evidence/paired_v2_unweighted.json`, and company-graph conclusions are provisional. Historical results and failed hypotheses remain published.
