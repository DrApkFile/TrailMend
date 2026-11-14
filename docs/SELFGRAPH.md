# SelfGraph (hydra-db/selfgraph)

Researched: 2026-11-14. Source: repo cloned at 168d6c6 (2026-11-14), README, docs/{trust,maintenance,retrieval,resolution}.md, src/.
Released by arrry-hydraDB (the hackathon organiser). Apache-2.0. Python 3.10+ and TS (@hydradb/selfgraph). v0.0.3 Nov 7 → v0.1.0 Nov 9 (breaking changes) → 0.2.0 on PyPI. ~13 stars.

## What it gives us
- Text → entities/relations (LLM, spaCy or regex), deterministic ids, typed CRUD.
- Versioned relations; newer facts retire older ones; `as_of` reads.
- Entity resolution on insert (exact/default/fuzzy/llm); every merge recorded; `unmerge`.
- Evidence/provenance records; `unsupported_fact` lint; certification; hub detection.
- `check_answerable`: LLM-free verdict answerable/partial/uncertain/not_answerable + `missing` terms.
- Maintenance: decay (recency + source/degree frequency), prune, dedupe. Dry-run by default.
- Retrieval: BM25 seeds → BFS/DFS/PPR. No vector store. HydraDBStore needs HydraDB ≥0.4 over Bolt.
- CLI + MCP server.

## What it does NOT do (our gap)
- Nothing learns from answer outcomes. Decay uses time and counts, not whether an edge led to a right or wrong answer.
- Merges come from names/ids at insert, not from answer evidence. No split driven by answers.
- Retrieval doesn't use HydraDB's weighted path procedures (no algo.SPpaths/MSpaths/costProp in src).
- No shortcut/path-compression edges, no quarantine, no gap-driven ingestion loop (check_answerable reports gaps; nothing acts on them).

## Risks
- Days old, API churning; pin exact version; read the HydraDB store code before trusting it.
- If we lean on it too much, our own contribution must be obvious in the repo and the Loom.

## Spike S-SG1 result (2026-11-14, code reading of src/selfgraph/stores/hydradb.py @168d6c6)
- On HydraDB, every relation is stored as ONE edge type, `RELATES` (`_EDGE = "RELATES"`, line 31); the real type lives in an `etype` property.
- Versioning keeps old revisions as additional `RELATES` edges with `is_current = false`.
- Consequence: HydraDB path procedures (which filter by relationship type via `relTypes`) can't restrict to a relation type, and would walk retired revisions too. Our weighted, typed search can't run directly on SelfGraph's layout.
- Decision: SelfGraph is NOT on the answer path. Our graph uses real typed edges with `cost`/`status`. SelfGraph may still be used at the edges (e.g. P1: extraction of gap-fill documents into facts we then write ourselves), or dropped. Recorded in DECISIONS.md.
