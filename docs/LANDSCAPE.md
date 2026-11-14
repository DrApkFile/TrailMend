# LANDSCAPE

Researched: 2026-11-14

## House style (HydraDB events)
Agent memory / company brain / code-as-graph, with a benchmark number against a baseline (e.g. a HydraDB engineer's coding harness reported ~91 vs DeepWiki ~66 on CodeWikiBench). Judges are HydraDB engineers: they will respect Cypher that uses path procedures properly, and punish "vector search with a graph sticker".

## Neighbours
| Project | What it does | Positioning line |
|---|---|---|
| Cognee 1.0 | Feedback weights on graph nodes/edges, LLM-scored sentiment feeds retrieval; `improve()` | Cognee reweights by sentiment; we learn which *paths* answer questions, prove the lift on a held-out set, and can undo any change. |
| Graphiti / Zep | Temporal KG for agent memory | Time-aware facts; doesn't learn from use. |
| Mem0 graph | Graph memory (paid tier) | Storage, not a learning loop. |
| Microsoft GraphRAG / LightRAG | Build-once community summaries | Frozen at index time — exactly what this hackathon is against. |
| HydraDB Cloud (Minion-1 "dream") | Vendor's own continuous improvement | We're the open, inspectable loop on their OSS engine. |

## The gap
Everyone claims "gets smarter with use". Almost nobody (a) shows a run-over-run curve on questions the system has never seen, against a frozen vector baseline, with seeds; or (b) demos the system **unlearning** a wrong relationship before it spreads. HydraDB's own team has posted about wrong relationships travelling through enterprise graphs — that's the moment to demo.

## Prepared judge questions
- Q: Isn't this just Cognee? A: Cognee's weights come from LLM sentiment; ours are deterministic updates with receipts, executed as weighted path search inside HydraDB, and measured on held-out queries.
- Q: Why not a vector store? A: Baseline in repo; the answers need 2–3 hops whose middle nodes don't look like the question.
- Q: Does it overfit? A: Train/held-out split by entity, decay, capped weights, and a poisoning test.
