#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

COUNT="${MYROLL_E2E_REPEAT_COUNT:-3}"
REPEAT_ROOT="${MYROLL_E2E_REPEAT_ROOT:-$PROJECT_ROOT/artifacts/e2e/scribe-campaign-real-repeat}"
LANGUAGE="${MYROLL_E2E_LANGUAGE:-en}"

rm -rf "$REPEAT_ROOT"
mkdir -p "$REPEAT_ROOT"

failures=0
for index in $(seq 1 "$COUNT"); do
  run_root="$REPEAT_ROOT/run-$index"
  report_path="$run_root/report.md"
  report_json_path="$run_root/report.json"
  echo "=== Scribe real journey repeat $index/$COUNT ($LANGUAGE) ==="
  if MYROLL_E2E_RUN_ROOT="$run_root" \
    MYROLL_E2E_REPORT_PATH="$report_path" \
    MYROLL_E2E_REPORT_JSON_PATH="$report_json_path" \
    MYROLL_E2E_LANGUAGE="$LANGUAGE" \
    "$SCRIPT_DIR/run_scribe_campaign_real_llm_journey.sh"; then
    echo "repeat $index passed"
  else
    echo "repeat $index failed" >&2
    failures=$((failures + 1))
  fi
done

node - "$REPEAT_ROOT" "$COUNT" "$failures" <<'NODE'
const fs = require("fs");
const path = require("path");

const root = process.argv[2];
const expected = Number(process.argv[3]);
const failures = Number(process.argv[4]);
const categories = ["backend_contract", "product_quality", "model_behavior"];
const reports = [];

for (let index = 1; index <= expected; index += 1) {
  const file = path.join(root, `run-${index}`, "report.json");
  if (!fs.existsSync(file)) {
    reports.push({ index, missing: true, checks: [] });
    continue;
  }
  reports.push({ index, ...JSON.parse(fs.readFileSync(file, "utf8")) });
}

const summary = {
  generatedAt: new Date().toISOString(),
  runCount: expected,
  processFailures: failures,
  categories: {},
  checks: {},
};

for (const category of categories) {
  const checks = reports.flatMap((report) => (report.checks || []).filter((check) => check.category === category));
  summary.categories[category] = {
    passed: checks.filter((check) => check.pass).length,
    total: checks.length,
  };
}

for (const report of reports) {
  for (const check of report.checks || []) {
    summary.checks[check.name] ??= { category: check.category, severity: check.severity, passed: 0, total: 0, failures: [] };
    summary.checks[check.name].total += 1;
    if (check.pass) summary.checks[check.name].passed += 1;
    else summary.checks[check.name].failures.push({ run: report.index, details: check.details });
  }
}

fs.writeFileSync(path.join(root, "summary.json"), `${JSON.stringify(summary, null, 2)}\n`);
const lines = [
  "# Scribe Real Journey Repeat Summary",
  "",
  `Generated: ${summary.generatedAt}`,
  `Runs requested: ${expected}`,
  `Process failures: ${failures}`,
  "",
  "## Categories",
  ...categories.map((category) => `- ${category.replace("_", " ")}: ${summary.categories[category].passed}/${summary.categories[category].total} passed`),
  "",
  "## Checks",
  ...Object.entries(summary.checks).map(([name, item]) => `- ${item.passed}/${item.total} ${name}${item.failures.length ? `; failures: ${item.failures.map((failure) => `run ${failure.run}: ${failure.details}`).join(" | ")}` : ""}`),
  "",
];
fs.writeFileSync(path.join(root, "summary.md"), lines.join("\n"));
console.log(`Repeat summary: ${path.join(root, "summary.md")}`);
NODE

if [ "$failures" -gt 0 ]; then
  exit 1
fi
