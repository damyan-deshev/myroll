#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

BACKEND_HOST="${MYROLL_BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${MYROLL_BACKEND_PORT:-8000}"
FRONTEND_HOST="${MYROLL_FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${MYROLL_FRONTEND_PORT:-5173}"
BACKEND_URL="http://$BACKEND_HOST:$BACKEND_PORT"
HEALTH_URL="$BACKEND_URL/health"

BACKEND_PID=""

cleanup() {
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}

wait_for_health() {
  local attempts=90
  local attempt=1
  while [ "$attempt" -le "$attempts" ]; do
    if command -v curl >/dev/null 2>&1; then
      if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
        return 0
      fi
    else
      if python3 - "$HEALTH_URL" >/dev/null 2>&1 <<'PY'
import sys
import urllib.request

urllib.request.urlopen(sys.argv[1], timeout=1).read()
PY
      then
        return 0
      fi
    fi
    sleep 1
    attempt=$((attempt + 1))
  done
  echo "Backend did not become healthy at $HEALTH_URL" >&2
  return 1
}

trap cleanup EXIT INT TERM

MYROLL_HOST="$BACKEND_HOST" MYROLL_PORT="$BACKEND_PORT" "$PROJECT_ROOT/scripts/start_backend.sh" &
BACKEND_PID="$!"

wait_for_health

npm --prefix "$PROJECT_ROOT/frontend" install

MYROLL_BACKEND_URL="$BACKEND_URL" MYROLL_FRONTEND_PORT="$FRONTEND_PORT" \
  npm --prefix "$PROJECT_ROOT/frontend" run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
