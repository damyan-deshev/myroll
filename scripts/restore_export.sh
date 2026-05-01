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
python -m pip install -r "$PROJECT_ROOT/requirements.txt" >/dev/null

export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

python -m backend.app.db.restore_export "$@"
