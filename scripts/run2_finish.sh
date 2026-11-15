#!/usr/bin/env bash
# Everything that turns a finished run-2 sweep into published evidence, in the order the files depend on each other.
# Run it after `python -m trailmend.eval.run --v2 1 7 42` has exited and released evidence/.measuring.json.
set -euo pipefail
cd "$(dirname "$0")/.."

seeds=${*:-1 7 42}

echo "== oracle ladder on v2 (needs HydraDB; writes the denominator for the captured share)"
uv run python -m trailmend.eval.oracle_run $seeds

echo "== document-only baseline on v2 (no graph)"
uv run python -m trailmend.eval.plain_run --v2 $seeds

echo "== decide H1' to H8' and write run 2's evidence and manifest"
uv run python -m trailmend.eval.analyse_v2

echo "== fill the README numbers block for both runs"
uv run python -m trailmend.eval.report

echo
echo "done. Next: commit and push so Railway and Vercel serve it, then reset the hosted demo graph:"
echo "  set -a; . ./.env.prod; set +a; ./scripts/demo_reset.sh"
