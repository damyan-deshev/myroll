#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

DEMO_DATA_DIR="${MYROLL_DEMO_DATA_DIR:-$PROJECT_ROOT/data/demo}"
DEMO_DB_PATH="${MYROLL_DB_PATH:-$DEMO_DATA_DIR/myroll.dev.sqlite3}"
DEMO_ASSET_DIR="${MYROLL_ASSET_DIR:-$DEMO_DATA_DIR/assets}"
DEMO_BACKUP_DIR="${MYROLL_BACKUP_DIR:-$DEMO_DATA_DIR/backups}"
DEMO_EXPORT_DIR="${MYROLL_EXPORT_DIR:-$DEMO_DATA_DIR/exports}"
VENV_DIR="${MYROLL_VENV_DIR:-$PROJECT_ROOT/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

case "$DEMO_DATA_DIR" in
  "$PROJECT_ROOT"/data/demo|"$PROJECT_ROOT"/data/demo/*|*/data/demo|*/data/demo/*) ;;
  *)
    if [ "${MYROLL_DEMO_ALLOW_UNSAFE_RESET:-}" != "1" ]; then
      echo "Refusing to reset unsafe demo data dir: $DEMO_DATA_DIR" >&2
      echo "Use MYROLL_DEMO_ALLOW_UNSAFE_RESET=1 only for an explicit demo-only directory." >&2
      exit 2
    fi
    ;;
esac

if [ ! -x "$VENV_DIR/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$PROJECT_ROOT/requirements.txt"

rm -rf "$DEMO_DATA_DIR"
mkdir -p "$DEMO_DATA_DIR" "$DEMO_ASSET_DIR" "$DEMO_BACKUP_DIR" "$DEMO_EXPORT_DIR" "$(dirname "$DEMO_DB_PATH")"

export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export MYROLL_DATA_DIR="$DEMO_DATA_DIR"
export MYROLL_DB_PATH="$DEMO_DB_PATH"
export MYROLL_ASSET_DIR="$DEMO_ASSET_DIR"
export MYROLL_BACKUP_DIR="$DEMO_BACKUP_DIR"
export MYROLL_EXPORT_DIR="$DEMO_EXPORT_DIR"
export MYROLL_SEED_MODE="none"

python -m backend.app.db.migrate upgrade
python -m backend.app.db.demo_seed

echo "Demo data reset at: $DEMO_DATA_DIR"
