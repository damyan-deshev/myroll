#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

VENV_DIR="${MYROLL_VENV_DIR:-$PROJECT_ROOT/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$PROJECT_ROOT/requirements.txt"

export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

DATA_DIR="${MYROLL_DATA_DIR:-$PROJECT_ROOT/data}"
DB_PATH="${MYROLL_DB_PATH:-$DATA_DIR/myroll.dev.sqlite3}"
ASSET_DIR="${MYROLL_ASSET_DIR:-$DATA_DIR/assets}"
BACKUP_DIR="${MYROLL_BACKUP_DIR:-$DATA_DIR/backups}"
EXPORT_DIR="${MYROLL_EXPORT_DIR:-$DATA_DIR/exports}"
SEED_MODE="${MYROLL_SEED_MODE:-dev}"

export MYROLL_DATA_DIR="$DATA_DIR"
export MYROLL_DB_PATH="$DB_PATH"
export MYROLL_ASSET_DIR="$ASSET_DIR"
export MYROLL_BACKUP_DIR="$BACKUP_DIR"
export MYROLL_EXPORT_DIR="$EXPORT_DIR"
export MYROLL_SEED_MODE="$SEED_MODE"

mkdir -p "$DATA_DIR" "$ASSET_DIR" "$BACKUP_DIR" "$EXPORT_DIR" "$(dirname "$DB_PATH")"

python -m backend.app.db.backup
python -m backend.app.db.migrate upgrade
if [ "$SEED_MODE" != "none" ]; then
  python -m backend.app.db.seed
else
  echo "Skipping dev seed because MYROLL_SEED_MODE=none."
fi

HOST="${MYROLL_HOST:-127.0.0.1}"
PORT="${MYROLL_PORT:-8000}"

exec uvicorn backend.app.main:app --host "$HOST" --port "$PORT"
