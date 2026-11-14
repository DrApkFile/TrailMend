# TrailMend

**The graph that repairs its own relationships.** Built on [HydraDB OSS](https://github.com/hydra-db/hydradb) for the HydraDB hackathon (Track 1: self-improving graph).

Your knowledge graph is wrong in ways nobody can see. TrailMend answers questions by weighted path search inside HydraDB, learns from whether each answer was right, and repairs the graph: confirmed links get cheaper, blamed links get costlier, links that keep misleading get quarantined, and every change leaves a receipt you can roll back.

> Status: under construction. No results are reported yet. Numbers will appear here only once they are produced by a recorded run (see `evidence/`).

| | |
|---|---|
| Live app | — |
| Loom | — |
| Headline curve | — |

## Docs
- Plan: [docs/PRD.md](docs/PRD.md) · Build order: [docs/TASKS.md](docs/TASKS.md) · Rules: [docs/BUILD_CONTRACT.md](docs/BUILD_CONTRACT.md)
- HydraDB facts verified live: [docs/REALITY_SPIKES.md](docs/REALITY_SPIKES.md)

## Run it locally
```bash
uv sync --frozen
make gate          # lint, strict types, unit tests
make hydra-up      # MinIO + HydraDB via docker compose
make verify        # live contract tests against HydraDB
```

## Attribution
HydraDB is AGPL-3.0 and runs as a separate, unmodified service. TrailMend is Apache-2.0.
