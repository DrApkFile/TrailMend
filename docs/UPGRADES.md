# UPGRADES — the 10 changes to the TrailMend plan, ranked by impact on judging

Ranked by marginal points against the stated rubric (Technical 50 % / GTM 50 %, Track 1 bar =
"an accuracy curve rising over iterations"). Effort is in focused engineer-hours; "risk if skipped"
is what a sharp judge says out loud. Every item is derived from what CANON did, did badly, or left
undone — see `PRIOR_ART_CANON.md` for citations.

---

## 1. Make the rising curve the first artifact in the repo, not a result inside it

**Change.** The README's first screen is a round-indexed accuracy chart: held-out accuracy at rounds
0..N, three seeds, mean with min/max band, with round 0 = the frozen graph drawn as a flat line, the
vector-only baseline as a second flat line, and the two random controls as two more curves that do
not rise. Every other number in the repo is subordinate to that chart. Write the exact chart
contract before writing the loop: `round, seed, arm, n_heldout, correct, accuracy`, one JSONL row
per (round, seed, arm), appended by the loop itself and never edited by hand.

**Why.** CANON wins on a static before/after and has no curve at all — against this rubric it scores
zero on the headline criterion. The curve is the only thing that cannot be faked by a better
retriever, and it is the one deliverable where we are structurally ahead. CANON's lesson is about
*presentation*: four numbers in a 2-column table on screen one (`README.md:59-64`) is what made its
claim legible in 90 seconds. Ours is one chart.

**Effort.** 4 h for the harness and chart once the loop exists (the loop itself is the project).
**Risk if skipped.** We lose the single criterion the organisers named. A static "graph beats
vector" result reads as a weaker CANON.

---

## 2. Ship the no-graph ablation arm — the thing CANON never built

**Change.** A fourth arm that runs the identical pipeline (same ingest, same questions, same judge,
same number of rounds) with the entry-entity lookup feeding flat top-k over a plain store and *no*
path search. Report two things: its round-0 accuracy, and that its curve is flat — because there are
no paths to reweight, no edges to quarantine, no multi-hop to compress. Add a one-paragraph
"what breaks without the graph" section naming which repair operations become undefined.

**Why.** "The graph doing real work, so the project would fall apart on a plain store" is an
explicit judging line. CANON *asserts* this (`README.md:211-213`) and never measures it; a judge who
notices the production graph has 19 `SUPERSEDES` edges can press hard. Measuring it converts our
strongest architectural claim from rhetoric into a row in a table.

**Effort.** 6-8 h (the flat-store arm is mostly the baseline we need anyway).
**Risk if skipped.** The most damaging question in the room — "would a dict do this?" — goes
unanswered, and the Technical half is judged on assertion.

---

## 3. Build the random-reweight and random-quarantine controls on day one, not at the end

**Change.** Two control arms, seeded per round and per question, each making *the same number and
magnitude* of changes the real repair loop made that round, chosen at random, and running for the
same number of rounds. Store each control's design string next to its numbers. Expected result and
the claim it earns: the controls stay flat, so the gain comes from choosing the *right* edges, not
from perturbing the graph.

**Why.** This is a direct copy of CANON's single best experiment
(`scripts/benchmark/random_control.py:26-68`, which landed the random arm at exactly the baseline
70.0 %). Two details are worth copying exactly: the seed is derived from the question id, so the
control is reproducible; and the control backfills from the same ranking, so document counts stay
equal. One detail must be *improved*: CANON's control was a single-step control against a
single-step intervention — ours must run the full loop, or a judge will say the control was given
fewer chances to improve.

**Effort.** 4 h if the loop is parameterised by a "repair policy" from the start; 2 days if bolted on
afterwards. Build the policy seam now.
**Risk if skipped.** "You wiggled the weights until accuracy went up." Without this, the curve is
uninterpretable and the whole technical case collapses.

---

## 4. Non-regression as a first-class, per-round gate

**Change.** For every question correct at round *n*, assert it is still correct at round *n+1*.
Publish three numbers per round: newly fixed, newly broken, net. Every regression is traced to the
specific repair receipt that caused it, by id. Ship a `make verify`-style check that fails the build
if net regressions exceed a declared threshold.

**Why.** CANON's safety envelope (`envelope.py:66-119`) — 471/480 contexts byte-identical, 0
expected documents harmed, every one of the 9 interventions traced to its origin — is the most
convincing artifact in its repo, because it answers "does your clever thing break the normal case?"
without a model in the loop. A self-modifying graph invites that question far harder than a static
filter does. Tracing each regression to a receipt is strictly stronger than CANON's tracing.

**Effort.** 5 h (the per-round judgments already exist; this is bookkeeping plus the trace join).
**Risk if skipped.** The obvious attack on any self-improving system — "it learns one thing and
forgets another" — is left standing, and a rising aggregate curve gets read as cherry-picking.

---

## 5. Plant known errors and report edge precision/recall

**Change.** Construct a known-truth graph, plant a declared set of wrong edges and delete a declared
set of true ones, then report after N rounds: wrong edges quarantined / wrong edges planted
(recall), good edges wrongly quarantined / total quarantined (false-positive rate), missing edges
recovered by gap-driven ingestion, and spurious ingests. Publish the planted list in the repo so the
measurement is auditable.

**Why.** This is a deterministic, model-free, ground-truth metric — the same tier as CANON's
strongest rows (superseded-in-context 14/20 → 1/20, no model involved). Accuracy alone shows the
system moved; precision/recall on planted errors shows it moved *for the right reason*. It is also
the only metric that can show the repair loop is not just memorising the eval set.

**Effort.** 8-10 h including constructing the planted-error corpus.
**Risk if skipped.** Our accuracy curve has no mechanistic backing. A judge can suggest the loop is
overfitting the question set, and we have nothing deterministic to answer with.

---

## 6. Receipts with real rollback, exposed as a product contract

**Change.** Every graph mutation writes a receipt: cause (question id, judgment, blamed path),
before/after state, the HydraDB query ids that decided it, a content hash, and a rollback handle.
Expose `GET /receipts`, `GET /receipts/{id}`, `POST /rollback/{id}`. Prove rollback in `make verify`:
apply a repair, roll it back, assert the graph is byte-identical to its pre-repair state.

**Why.** CANON's Temporal Context Receipt (`app.py:98-148`) is its best *product* idea — input
ranking, per-cut reason, context hash, query ids, "an auditor can replay the decision without
trusting the service". We extend it in the direction that matters for a self-modifying graph: an
audit log that can be undone. That is the difference between a demo and something an enterprise
would run. It is also the single most demo-able thing we have: break the graph live, roll it back
live.

**Effort.** 10 h, and it must be designed into the writer from the first commit — retrofitting
rollback onto a loop that mutates in place is a rewrite.
**Risk if skipped.** "Self-improving" reads as "self-corrupting with no undo", the GTM pitch loses
its strongest enterprise hook, and the Loom has no dramatic moment.

---

## 7. A real load test: concurrency, write-under-read, p99

**Change.** Concurrent clients against the *product* query mix (entry lookup + bounded weighted path
search), reporting p50/p95/p99, sustained QPS, error rate by HydraDB error code, and a second run
with the repair loop writing concurrently. Record engine quirks encountered, with the workaround, in
the same evidence file.

**Why.** "Holds up under load" is an explicit judging line, and CANON's `make perf`
(`perf.py:139-244`) is a *latency* benchmark — one client, sequential, 20 runs, on a synthetic
subgraph unrelated to its product queries. Copy its good parts: named queries, p50/p95 per
operation, written to `evidence/`, plus honest notes about engine behaviour (its notes on the 30 s
timeout on unanchored scans and ~1/s vertex deletes are more useful than its numbers). Then beat it
on the axis it skipped. Reads during writes is the interesting case for us specifically, because our
loop writes while judges are clicking.

**Effort.** 6 h.
**Risk if skipped.** We tie with CANON on a line we could win outright, and the live demo risks
falling over under judge traffic with no evidence we ever tested it.

---

## 8. Deploy the judge-facing app in the CANON shape, early, and keep it warm

**Change.** Adopt the pattern wholesale: frontend on Vercel; API + HydraDB + MinIO on one dedicated
box via `docker compose`; **all page data fetched in server components** so the API is never called
from a browser (no CORS, no TLS on the backend, no keys in client JS); exactly one client-initiated
endpoint behind our own route handler. Gate every ingest on a *writability* probe, not `/healthz`.
Add the two things CANON lacks: an auth token or rate limit on the public endpoint and a bounded
`top_k`. Deploy a walking skeleton on day one and redeploy continuously.

**Why.** The exact hosting mechanics are in `PRIOR_ART_CANON.md` §7 and they are the highest-value
thing in this whole teardown: the MinIO requirement (writer leases need conditional writes — a bind
mount will not work), `RUST_MIN_STACK=32MB`, unique `query_id` per request (the server's counter
restarts at 1 and silently dedupes post-restart writes), no `MERGE` (check a real property before
every create), and anchored-queries-only (unanchored scans exceed the 30 s timeout). Each of those
cost CANON real debugging time; each is now free to us. CANON also has no deploy config in-repo —
we should commit ours, so "self-hosted HydraDB" is verifiable rather than asserted.

**Effort.** 6-8 h for the first deploy if done early; a day or more of panic if left to the last
evening.
**Risk if skipped.** The submission requires a hosted live app judges can use. A late deploy on an
unfamiliar engine is the classic way to ship a broken link.

---

## 9. Name the core operation, then decompose it into single-mechanism arms

**Change.** One name — "the Mend" — covering reweight + quarantine + promote + gap-fill, with a
table showing each mechanism run alone for the same rounds on the same questions, plus all four
together. Report deterministic rows for each (edges touched, paths promoted, gaps filled) alongside
accuracy.

**Why.** CANON's "Temporal Cut" is a name judges can repeat, and its two-half decomposition
(`evidence/mechanism.json`: cut-only 1/20 leak but 18/20 current gold; pin-only 14/20 but 20/20;
both 1/20 and 20/20) proves no single trick carries the result. With four mechanisms we have a
stronger version of the same argument — and a real risk of the opposite reading: that we shipped
four half-ideas. The decomposition table is what turns a grab-bag into a mechanism.
Copy CANON's honesty rule here too: if an arm's judged scores cannot be produced reliably, publish
the deterministic rows and record the rest as `not_run` with the verbatim reason, never a number.

**Effort.** 5 h, given the policy seam from item 3 (each mechanism is one policy configuration).
**Risk if skipped.** No phrase for judges to carry into deliberation, and the loop is read as four
heuristics stacked until the number moved.

---

## 10. Close the GTM half properly — the cheapest points on the board

**Change.** A one-page pitch in the README and the Loom: a named buyer (role and budget line, not a
market), the pain in their words, the status quo they pay for today, a price with a unit
(per grounded query / per repaired graph / per seat), and what the first paid pilot includes. Two or
three social posts tagging HydraDB, timed around the submission. Lead the README with the hook and
the curve, close it with the pitch.

**Why.** Half the rubric, and CANON — which won — has no buyer, no price and no paid-product
framing: one X thread, a demo video, badges and an excellent component contract
(`PRIOR_ART_CANON.md` §8). Its GTM strength is positioning-by-contract ("put it between your
retriever and your LLM") and craft; its gap is commercial specificity. We copy the contract framing
and add the commercial page it never wrote. This is single-digit hours for a double-digit share of
the score.

**Effort.** 4-6 h including the posts and the Loom section.
**Risk if skipped.** We can win the technical half outright and still lose, because the other half
was left at "it's obviously useful".

---

## Sequencing note

Items 3, 6 and 8 must be designed in before the loop is written — a repair-policy seam, a receipt
and rollback path in the writer, and a deployable compose + BFF skeleton. Retrofitting any of the
three is a rewrite. Items 1, 4, 5, 7, 9 are measurement work that lands once the loop runs. Item 10
is independent and should be drafted while the loop is running, not after.
