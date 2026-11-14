#!/usr/bin/env bash
set -euo pipefail
PORT="${TRAILMEND_S3_PORT:-5000}"
BUCKET="${TRAILMEND_S3_BUCKET:-hydradb}"
PID_FILE="hydradb-data/moto.pid"
LOG_FILE="hydradb-data/moto.log"

case "${1:-start}" in
start)
  mkdir -p hydradb-data
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "s3 stand-in already running on port $PORT (pid $(cat "$PID_FILE"))"
  else
    nohup uv run moto_server --host 0.0.0.0 --port "$PORT" >"$LOG_FILE" 2>&1 &
    echo $! >"$PID_FILE"
  fi
  for _ in $(seq 1 40); do
    if curl -fsS -o /dev/null -X PUT "http://127.0.0.1:$PORT/$BUCKET" 2>/dev/null; then
      echo "s3 stand-in ready on port $PORT with bucket $BUCKET"
      exit 0
    fi
    sleep 1
  done
  echo "s3 stand-in did not answer on port $PORT; see $LOG_FILE" >&2
  exit 1
  ;;
stop)
  if [ -f "$PID_FILE" ]; then
    kill "$(cat "$PID_FILE")" 2>/dev/null || true
    rm -f "$PID_FILE"
  fi
  echo "s3 stand-in stopped"
  ;;
*)
  echo "usage: $0 [start|stop]" >&2
  exit 2
  ;;
esac
