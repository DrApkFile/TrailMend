# DECISIONS

| Date | Decision | Why | Evidence |
|---|---|---|---|
| 2026-11-14 | Track 1, product "TrailMend", core operation "the Mend" | Matches organisers' four named techniques and CEO's stated problem; CANON scored zero on "rising curve" | IDEA_CHECK.md, STAKEHOLDERS.md, PRIOR_ART_CANON.md |
| 2026-11-14 | Hosting: Railway (HydraDB + bucket + API), Vercel (web, BFF) | HydraDB is a long-running server needing S3; CANON's BFF shape | PRIOR_ART_CANON.md §7 |
| 2026-11-14 | SelfGraph not on the answer path | Stores all relations as one RELATES edge type with etype property; old revisions remain as edges | SELFGRAPH.md S-SG1 |
| 2026-11-14 | Scoring is exact-match on gold entity ids; no LLM judge | Deterministic, cheap, many seeds; removes "model graded itself" attack | PRD §3 |
| 2026-11-14 | Local dev S3 is `moto_server` on the host, not MinIO in compose; the local hydradb service runs with `network_mode: host` | `minio/minio:latest` no longer exists on Docker Hub (S16), and `ufw` on the build host drops docker-bridge traffic to a host-side endpoint (S18). moto needs no image pull and is confirmed to carry HydraDB's conditional writes across a restart (S17). | REALITY_SPIKES S16, S17, S18 |
