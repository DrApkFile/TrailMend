# ROADMAP

Ideas that are not in the current build. Nothing here is claimed as built.

- Learned query recipes per template (which relTypes and maxLen to search).
- Seeds 101 and 404, and the mechanism-ablation arms, on dataset v2. Preregistered as an **extension** that may not
  enter a run-2 verdict (PRD §3.2): the sweep's seven arms on seeds 1, 7 and 42 decide H1'-H8', and anything extra
  is reported separately or not at all.
- An anatomy pass on dataset v2, like the one in `docs/RUN1_DIAGNOSIS.md` §1, cross-tabulating cause against
  verdict per question - which run 1's `anatomy.json` counted separately and could not split.
- Vector-store arm (needs an embedding model reachable from the host).
- Real connectors (Slack, Jira, GitHub) as ingestion sources.
- Upstream PR to hydra-db/selfgraph: an answer-outcome feedback hook.
- ~~Gap-fill that follows the newly reached nodes for one more wave.~~ **Built for run 2** as the `wide` rule
  (two waves, and it also triggers on wrong answers, not only unreachable ones), after the run-1 diagnosis measured
  that gap-fill was where the headroom was: +9.8 points reachable, +2.2 taken by `gapfill_only`. The narrow one-wave
  rule stays reachable and is what run 1's arms used; INV7 is pinned for both. See PRD §3.2 and
  `docs/RUN1_DIAGNOSIS.md` §5.
- Pooling confirmed sub-paths across templates when promoting. Measured on seed 1 round 0: 8 sub-paths reach the
  promotion threshold keyed per template, 12 if pooled (REALITY_SPIKES S24). Not built: `SC_<TEMPLATE>` per PRD §4
  keeps each template searching only its own shortcuts.

- **A second HydraDB for tests.** Not built. The live and API tests share the one local graph with the measured runs and serialise on `evidence/.measuring.json` instead. True isolation needs a second container with its own bucket and a token scoped to its own graph id; the local token is scoped to `default/graphs/default` and a write to any other graph id is refused 403.
