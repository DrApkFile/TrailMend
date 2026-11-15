# Loom script (~3–4 min)

Recorded against the hosted app. Every number spoken is read off the screen, not from this file: the blanks below
stay blank until `evidence/` has the value, and the shot list says which page shows it.

Setup before recording: hosted API healthy (`GET /v1/ready` → `graph_writable: true`), the three seeds' evidence
loaded, browser at 1280 wide, second tab on `/evidence`.

---

**0:00 — the problem.** One wrong ownership link sends every page to the wrong team.

> "This is a service catalogue. One link in it is wrong — this service points at a team that handed it over months
> ago. Nobody notices until 3am, when the page goes to the wrong humans and the incident runs long. The catalogue is
> maintained by hand, so it decays between audits."

Shot: `/` hero, then scroll to the curve but don't explain it yet.

**0:30 — ask it live, get the wrong answer, see the path.**

> "TrailMend answers this as a weighted path search inside HydraDB. Who do I page for this alert?"

Shot: `/ask`, pick the listed question whose fault is planted on its cheapest path. Point at the drawn path and the
per-hop costs. Say the answer is wrong and that the graph has no idea yet.

**1:00 — judge it, run rounds, watch blame accumulate until quarantine fires.**

> "I press wrong. That writes a receipt before it touches the graph, and it makes every edge on that path more
> expensive — bounded, so one judgement can't swing it. Three more rounds of judging and the blame concentrates on
> the one edge all the wrong answers share."

Shot: `/ask` → **wrong** → the receipt ids. Then `/mend`: the blame bars rising per round, the quarantine firing,
and open the quarantine receipt — before-state, after-state, digest.

**1:40 — the same question is now right, and the confirmed route has a shortcut.**

> "The bad edge is now in a type the search cannot traverse. Same question, cheapest route is a different one, and
> it's correct. The route that keeps being confirmed got compressed into a single shortcut edge carrying the path it
> replaces."

Shot: `/ask` again on the same question, then the `SC_` edge on the path with its `via_path`.

**2:10 — the curve, against frozen, plain store and the random controls.**

> "Held-out questions, never judged, scored every round. Frozen is the same graph with learning off. Plain store is
> retrieval over the documents with no graph. Random reweight and random quarantine make the same number and size of
> changes as the full Mend in the same round — that's the control that matters, and it's checked as an invariant, not
> asserted."

Numbers to read off the page: round 0 ______ → round N ______ for full; frozen ______ ; plain store ______ ;
random controls ______ . Source: `/` curve, backed by `evidence/curve.jsonl` and `evidence/mechanisms.json`.

Say the honest part out loud:

> "H1 ______ . And here is the limitation that bounds it: when the planted fault points a link at the wrong target,
> the true link isn't in the corpus at all, so quarantining the bad edge turns a wrong answer into a refusal rather
> than a correct one. The hypotheses were registered before the run and the failed ones are still on the page."

**2:50 — roll a fix back, then re-apply.**

> "Every change is a receipt, and every receipt inverts. This un-quarantines the edge and puts the costs back exactly
> where they were."

Shot: `/mend` rollback button, the accuracy dropping back, then apply the round again.

**3:10 — load numbers.** p50 / p95 / p99 and QPS on the product query mix, read off `/evidence`. Source:
`evidence/load.json`.

**3:30 — who pays.**

> "Platform or SRE lead who owns the rota. $4 per service per month, minimum $400. Six-week pilot at $2,000, judged
> on one number your team picks, refunded if it doesn't move. The data in this demo is generated and labelled
> generated — no customer data has been measured."

Shot: `/pricing`, end on `/evidence` with the sha256 column visible.
