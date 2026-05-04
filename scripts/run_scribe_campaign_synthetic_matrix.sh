#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

MATRIX_ROOT="${MYROLL_E2E_MATRIX_ROOT:-$PROJECT_ROOT/artifacts/e2e/scribe-campaign-synthetic-matrix}"
SCENARIOS=(
  synth_inquest_bg
  synth_heist_bg
  synth_expedition_bg
  synth_quarantine_bg
  synth_naval_bg
  synth_oasis_rtl_bg
)

rm -rf "$MATRIX_ROOT"
mkdir -p "$MATRIX_ROOT"

failures=0
for scenario in "${SCENARIOS[@]}"; do
  run_root="$MATRIX_ROOT/$scenario"
  report_path="$run_root/report.md"
  report_json_path="$run_root/report.json"
  echo "=== Scribe synthetic scenario: $scenario ==="
  if MYROLL_E2E_SCENARIO="$scenario" \
    MYROLL_E2E_LANGUAGE="bg" \
    MYROLL_E2E_RUN_ROOT="$run_root" \
    MYROLL_E2E_REPORT_PATH="$report_path" \
    MYROLL_E2E_REPORT_JSON_PATH="$report_json_path" \
    "$SCRIPT_DIR/run_scribe_campaign_real_llm_journey.sh"; then
    echo "$scenario passed"
  else
    echo "$scenario failed" >&2
    failures=$((failures + 1))
  fi
done

node - "$MATRIX_ROOT" "${SCENARIOS[@]}" "$failures" <<'NODE'
const fs = require("fs");
const path = require("path");

const args = process.argv.slice(2);
const root = args[0];
const failures = Number(args[args.length - 1]);
const scenarios = args.slice(1, -1);
const categories = ["backend_contract", "product_quality", "model_behavior"];
const reports = scenarios.map((scenario) => {
  const file = path.join(root, scenario, "report.json");
  if (!fs.existsSync(file)) return { scenario: { id: scenario, title: scenario }, missing: true, checks: [] };
  return JSON.parse(fs.readFileSync(file, "utf8"));
});

const summary = {
  generatedAt: new Date().toISOString(),
  scenarioCount: scenarios.length,
  processFailures: failures,
  categories: {},
  scenarios: [],
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
  const checks = report.checks || [];
  summary.scenarios.push({
    id: report.scenario?.id,
    title: report.scenario?.title,
    passed: checks.filter((check) => check.pass).length,
    total: checks.length,
    contractFailures: checks.filter((check) => !check.pass && check.severity === "critical").map((check) => ({
      category: check.category,
      severity: check.severity,
      name: check.name,
      details: check.details,
    })),
    reviewSignals: checks.filter((check) => !check.pass && check.severity !== "critical").map((check) => ({
      category: check.category,
      severity: check.severity,
      name: check.name,
      details: check.details,
    })),
    acceptedMemory: report.recap?.acceptedMemory?.length ?? 0,
    linkedCandidateCount: report.bridge?.linkedCandidateCount ?? 0,
    droppedMarkerLinkCount: report.bridge?.droppedMarkerLinkCount ?? 0,
  });
  for (const check of checks) {
    summary.checks[check.name] ??= { category: check.category, severity: check.severity, passed: 0, total: 0, failures: [] };
    summary.checks[check.name].total += 1;
    if (check.pass) summary.checks[check.name].passed += 1;
    else summary.checks[check.name].failures.push({ scenario: report.scenario?.id, details: check.details });
  }
}

fs.writeFileSync(path.join(root, "summary.json"), `${JSON.stringify(summary, null, 2)}\n`);
const lines = [
  "# Scribe Synthetic Scenario Matrix",
  "",
  `Generated: ${summary.generatedAt}`,
  `Scenarios: ${summary.scenarioCount}`,
  `Process failures: ${summary.processFailures}`,
  "",
  "## Categories",
  ...categories.map((category) => `- ${category.replace("_", " ")}: ${summary.categories[category].passed}/${summary.categories[category].total} passed`),
  "",
  "## Scenarios",
  ...summary.scenarios.map((item) =>
    [
      `### ${item.id}: ${item.title}`,
      `Checks: ${item.passed}/${item.total}`,
      `Accepted memory: ${item.acceptedMemory}`,
      `Linked candidates: ${item.linkedCandidateCount}`,
      `Dropped marker links: ${item.droppedMarkerLinkCount}`,
      ...(item.contractFailures.length
        ? ["Contract failures:", ...item.contractFailures.map((failure) => `- [${failure.category}/${failure.severity}] ${failure.name}: ${failure.details}`)]
        : ["Contract failures: none"]),
      ...(item.reviewSignals.length
        ? ["Human-review signals:", ...item.reviewSignals.map((signal) => `- [${signal.category}/${signal.severity}] ${signal.name}: ${signal.details}`)]
        : ["Human-review signals: none"]),
      "",
    ].join("\n"),
  ),
  "## Cross-Scenario Checks",
  ...Object.entries(summary.checks).map(([name, item]) => `- ${item.passed}/${item.total} ${name}${item.failures.length ? `; failures: ${item.failures.map((failure) => `${failure.scenario}: ${failure.details}`).join(" | ")}` : ""}`),
  "",
];
fs.writeFileSync(path.join(root, "summary.md"), lines.join("\n"));
console.log(`Matrix summary: ${path.join(root, "summary.md")}`);
NODE

if [ "$failures" -gt 0 ]; then
  exit 1
fi
