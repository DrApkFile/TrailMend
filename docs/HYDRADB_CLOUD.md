# HydraDB Cloud API v2 (the managed context layer)

Researched: 2026-11-14
Primary sources: docs.hydradb.com (intro, essentials/v2/query.md), openapi.json (schemas section only), quickstart via context7 mirror. **api.hydradb.com is blocked from this workspace** — spikes must run on your machine or after allowlisting.

## What it is
Serverless: create a database, ingest "knowledge" (docs/apps) or "memories", HydraDB extracts entities/relations into a context graph, then `POST /query` returns ranked chunks + `graph_context`. ~70 connectors, MCP server, CLI, Python `hydradb-sdk` (import `hydra_db`), TS `@hydradb/sdk`. Pricing: Ship from $25/mo; OSS free; no hosted free tier listed.

## Essentials
- Base `https://api.hydradb.com`, headers `Authorization: Bearer $HYDRA_DB_API_KEY`, `API-Version: 2`.
- Flow: POST /databases → poll /databases/status (`ready_for_ingestion`) → POST /context/ingest (multipart; `type`, `database`, `memories`) → poll /context/status → POST /query.
- Query: `type` knowledge|memory|all; `mode` fast|thinking|auto; `alpha` (0.8), `recency_bias` (0.4), `metadata_filters`, `graph_context`, `query_forceful_relations`, `max_results` ≤250. Response `data.chunks`, `data.sources`, `data.graph_context.{query_paths,chunk_relations,chunk_id_to_group_ids}`, `meta.request_id`.
- Schemas also show: graph relations (paged), **source subgraph traversal (`id`, `depth`, `max_sources`)**, entities/triplets with evidence, **feedback submit (`request_id`, `rating`, `ground_truth`)**, metadata edit, memory delete.

## Gotchas
- Thinking mode 3–5s; fast ≤500ms. Content searchable only once status reaches `graph_creation`.
- No documented traversal-depth parameter on /query (depth lives on the subgraph endpoint).
- Endpoint paths for graph/feedback not confirmed (OpenAPI paths section not read).

## Implication for us
Cloud is a black box that already "improves itself" (Minion-1). Building the learning loop ourselves on OSS shows more engineering; Cloud is optional for entity extraction.
