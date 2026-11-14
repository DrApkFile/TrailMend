# EVENT: HydraDB 48-hour hackathon

Researched: 2026-11-14 (updated 17:30 Lagos with organiser Discord announcement + FAQ, pasted by user)
Sources: organiser Discord posts (announcement and FAQ by "Arrry"), HydraDB LinkedIn post, luma.com/bqwllms4 (not fetched).

## At a glance
| Item | Detail |
|---|---|
| Build window | Nov 14 09:00 IST → Nov 16 09:00 IST |
| **Hard deadline** | **Nov 16 09:00 IST = 03:30 UTC = 04:30 Lagos** (confirmed in FAQ) |
| Prizes | $1,000 total. Per track: winner $300, runner-up $150 |
| The one rule | HydraDB **open-source engine** (github.com/hydra-db/hydradb), self-run, as the graph DB. Not the hosted platform. |
| Organiser VC | ~9 PM IST Nov 14 (Q&A) |

## Tracks (paraphrased from organisers)
1. **Self-improving graph**: graph search that learns from its own answers to improve *what it ingests* and *how it queries*. Named fair game: path compression, edge reweighting, gap-driven ingestion, entity split/merge. **Bar: an accuracy curve rising over iterations.**
2. **Agent context layer**: HydraDB as the live store for an agent's skills, tool/MCP definitions and already-resolved entities; the agent traverses and pulls only what the task needs instead of preloading every tool and chaining round trips.

## Scoring (equal halves, both tracks)
| Half | What they said they look for | Our proof |
|---|---|---|
| Engineering | real traversal; does it need the graph; holds up under load. FAQ detail: (a) right metrics, not vanity; (b) real continual-learning improvement over a clearly defined baseline, not a one-off; (c) graph does real work, would fall apart on a plain store | metric defined before building; baseline(s) in repo; curve over ≥3 seeds; ablation with graph removed; load test |
| Go-to-market | who wants it; pitchable as a paid product; **post on X, LinkedIn etc. tagging HydraDB** | GTM.md, posts with links logged in evidence/ |

Fatal gates: not on HydraDB OSS; no baseline; improvement not shown over iterations.

## Submission (all three required)
1. **Hosted live app** judges can use (so HydraDB OSS must be hosted too — Railway template exists for v0.3; verify v0.4)
2. Open-source GitHub repo
3. Loom walkthrough (length not stated)

## Acceptance IDs
| ID | Requirement | Verify by |
|---|---|---|
| A01 | HydraDB OSS is the graph DB, on the critical path | delete-HydraDB test |
| A02 | Defined baseline (vector-only top-k; frozen graph) on same data | eval script |
| A03 | Accuracy rises over iterations on held-out questions, ≥3 seeds | evidence/A03 curve |
| A04 | Graph ablation: plain store loses | evidence/A04 |
| A05 | Holds up under load | load script, p50/p95, error rate |
| A06 | Live link works from a fresh browser | manual + uptime check |
| A07 | Public repo, Loom, social posts tagging HydraDB, before 04:30 Lagos Nov 16 | checklist |

## Open questions
- Loom max length? Submission form location?
- One track only per project? (prizes are per track; assume pick one)
