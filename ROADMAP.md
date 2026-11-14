# ROADMAP

Ideas that are not in the current build. Nothing here is claimed as built.

- Learned query recipes per template (which relTypes and maxLen to search).
- Vector-store arm (needs an embedding model reachable from the host).
- Real connectors (Slack, Jira, GitHub) as ingestion sources.
- Upstream PR to hydra-db/selfgraph: an answer-outcome feedback hook.
- Gap-fill that follows the newly reached nodes for one more wave. Measured on seed 1: the built one-wave rule
  reaches 35 of 96 unreachable questions, a second wave would reach 43 (REALITY_SPIKES S25). Not built: it widens
  what the Mend may read for a question it has already failed, and INV7 is written against the narrow rule.
- Pooling confirmed sub-paths across templates when promoting. Measured on seed 1 round 0: 8 sub-paths reach the
  promotion threshold keyed per template, 12 if pooled (REALITY_SPIKES S24). Not built: `SC_<TEMPLATE>` per PRD §4
  keeps each template searching only its own shortcuts.
