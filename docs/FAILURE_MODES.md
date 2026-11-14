# FAILURE_MODES

## HydraDB OSS
| Mode | Guard | Where | Test |
|---|---|---|---|
| Unreachable / not writable | startup writability probe; API returns 503 graph_unavailable; loop aborts round, records not_run | graph/client.py | A-graph-down |
| Restart dedupes writes (query_id reuse) | uuid4 query_id per request | graph/client.py | live: restart mid-verify |
| Budget hit → truncated rows | read budget/truncation flags from response; truncated → outcome `refused(budget_exceeded)`, never scored as wrong silently | search/ | unit with fake response |
| Timeout | outcome unknown → round marks the question `refused`, no Mend update from it | loop/ | unit |
| Partial write during a Mend batch | receipts written before effects; replay applies missing effects idempotently | core/receipts + graph | live |
| Phantom rows on unknown id | check a real property before create | graph/queries.py | live |

## SelfGraph
| Mode | Guard |
|---|---|
| API change | exact pin + lockfile; our interface wraps it |
| Extraction error | ingest fails loudly per document, recorded; no partial silent graph |

## Railway / Vercel
| Mode | Guard |
|---|---|
| Cold start / sleep | keep-warm ping; UI shows "graph waking" state, never fake data |
| Bucket misconfig | writability probe fails startup with the variable name |
| Public abuse | shared token for writes (judge/mend/rollback), rate limit on /ask, bounded parameters |
