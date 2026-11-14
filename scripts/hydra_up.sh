#!/usr/bin/env bash
set -euo pipefail
mkdir -p hydradb-data/cache hydradb-data/minio
[ -f hydradb-data/auth-token ] || printf 'local-development-token-32-bytes' > hydradb-data/auth-token
UID="$(id -u)" GID="$(id -g)" docker compose up -d
for _ in $(seq 1 60); do
  if uv run python -c "from trailmend.graph.client import HydraClient as H; H('http://127.0.0.1:8443','local-development-token-32-bytes','default','cell-0',10).require_writable()" 2>/dev/null; then
    echo "hydradb writable"; exit 0
  fi
  sleep 2
done
echo "hydradb did not become writable; see: docker compose logs hydradb" >&2
exit 1
