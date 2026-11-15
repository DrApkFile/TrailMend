#!/usr/bin/env bash
set -euo pipefail

: "${TRAILMEND_API_URL:=https://trailmend-production-ee2e07ff.up.railway.app}"

if [ -z "${TRAILMEND_ADMIN_TOKEN:-}" ]; then
  echo "set TRAILMEND_ADMIN_TOKEN to the deployment's admin token, for example:" >&2
  echo "  TRAILMEND_ADMIN_TOKEN=... ./scripts/demo_reset.sh" >&2
  echo "or put it in a file this script sources and never prints:" >&2
  echo "  set -a; . ./.env.prod; set +a; ./scripts/demo_reset.sh" >&2
  exit 2
fi

printf 'resetting the demo graph at %s\n' "$TRAILMEND_API_URL"
code="$(
  curl -sS -o /tmp/trailmend-reset.json -w '%{http_code}' --max-time 300 \
    -X POST "$TRAILMEND_API_URL/v1/demo/reset" \
    -H "x-admin-token: $TRAILMEND_ADMIN_TOKEN"
)"

if [ "$code" != "200" ]; then
  echo "reset failed with HTTP $code:" >&2
  cat /tmp/trailmend-reset.json >&2
  echo >&2
  rm -f /tmp/trailmend-reset.json
  exit 1
fi

python3 -c '
import json, sys
body = json.load(open("/tmp/trailmend-reset.json"))
print("receipt", body["receipt_id"], "digest", body["digest"][:16])
print("quarantines cleared", body["quarantines_cleared"])
print("shortcuts cleared  ", body["shortcuts_cleared"])
print("pool edges withheld", body["pool_edges_withheld"])
'
rm -f /tmp/trailmend-reset.json
curl -sS --max-time 30 "$TRAILMEND_API_URL/v1/ready"
echo
