#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DEMO_DATA_DIR="${MYROLL_DEMO_DATA_DIR:-$PROJECT_ROOT/data/demo}"

if [ "${MYROLL_DEMO_RESET:-}" = "1" ] || [ ! -s "${MYROLL_DB_PATH:-$DEMO_DATA_DIR/myroll.dev.sqlite3}" ]; then
  MYROLL_DEMO_DATA_DIR="$DEMO_DATA_DIR" "$PROJECT_ROOT/scripts/reset_demo.sh"
fi

export MYROLL_DATA_DIR="$DEMO_DATA_DIR"
export MYROLL_DB_PATH="${MYROLL_DB_PATH:-$DEMO_DATA_DIR/myroll.dev.sqlite3}"
export MYROLL_ASSET_DIR="${MYROLL_ASSET_DIR:-$DEMO_DATA_DIR/assets}"
export MYROLL_BACKUP_DIR="${MYROLL_BACKUP_DIR:-$DEMO_DATA_DIR/backups}"
export MYROLL_EXPORT_DIR="${MYROLL_EXPORT_DIR:-$DEMO_DATA_DIR/exports}"
export MYROLL_SEED_MODE="none"

exec "$PROJECT_ROOT/scripts/start_dev.sh"
