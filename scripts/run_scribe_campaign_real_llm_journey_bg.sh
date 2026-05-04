#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

RUN_ROOT="${MYROLL_E2E_RUN_ROOT:-$PROJECT_ROOT/artifacts/e2e/scribe-campaign-real-bg}"

MYROLL_E2E_LANGUAGE="bg" \
MYROLL_E2E_RUN_ROOT="$RUN_ROOT" \
MYROLL_E2E_REPORT_PATH="${MYROLL_E2E_REPORT_PATH:-$RUN_ROOT/scribe-campaign-real-bg-report.md}" \
MYROLL_E2E_REPORT_JSON_PATH="${MYROLL_E2E_REPORT_JSON_PATH:-$RUN_ROOT/scribe-campaign-real-bg-report.json}" \
  "$SCRIPT_DIR/run_scribe_campaign_real_llm_journey.sh"
