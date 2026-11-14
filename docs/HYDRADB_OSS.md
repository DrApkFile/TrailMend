# HydraDB OSS (the graph database)

Researched: 2026-11-14
Primary sources: github.com/hydra-db/hydradb @ 916637477 (2026-11-14), README.md, USING-HYDRADB.md, cypher-compat.md, CHANGELOG.md, crates/mcp, Dockerfile.

## What it is
Rust, object-store-native graph DB (AGPL-3.0). Durable state in S3-compatible storage via SlateDB; query nodes and indexers hold only caches. Neo4j drivers work over Bolt 5.x; also a JSON/NDJSON HTTP API. v0.4.0 (2026-11-06) added ISO GQL, a Bolt proxy, an MCP server, DataFusion path.

## Core concepts you'd get wrong by guessing
- `id` is the upsert key. Plain `CREATE` duplicates relationships; use `MERGE` or `UNWIND … CREATE`.
- Patterns: exactly ONE relationship type and a direction per pattern; undirected rejected.
- Variable-length needs a max (`*1..3`); `*` / `*1..` rejected. Ranges are inclusive.
- WHERE: no `IN`, `CONTAINS`, `ENDS WITH`, `IS NULL`. `STARTS WITH` only. `WITH` is pass-through only.
- **Auto-commit only**: BEGIN/COMMIT/ROLLBACK rejected. Design idempotent writes.
- Query budgets (edges scanned, rows, bytes, deadline): **fewer rows can mean a budget hit, not missing data.**
- Wrong `cell_id` → opaque HTTP 500.
- `/healthz` on 8443; `/readyz` (200, empty body) and `/metrics` on 9090.
- No vector/embedding support documented. No PageRank; algorithms = path procs + `algo.degree`.

## The procedures that matter for us
- `algo.SPpaths` / `algo.SSpaths` / `algo.MSpaths`: bounded simple paths; `relTypes` can list several types (MATCH can't); **weighted** via `weightProp`, `costProp`, `maxCost`. `maxLen` counts edges; too small looks identical to "no path".
- `algo.MSpaths` evaluates many source/target pairs server-side; list values must be inlined (list params rejected); `sourceLabel`, `sourceProperty` required; set `pairwise` explicitly.
- `algo.degree` per label from compiled topology.

## Minimal working shape (HTTP)
`POST /v1/graphs/default/query` with `Authorization: Bearer <token>`, body `{"cell_id":"cell-0","query":"…","parameters":{…}}`. Python: `neo4j` driver, `bolt://127.0.0.1:7687`, auth ("neo4j", token), `database="default"`.

## Run locally
- Source: Rust (Dockerfile pins 1.99.0; MCP crate needs rust 1.99), clang, cmake, libcypher-parser-dev, libgraphblas-dev, LAGraph (built by scripts/install_lagraph.sh). `CLOUD_PROVIDER=local`, `GRAPH_ALLOW_PLAINTEXT=true`, `RUST_MIN_STACK=33554432`, `cargo run --locked --features server-runtime --bin graph-node`. Smoke: scripts/runtime_smoke.sh → `runtime-smoke-ok`.
- Image: ghcr.io/hydra-db/hydradb (from Helm values). Railway template exists (v0.3).

## Unverified → REALITY_SPIKES.md
- Does the ghcr image run standalone with local storage?
- Weighted `SPpaths` semantics: is `weightProp` minimised? How are ties ordered?
- Can we update an edge property (`MATCH ()-[e]->() SET e.w = …`) and see it on the next read (causal vs strong)?
- MCP server tool surface (one tool: `execute_query`).

## Out of scope
Clustering, Helm/K8s, FalkorDB import, GQL.
