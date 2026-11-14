# STAKEHOLDERS: what HydraDB cares about

Researched: 2026-11-14
Sources: LinkedIn (Nishkarsh Srivastava posts), research.hydradb.com/hydradb (paper), benchmarks.hydradb.com/hydradb, hydradb.com blog (dev.to mirrors), funding listings.

## People
- Nishkarsh Srivastava: founder/CEO (since Apr 2025; previously founded Findr, an "AI second brain"). Writes most blog posts.
- Paper authors (Engineering): Soham Ratnaparkhi, Nishkarsh Srivastava, Aadil Garg, Pratham Garg.
- Team seen in public: Harsh Bhatt (Rust internals, coding harness benchmark), Abhishek Tripathi (Raft/distributed systems walkthroughs), Arrry (Discord organiser).
- Money: $6.5M seed, Mar 2026. Investors include Sky9 Capital, Jeff Dean, Gokul Rajaram, Joshua Sum, Sean Cai, Ashish Kakran.

## Recurring themes (ranked by how often they show up)
1. Superseded/stale facts; bitemporal edges (when true vs when learned). CEO post: account changes owner Oct 1, agent learns Oct 5.
2. Wrong or missing relationships: an unsupported edge sends retrieval down the wrong path, and a missing one leaves the right path unreachable. Check affected entities after each write.
3. Entity identity across systems (the same person in Slack, Gmail, docs).
4. Provenance and decision traces: every fact linked to source, time, confidence; append-only.
5. "A graph only helps once retrieval finds the right starting node": vector recall for entry points + bounded traversal.
6. Retention: decay unused memories, reinforce only on evidence of usefulness, not on merely appearing in candidates.
7. Infra gives primitives, not a schema (bring your own ontology).
8. Object-storage economics and scale; compute/storage separation.
9. Use cases they name: service dependencies, account ownership, superseded policies (support), coding assistants, fraud, multi-agent shared state.

## Implications
- Pure edge reweighting is close to what they already describe (retention/reinforcement); novelty must come from repair (quarantine wrong edges, ingest missing ones, merge/split) and from proof.
- CANON (prior winner) already owns "temporal truth": don't build a CANON clone.
- Load/scale claims should lean on HydraDB's own strengths (MSpaths server-side, budgets).
