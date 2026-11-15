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
- [ ] E1 Run 3 seeds × arms × N rounds (N fixed in config before the first run). Constants frozen in
  `config/mend.toml`; changing them = new run id.
- [ ] E2 Curve chart + `evidence/curve.jsonl` + `evidence/run_manifest.json` (commit, HydraDB digest, config hash,
  dataset hashes, sha256 of every evidence file).
- [ ] E3 Non-regression per round: newly fixed / newly broken / net; each break traced to receipt ids.
- [ ] E4 Quarantine precision/recall vs `faults.json`; false-quarantine rate; gaps filled vs spurious ingests.
- [ ] E5 Mechanism decomposition table (one mechanism per arm).
- [ ] E6 Load test (`eval/load.py`): concurrent clients on the product query mix, p50/p95/p99, QPS, errors by code;
  second run with a Mend round writing concurrently. Against the Railway deployment.
  WRITTEN 2026-11-15, NOT RUN: `eval/load.py` writes `evidence/latency.json` (the claim is `latency`, not `load`,
  because `evidence/load.json` already holds G0's load evidence). Needs a running API; against Railway it needs A1.
- [ ] E7 Preregistered hypotheses H1–H5 (PRD §3): write PASS / FAIL / INCONCLUSIVE with numbers. Failed ones stay.

## Phase F — product surface (PRD §11–§12)
- [ ] F1 API: `/v1/ask`, `/v1/judge`, `/v1/mend/round` (admin token), `/v1/receipts`, `/v1/receipts/{id}`,
  `/v1/rollback/{id}` (admin token), `/v1/evidence/curve`, `/v1/graph/neighbourhood/{id}`. Rate limit `/v1/ask`.
- [ ] F2 Web `/`: hook + curve (all arms, seed bands) + 60-second judge path.
- [ ] F3 Web `/ask`: ask, see the path drawn, judge it, see receipts.
- [ ] F4 Web `/mend`: the planted bad link — blame building up, quarantine, accuracy rising; rollback button.
- [ ] F5 Web `/evidence` and `/pricing`.
  BUILT; RENDER CHECKED AGAINST A STUB 2026-11-15: all five pages return 200 with no `api_unreachable`,
  `unreadable_response` or framework error, served by `next start` against a stand-in API that replayed the real
  curve rows and the real analysis files. `/evidence` now lists `load` and `latency` as well. Nothing long can
  overflow at 390px: the only table is wrapped in `overflow-x-auto`, the curve is a `viewBox` SVG at `w-full`, and
  every sha256, run id and path line carries `break-all`. No API url appears in `.next/static` or `.next/server/app`.
  Ticks when the same five pages are rendered against the live API in a real browser at 390px (task #3).

## Phase G — submission (PRD §13, §17, §18)
- [ ] G1 README: judge path in 60 seconds, the curve, how HydraDB is used, numbers each linked to evidence,
  limitations section, run-it-locally, attribution (HydraDB AGPL-3.0, used as a separate service).
  PROSE WRITTEN 2026-11-15: all sections are in README.md. Every figure lives between `<!-- numbers:start -->` and
  `<!-- numbers:end -->`, rewritten by `trailmend.eval.report` from `evidence/`; the block currently says it is
  unfilled because the E1 sweep is still running. Ticks when the sweep finishes and the block holds real numbers.
- [x] G2 GTM: buyer, pain, status quo, price with a unit, pilot offer → README + `/pricing`.
  Evidence: README "Who this is for, and what it costs" and `apps/web/app/pricing/page.tsx` carry the same buyer
  (platform/SRE lead who owns the rota), pain, status quo, unit price ($4 / service / month, minimum $400) and pilot
  (6 weeks, $2,000, capped at 250 services, refunded if the agreed number does not move), plus what it is not and the
  generated-data label.
- [ ] G3 Loom (script in PRD §13). G4 Posts on X and LinkedIn tagging HydraDB → `evidence/posts.md`.
  SCRIPT AND DRAFTS WRITTEN 2026-11-15: `docs/LOOM_SCRIPT.md` is the shot-by-shot recording script with the page each
  spoken number is read off; `evidence/posts.md` holds the X thread and the LinkedIn post with a table saying which
  evidence file fills each blank, and `@<hydradb-handle>` to be checked rather than guessed. Recording the Loom and
  posting both need the hosted URLs (A1/A2) and the finished numbers.
- [ ] G5 Pre-submit audit from a clean clone; submit before 09:00 IST Nov 16.
