# Kickoff prompt for Claude Code (paste as the first message in the repo)

You are building TrailMend for the HydraDB hackathon. The hard deadline is Nov 16, 09:00 IST.
Quality is the bar: real measurements, real tests, nothing faked.

1. Read CLAUDE.md, then docs/TASKS.md, docs/PRD.md, docs/BUILD_CONTRACT.md and docs/REALITY_SPIKES.md in full.
2. Run `uv sync --frozen && make gate` and confirm it is green before changing anything.
   If HydraDB is available (`make hydra-up` or a running instance), run `make verify` too.
3. Work docs/TASKS.md top to bottom, starting at the first unchecked task. For each task:
   - read the PRD section it names;
   - write the tests that prove its acceptance first, named as behaviour, with acceptance/invariant ids;
   - implement in the package the task names, keeping trailmend/core pure;
   - run `make gate` (and `make verify` for graph work); tick the task only when acceptance passes;
   - commit with a behavioural subject line and a body that says what is true now and how it was verified.
4. When something in the docs turns out to be wrong against the live system, record the finding in
   docs/REALITY_SPIKES.md, update the PRD or CLAUDE.md, and add a DECISIONS.md row. Do not work around it silently.
5. Never invent numbers, results or test counts. Evidence files are produced by code. Anything not built is listed
   as not built. Failed hypotheses stay on record.
6. If a task is blocked (credentials, hosting, a missing dataset), say exactly what is needed and move to the next
   unblocked task.

Start now with the first unchecked task in docs/TASKS.md and report what you did when it passes.
