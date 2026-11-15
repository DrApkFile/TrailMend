#!/usr/bin/env bash
set -uo pipefail

: "${CLONE_DIR:=${TMPDIR:-/tmp}/trailmend-presubmit}"
SKIP_LIVE="${SKIP_LIVE:-0}"
SOURCE="$(cd "$(dirname "$0")/.." && pwd)"

failures=0
report=()

check() {
  local name="$1"; shift
  if "$@" >"$CLONE_DIR/.check.log" 2>&1; then
    report+=("PASS  $name")
  else
    report+=("FAIL  $name")
    failures=$((failures + 1))
    echo "--- $name failed ---" >&2
    tail -25 "$CLONE_DIR/.check.log" >&2
  fi
}

no_env_file() { [ ! -e "$CLONE_DIR/.env" ]; }

no_secrets() {
  cd "$CLONE_DIR" || return 1
  local hits
  hits="$(git grep -nIE '(AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{32,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)' -- . || true)"
  [ -z "$hits" ] || { echo "$hits"; return 1; }
}

numbers_filled() {
  cd "$CLONE_DIR" || return 1
  grep -q '<!-- numbers:start -->' README.md || { echo "numbers block missing"; return 1; }
  local block
  block="$(awk '/numbers:start/,/numbers:end/' README.md)"
  local hole
  hole="$(printf '%s\n' "$block" | grep -nE 'Not filled yet|not measured|Not decided yet|—' || true)"
  [ -z "$hole" ] || {
    echo "the README numbers block still has holes; re-run trailmend.eval.report once every evidence file exists"
    printf '%s\n' "$hole"
    return 1
  }
}

evidence_digests_match() {
  cd "$CLONE_DIR" || return 1
  uv run python -I - <<'PY'
import hashlib, json, sys
from pathlib import Path

manifests = [Path("evidence/run_manifest.json"), Path("evidence/run_manifest_v2.json")]
present = [m for m in manifests if m.exists()]
if not present:
    print("evidence/run_manifest.json is missing")
    sys.exit(1)
bad = []
for curve, manifest in ((Path("evidence/curve.jsonl"), manifests[0]), (Path("evidence/curve_v2.jsonl"), manifests[1])):
    if curve.exists() and not manifest.exists():
        bad.append(f"{curve} is published without {manifest.name}: an unanalysed run is not a published run")
for manifest in present:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    files = payload.get("evidence_sha256")
    if not isinstance(files, dict) or not files:
        bad.append(f"{manifest.name} records no evidence_sha256 map")
        continue
    for name, digest in files.items():
        path = Path("evidence") / name
        if not path.exists():
            bad.append(f"{manifest.name} -> {name}: recorded but absent")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            bad.append(f"{manifest.name} -> {name}: manifest {digest[:12]} but file {actual[:12]}")
for line in bad:
    print(line)
sys.exit(1 if bad else 0)
PY
}

no_placeholder_numbers_on_site() {
  cd "$CLONE_DIR" || return 1
  local hits
  hits="$(git grep -nI '______' -- README.md 'apps/web' || true)"
  [ -z "$hits" ] || { echo "$hits"; return 1; }
}

echo "clean clone of $SOURCE at $(git -C "$SOURCE" rev-parse --short HEAD)"
rm -rf "$CLONE_DIR"
git clone --quiet "$SOURCE" "$CLONE_DIR" || { echo "clone failed" >&2; exit 1; }
: >"$CLONE_DIR/.check.log"

check "no .env in the clone"            no_env_file
check "no credential-shaped strings"    no_secrets
check "README numbers block filled"     numbers_filled
check "evidence digests match manifest" evidence_digests_match
check "no unfilled blanks on the site"  no_placeholder_numbers_on_site

cd "$CLONE_DIR" || exit 1
check "uv sync --frozen"  uv sync --frozen
check "ruff"              make lint
check "pyright strict"    make typecheck
check "unit tests"        make test
check "web install"       make web-install
check "web typecheck"     make web-typecheck
check "web lint"          make web-lint
check "web build"         make web-build

if [ "$SKIP_LIVE" = "1" ]; then
  report+=("SKIP  live contract tests (SKIP_LIVE=1)")
else
  check "live contract tests" make test-live
fi

echo
printf '%s\n' "${report[@]}"
echo
if [ "$failures" -eq 0 ]; then
  echo "pre-submit audit: clean"
else
  echo "pre-submit audit: $failures check(s) failed"
fi
exit "$failures"
