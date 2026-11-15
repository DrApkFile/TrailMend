# Posts

Drafts for X and LinkedIn, tagging HydraDB. `@<hydradb-handle>` is a placeholder: check the real handle on the
hackathon page before posting rather than guessing it. Blanks (`______`) are filled from `evidence/` before posting — the rule
in `docs/BUILD_CONTRACT.md` applies here too: no figure is typed from memory. Posted links and timestamps go at the
bottom once they exist.

Fill from:

| Blank | File | Field |
|---|---|---|
| round 0 → round N, full arm | `evidence/curve.jsonl` | `accuracy` at `policy: full`, min and max `round` |
| frozen, plain store, random controls | `evidence/mechanisms.json` | `arms` |
| H1 verdict | `evidence/hypotheses.json` | `H1.verdict` |
| quarantine precision / recall | `evidence/quarantine.json` | `precision`, `recall` |
| p95 | `evidence/latency.json` | `p95_ms` |

---

## X (thread)

**1/**
Built a graph that repairs its own relationships, on @<hydradb-handle> for the HydraDB hackathon.

Ask it "who do I page for this alert?" It answers with a weighted path search. Tell it the answer was wrong. The
edges on that path get costlier. The ones that keep misleading get quarantined.

No LLM on the answer path.

**2/**
Held-out questions, never judged: ______ → ______ over N rounds.

Frozen graph, learning off: ______ .
Documents-only retrieval, no graph: ______ .
Random edits of the same count and size as the real ones: ______ .

The random control is the one that matters, and it's enforced as an invariant.

**3/**
What the mend actually does, each as its own arm:
• reweight — confirmed links cheaper, blamed links costlier, bounded
• quarantine — a misleading edge moves to a type the search cannot traverse
• promote — a route confirmed again and again becomes one shortcut edge
• gap-fill — an unanswerable question pulls in a document that mentions the entity

**4/**
Every change writes a receipt *before* it touches the graph: before-state, after-state, sha256. Every receipt
inverts, so any fix rolls back. That's what makes "the graph edited itself" something you can audit instead of
something you have to trust.

**5/**
The honest part. H1 was registered before the run and came out ______ .

When a planted fault points a link at the wrong target, the true link isn't in the corpus, so quarantining the bad
edge turns a wrong answer into a refusal — not into a right answer. On the site, failed hypotheses stay up.

**6/**
HydraDB 0.4 things I had to find out by running it, all in docs/REALITY_SPIKES.md:
• `UNWIND $rows` only feeds a write, never a RETURN
• an UNWIND write can't SET a literal
• `count(n)` rejected, `count(*)` fine
• a repeated query_id is silently dropped after a restart

**7/**
Live app: ______
Repo: ______
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

On held-out questions that are never judged, accuracy went ______ → ______ over N rounds. The comparisons that make
that number mean something: the same graph with learning switched off (______), documents-only retrieval with no
graph (______), and random edits making the same number and size of changes as the real mend in the same round
(______).

Every change writes a receipt before it touches the graph, with a before-state, an after-state and a digest, and
every receipt inverts — so a self-editing graph stays auditable and any fix rolls back.

What didn't work is on the site too. One preregistered hypothesis came out ______, because a planted wrong link has
no recoverable truth in the corpus: quarantining it converts a wrong answer into a refusal rather than a correct
one. The failed hypothesis stays published with its numbers.

The evaluation data is generated and labelled as generated. No customer data has been measured.

Live app: ______
Repo: ______
Loom: ______

#HydraDB #graphdatabases #platformengineering #sre

---

## Posted

| Where | URL | When |
|---|---|---|
| X | — | — |
| LinkedIn | — | — |
