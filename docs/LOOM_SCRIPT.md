# Loom script (~3–4 min)

Recorded against the hosted app. Every number spoken is on the screen while it is said, and the shot list names the
page that shows it. The figures below are from run `01f1f6f-06b10c13`; if the run is ever redone, read them off the
page again rather than from here.

Setup before recording: `GET /v1/ready` on the API returns `graph_writable: true`; the demo graph is at its loaded
state (`set -a; . ./.env.prod; set +a; ./scripts/demo_reset.sh`); browser at 1280 wide; second tab on `/evidence`.

---

**0:00 — the problem.** One wrong ownership link sends every page to the wrong team.

> "This is a service catalogue. One link in it is wrong — this service points at a team that handed it over months
> ago. Nobody notices until 3am, when the page goes to the wrong humans and the incident runs long. The catalogue is
> maintained by hand, so it decays between audits."

Shot: `/` hero, then scroll past the curve without explaining it yet.

**0:30 — ask it live, see the path and the cost of every hop.**

> "TrailMend answers this as a weighted path search inside HydraDB. Who do I page for this alert? There's the path
> it walked, and the cost of every hop. No model wrote that answer and no model is about to score it."

Shot: `/ask`, run the first listed question, point at the drawn path and the per-hop costs.

**1:00 — judge it, and watch the graph move.**

> "I press wrong. That writes a receipt before it touches the graph, and it makes every edge on that path more
> expensive — bounded, so one judgement can't swing it. Here's the receipt id, and here's the same edge, now at
> 1.419 instead of 1.000."

Shot: `/ask` → **wrong** → the judgement panel with the receipt id, then the re-drawn path with the new cost. Say
plainly that one blame moves a cost; quarantine needs blame to concentrate across rounds, which the next shot shows
from the recorded runs rather than live.

**1:40 — quarantine, measured against the planted faults.**

> "When an edge keeps being blamed, with a high enough share of its recent judgements and almost no confirmations,
> it is quarantined: moved to a type the search cannot traverse. Here is how often that was right, against faults we
> planted and therefore know: precision 0.88, 0.81 and 0.93 across the three seeds, recall 1.0, 0.92 and 0.92. And
> here is what it cost: a false-quarantine rate of 0.118, 0.188 and 0.071, against a budget of 0.1. That budget is
> one of the hypotheses, and it failed."

Shot: `/mend`, the quarantine table.

**2:10 — the curve, against frozen, plain store and the random controls.**

> "Held-out questions, never judged, scored every round. The full Mend goes from 83.9% to 84.2%. Frozen — the same
> graph with learning off — stays at 83.9%. Documents only, no graph, scores 24.6%. And the random controls, which
> make the same number and size of changes as the real Mend in the same round, fall to 81.3% and 76.2%. That
> matching is checked as an invariant before any of these files is written, not asserted."

Shot: `/` curve and the arm table, then the controls table on `/evidence`.

Say the honest part out loud:

> "H1 asked for a lift bigger than the spread between seeds. Plus 0.4 points against a 2.9-point spread is not that,
> so H1 failed, and so did two others. They are all still on the page with the rule each was decided by. Here is the
> limitation behind it: when the planted fault points a link at the wrong target, the true link isn't in the corpus
> at all, so quarantining the bad edge turns a wrong answer into a refusal rather than a correct one. The one
> mechanism that does move accuracy on its own is gap-fill, at plus 2.2 points on every seed."

Shot: the hypotheses table on `/`, then the mechanisms table.

**2:50 — roll the fix back.**

> "Every change is a receipt, and every receipt inverts. This is the judgement I made a minute ago. Roll it back,
> and the cost is exactly where it was — and the rollback leaves its own receipt, so nothing is erased."

Shot: `/mend`, **roll this back** on that receipt, the `undone by rcpt-…` line, then `/ask` again showing cost 1.0.

**3:10 — what it costs to answer.**

> "Eight concurrent clients on the product question mix against this deployment: p50 553 milliseconds, and the same
> load again while a Mend round writes 572 reweights and 5 quarantines to the same graph — p50 516 milliseconds.
> Reads don't degrade under the writer. The p95 is TLS setup on a new connection, which is written down too."

Shot: `/evidence`, the "What it costs to answer" panel.

**3:30 — who pays.**

> "Platform or SRE lead who owns the rota. $4 per service per month, minimum $400. Six-week pilot at $2,000, judged
> on one number your team picks, refunded if it doesn't move. The data in this demo is generated and labelled
> generated — no customer data has been measured."

Shot: `/pricing`, end on `/evidence` with the sha256 column visible.
