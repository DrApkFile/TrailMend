# REALITY_SPIKES

Run in order; record actual output. None run yet.

| ID | Question | How | Result |
|---|---|---|---|
| S0 | Workspace can reach crates.io (yes), ghcr.io (NO, 403), api.hydradb.com (NO, 403) | curl | done 2026-11-14 |
| S1 | HydraDB OSS runs | built 0.4 (commit 916637477) from source with Rust 1.97 `--ignore-rust-version`, LAGraph 1.0.2 via git clone; `CLOUD_PROVIDER=local` | CONFIRMED locally: /healthz ok, /readyz 200, 'create-only probe: writers allowed'. Hosting on Railway still to do. 2026-11-14 |
| S2 | Basic write/read | MERGE + MATCH over HTTP | CONFIRMED 2026-11-14 |
| S3 | Edge property update visible on next read | SET r.cost then read; also after restart | CONFIRMED (default consistency), persists across restart. 2026-11-14 |
| S4 | Weighted SPpaths minimises weightProp; float weights | two-route toy graph, raise/lower costs | CONFIRMED: `weightProp: 'cost'` picks min total; floats kept (2.4 vs 2.8 correct); pathWeight int when integral. 2026-11-14 |
| S5 | Quarantine mechanism | delete R edge, MERGE same endpoints as `Q_R` with props; search relTypes ['R'] | CONFIRMED: mirror-type quarantine works and persists across restart. `MATCH (a),(b) CREATE (a)-[]->(b)` is REJECTED ('not executable by the mutation engine'); use full-pattern MERGE with labels. 2026-11-14 |
| S6 | MSpaths with ~50 seeds under default budgets: latency, truncation | timing script | — |
| S7 | (Optional) Cloud ingest → graph relations export for entity extraction | your API key, your machine | — |
| S-SG1 | SelfGraph on HydraDB: are relations real edges usable by typed path search? | read stores/hydradb.py | NO: one RELATES type + etype property + old revisions as edges. Not on answer path. 2026-11-14 |
| S-D2 | Public multi-hop KG QA reachable from build host (MetaQA preferred; HF blocked here) | git/raw GitHub mirrors | — |
| S8 | MERGE on id works in 0.4 | live | CONFIRMED (CANON's 'no MERGE' was an older build). 2026-11-14 |
| S9 | query_id idempotency after restart | restart, then identical probe write | CONFIRMED BUG: server counter restarts at http-query-1 and a repeated write after restart is silently dropped. FIX: HTTP body accepts `query_id` (src/client/http.rs:698); client sends `tm-<uuid4>` per request. Verified across 2 restarts. 2026-11-14 |
| S10 | Local build with Rust 1.97 | cargo build --release --ignore-rust-version | CONFIRMED, 10m54s. 2026-11-14 |
| S11 | SSpaths pathCount semantics | toy graph | pathCount 0 and 1 returned only the nearest node; pathCount 5 returned both; treat pathCount as a total cap and set resultLimit explicitly. 2026-11-14 |
| S12 | Local-disk storage after restart | CLOUD_PROVIDER=local, restart, write | FAILS: `PutMode::Update not yet implemented by LocalFileSystem` → HTTP 500. S3-compatible storage is mandatory (matches CANON). Dev uses moto_server as S3 stand-in; Railway uses its bucket. 2026-11-14 |
| S13 | Single-statement `MERGE … SET` | live | REJECTED ('MERGE with following clauses is not executable'). Use `UNWIND $rows AS row MERGE (n {id: row.id}) SET n:Label, …` and `UNWIND $rows AS row MATCH (a:L {id: row.src}), (b:L {id: row.dst}) MERGE (a)-[r:T {id: row.eid}]->(b) SET r.… = row.…`. Both CONFIRMED. 2026-11-14 |
| S14 | Read-your-writes | write then read, before/after restart | Send the `bookmark` from each response on the next request; client does this. CONFIRMED with S9 fix. 2026-11-14 |
