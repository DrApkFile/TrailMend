# IDEA_CHECK

Date: 2026-11-14

## Recommended: "Trailmark" — Track 1 only

Updated after official rules: Track 2 is specifically a tool/skill/MCP-definition graph, so Trailmark does not straddle it. Pick one track.

### Hook
"Every answer leaves a trail. Good trails get shorter, bad ones get closed." A graph that learns which paths answer questions, and can unlearn a wrong link before it spreads.

### Who, the job, how they cope, where it fails
Support/ops engineer at a 50–500 person SaaS asking an internal agent "which customers are affected by incident X?" or "who owns the service behind this alert?". Today: vector RAG over Confluence/Slack/Jira. It fails when the answer is 2–3 hops away (alert → service → owning team → on-call) and the middle hops don't look like the question; and when an outdated link (old owner) keeps getting retrieved forever. Cost: wrong escalations, minutes per incident.

### Hard core
A deterministic learning loop on the graph itself:
1. Query → seed entities (keyword/embedding lookup only for entry points).
2. HydraDB `algo.SPpaths`/`MSpaths` with `costProp` over learned edge costs → candidate paths.
3. Answer is judged (ground truth in eval; user accept/correct in product).
4. Update rule (pure function, no network): confirmed path edges get cost ↓ (bounded, decayed); edges on corrected paths get cost ↑; edges repeatedly blamed are **quarantined** (excluded via property filter) with a receipt; a path confirmed K times across distinct queries is **promoted to a shortcut edge** with provenance back to the hops.
5. Every change is an append-only receipt → any edge can be rolled back.
6. **Gap-driven ingestion** (named by organisers): when no path reaches a confident answer, the gap (missing entity/relation type) is logged and the ingester pulls and parses the source docs that mention those entities next round.
7. **Entity merge/split** (named): two nodes repeatedly co-confirmed as the same thing get merged; a node whose edges split into disjoint answer clusters gets split.
Maps 1:1 to the organisers' list: path compression = shortcuts, edge reweighting = cost updates, gap-driven ingestion, entity split/merge.

### Thin-wrapper test
Delete the LLM: traversal, learning rule, quarantine, shortcuts and eval all still run (LLM only phrases the final answer and optionally extracts entities at ingest).

### Sponsor deletion test
| Sponsor | Removed → what breaks | Critical path? |
|---|---|---|
| HydraDB OSS | weighted multi-hop path search, edge-cost state, shortcut edges — the whole retriever | Yes |

### Boundary
AI proposes: entity extraction at ingest, final answer wording, (optional) judging in product mode.
Code decides: which paths, every weight change, quarantine, promotion, rollback.
The model never: writes to edge costs, creates or deletes edges, or grades itself in the eval.

### The loop
ingest → query → traverse → answer → judge → update → (next run is cheaper/better) → poison injected → detected → quarantined → rolled back. The step others skip: **unlearning**.

### Not claimed
Not a general memory layer; not better than HydraDB Cloud; improvement shown on a synthetic-but-realistic org dataset + one public multi-hop set, not production traffic.

### Rubric → proof
| Criterion | Answer | Proof |
|---|---|---|
| Beats vector store (gate) | same data, same embedding model, vector-only top-k baseline | evidence/A02 table, 3 seeds |
| Track 1: sharper every run | held-out accuracy & hops-per-answer over runs 1..N | evidence/A03 curve |
| Graph does real work | ablation: same loop on a plain key-value/vector store collapses | evidence/A04 |
| Holds up under load | concurrent query load test on hosted HydraDB | evidence/A05 |
| Engineering | pure update core + property tests, CI, receipts | tests/, CI badge |
| GTM | wedge: incident/ownership questions for SRE/support; OSS core + hosted; HydraDB as substrate | GTM.md |

### Consent / third parties
Synthetic org data + public dataset only; no real people's data.

## Alternative (Track 2): "Toolgraph"
Graph of skills → tools → MCP servers → required entities. Agent seeds from the task, traverses to the minimal tool set, loads only those schemas. Metrics: tokens in context, round trips, task success vs "preload all tools" and vector tool-retrieval baselines. Weaker for us: the organisers' Track 2 bar is softer to prove, and vector tool-retrieval is a strong baseline that may tie.

## Verdict
Go with Trailmark on Track 1. Main risk: getting HydraDB OSS running locally (spike S1 first, today).
