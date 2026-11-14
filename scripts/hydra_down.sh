#!/usr/bin/env bash
set -euo pipefail
docker compose down
./scripts/s3_dev.sh stop
