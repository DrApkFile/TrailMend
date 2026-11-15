# Posts

Drafts for X and LinkedIn, tagging HydraDB. `@<hydradb-handle>` is a placeholder: check the real handle on the
hackathon page before posting rather than guessing it. Every figure below is read from `evidence/` — the rule in
`docs/BUILD_CONTRACT.md` applies here too: no figure is typed from memory. Posted links and timestamps go at the
bottom once they exist.

Read from, for run `01f1f6f-06b10c13` (3 seeds, 5 rounds, means over seeds):

| Figure | File | Value |
|---|---|---|
| full arm, round 0 → round 5 | `evidence/mechanisms.json` | 83.9% → 84.2% |
| frozen graph, learning off | `evidence/mechanisms.json` | 83.9%, unchanged |
| documents only, no graph | `evidence/mechanisms.json` | 24.6% |
| random reweight / random quarantine | `evidence/mechanisms.json` | 76.2% / 81.3% |
| gap-fill alone | `evidence/mechanisms.json` | 86.1% |
| H1 / H2 / H3 / H4 / H5 | `evidence/hypotheses.json` | FAIL / PASS / PASS / FAIL / FAIL |
| quarantine precision, recall, false rate (full arm, per seed) | `evidence/quarantine.json` | 0.88, 0.81, 0.93 / 1.00, 0.92, 0.92 / 0.118, 0.188, 0.071 |
| hosted read latency | `evidence/latency.json` | p50 553 ms, p95 6071 ms (p95 is TLS setup, S34) |

---

## X (thread)

**1/**
Built a graph that repairs its own relationships, on @<hydradb-handle> for the HydraDB hackathon.

Ask it "who do I page for this alert?" It answers with a weighted path search. Tell it the answer was wrong. The
edges on that path get costlier. The ones that keep misleading get quarantined.

No LLM on the answer path.

**2/**
Held-out questions, never judged, 3 seeds × 5 rounds:

Full mend: 83.9% → 84.2%.
Frozen graph, learning off: 83.9%, flat.
Documents only, no graph: 24.6%.
Random edits, same count and size as the real ones: 76.2% and 81.3%.

The random controls are the ones that matter, and the matching is enforced as an invariant before any curve is
written.

**3/**
What the mend actually does, each as its own arm:
• reweight — confirmed links cheaper, blamed links costlier, bounded
• quarantine — a misleading edge moves to a type the search cannot traverse
• promote — a route confirmed again and again becomes one shortcut edge
• gap-fill — an unanswerable question pulls in a document that mentions the entity

Only gap-fill moves accuracy on its own: 86.1%.

**4/**
Every change writes a receipt *before* it touches the graph: before-state, after-state, sha256. Every receipt
inverts, so any fix rolls back. That's what makes "the graph edited itself" something you can audit instead of
something you have to trust.

**5/**
The honest part. Three of the five hypotheses were registered before the run and came out FAIL.

H1 wanted the lift to beat the spread between seeds: +0.4 points against a 2.9-point spread. It doesn't.
H4 missed its false-quarantine budget. H5 had one round that broke 3.25% of previously-correct answers.

All three stay published, with the rule each was decided by.

**6/**
Why the lift is small: when a planted fault points a link at the wrong target, the true link isn't in the corpus, so
quarantining the bad edge turns a wrong answer into a refusal — not into a right answer. Only the withheld-edge
faults have a document gap-fill can find. That's in Limitations, not in a footnote.

**7/**
HydraDB 0.4 things I had to find out by running it, all in docs/REALITY_SPIKES.md:
• `UNWIND $rows` only feeds a write, never a RETURN
• an UNWIND write can't SET a literal
• `count(n)` rejected, `count(*)` fine
• a repeated query_id is silently dropped after a restart

**8/**
Live app: https://trail-mend.vercel.app
Repo: https://github.com/DrApkFile/TrailMend
Loom: ______

Data is generated and labelled generated. @<hydradb-handle>

---

## LinkedIn

A service catalogue is wrong in ways nobody sees until 3am. A service points at a team that handed it over months
ago, a rota entry is stale, two entries are the same person. The page goes to the wrong humans and the incident runs
long. It's maintained by hand, so it decays between audits.

For the HydraDB hackathon I built TrailMend: it answers "who do I page for this alert?" as a weighted path search
inside HydraDB, then learns from whether the answer was right.

Confirmed links get cheaper. Blamed links get costlier, bounded so one judgement can't swing the graph. Links that
keep misleading are quarantined into a relationship type the search cannot traverse. Routes confirmed again and
again are compressed into a single shortcut edge. Questions nothing could reach pull in documents that mention the
entity asked about.

There is no LLM on the answer path and no LLM scoring an answer.

On held-out questions that are never judged, over 3 seeds and 5 rounds, the full mend went from 83.9% to 84.2%. The
comparisons that make that number mean something: the same graph with learning switched off stays at 83.9%,
documents-only retrieval with no graph scores 24.6%, and random edits making the same number and size of changes as
the real mend in the same round fall to 76.2% and 81.3%. Of the four mechanisms, only gap-fill moves accuracy on its
own, to 86.1%.

Every change writes a receipt before it touches the graph, with a before-state, an after-state and a digest, and
every receipt inverts — so a self-editing graph stays auditable and any fix rolls back.

What didn't work is on the site too. Three of the five preregistered hypotheses came out FAIL and stay published
with their numbers. The headline one, H1, asked for a lift larger than the spread between seeds: +0.4 points against
a 2.9-point spread is not that. The reason is in Limitations: when a planted wrong link has no recoverable truth in
the corpus, quarantining it converts a wrong answer into a refusal rather than a correct one, so only the
withheld-edge faults have a document gap-fill can find.

The evaluation data is generated and labelled as generated. No customer data has been measured.

Live app: https://trail-mend.vercel.app
Repo: https://github.com/DrApkFile/TrailMend
Loom: ______

#HydraDB #graphdatabases #platformengineering #sre

---

## Posted

| Where | URL | When |
|---|---|---|
| X | — | — |
| LinkedIn | — | — |
