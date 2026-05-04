#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

BACKEND_HOST="${MYROLL_E2E_BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${MYROLL_E2E_BACKEND_PORT:-18181}"
FRONTEND_HOST="${MYROLL_E2E_FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${MYROLL_E2E_FRONTEND_PORT:-15174}"
BACKEND_URL="http://$BACKEND_HOST:$BACKEND_PORT"
FRONTEND_URL="http://$FRONTEND_HOST:$FRONTEND_PORT"

RUN_ROOT="${MYROLL_E2E_RUN_ROOT:-$PROJECT_ROOT/artifacts/e2e/scribe-campaign-real}"
DATA_DIR="$RUN_ROOT/data"
LOG_DIR="$RUN_ROOT/logs"
DB_PATH="$DATA_DIR/myroll.e2e.sqlite3"
REPORT_PATH="${MYROLL_E2E_REPORT_PATH:-$RUN_ROOT/scribe-campaign-real-report.md}"
REPORT_JSON_PATH="${MYROLL_E2E_REPORT_JSON_PATH:-$RUN_ROOT/scribe-campaign-real-report.json}"

LLM_BASE_URL="${MYROLL_E2E_LLM_BASE_URL:-http://192.168.1.117:1234/v1}"
LLM_MODEL="${MYROLL_E2E_LLM_MODEL:-Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-Q8_K_P}"

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}

wait_for_url() {
  local url="$1"
  local label="$2"
  local attempts=90
  local attempt=1
  while [ "$attempt" -le "$attempts" ]; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    attempt=$((attempt + 1))
  done
  echo "$label did not become ready at $url" >&2
  return 1
}

trap cleanup EXIT INT TERM

rm -rf "$RUN_ROOT"
mkdir -p "$DATA_DIR/assets" "$DATA_DIR/backups" "$DATA_DIR/exports" "$LOG_DIR"

MYROLL_DATA_DIR="$DATA_DIR" \
MYROLL_DB_PATH="$DB_PATH" \
MYROLL_ASSET_DIR="$DATA_DIR/assets" \
MYROLL_BACKUP_DIR="$DATA_DIR/backups" \
MYROLL_EXPORT_DIR="$DATA_DIR/exports" \
MYROLL_SEED_MODE="none" \
MYROLL_HOST="$BACKEND_HOST" \
MYROLL_PORT="$BACKEND_PORT" \
MYROLL_ALLOWED_ORIGINS="$FRONTEND_URL" \
  "$PROJECT_ROOT/scripts/start_backend.sh" >"$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID="$!"

wait_for_url "$BACKEND_URL/health" "Backend"

MYROLL_BACKEND_URL="$BACKEND_URL" \
MYROLL_FRONTEND_PORT="$FRONTEND_PORT" \
  npm --prefix "$PROJECT_ROOT/frontend" run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" >"$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID="$!"

wait_for_url "$FRONTEND_URL" "Frontend"

PLAYWRIGHT_BASE_URL="$FRONTEND_URL" \
MYROLL_E2E_API_BASE="$BACKEND_URL" \
MYROLL_E2E_DB_PATH="$DB_PATH" \
MYROLL_E2E_REAL_LLM="1" \
MYROLL_E2E_LLM_BASE_URL="$LLM_BASE_URL" \
MYROLL_E2E_LLM_MODEL="$LLM_MODEL" \
MYROLL_E2E_REPORT_PATH="$REPORT_PATH" \
MYROLL_E2E_REPORT_JSON_PATH="$REPORT_JSON_PATH" \
  npm --prefix "$PROJECT_ROOT/frontend" run test:e2e -- scribe-campaign-real.spec.ts

echo "Report: $REPORT_PATH"
echo "Report JSON: $REPORT_JSON_PATH"
