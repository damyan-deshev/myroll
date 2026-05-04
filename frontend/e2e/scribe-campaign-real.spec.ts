import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type APIRequestContext, type APIResponse } from "@playwright/test";

const enabled = process.env.MYROLL_E2E_REAL_LLM === "1";
const apiBase = process.env.MYROLL_E2E_API_BASE ?? "http://127.0.0.1:8000";
const dbPath = process.env.MYROLL_E2E_DB_PATH ?? "";
const llmBaseUrl = (process.env.MYROLL_E2E_LLM_BASE_URL ?? "http://192.168.1.117:1234/v1").replace(/\/$/, "");
const defaultLlmModel = "Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-Q8_K_P";
const llmModelEnv = process.env.MYROLL_E2E_LLM_MODEL;
const artifactsRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../artifacts/e2e/scribe-campaign-real");
const screenshotDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../artifacts/playwright");
const reportPath = process.env.MYROLL_E2E_REPORT_PATH ?? path.join(artifactsRoot, "scribe-campaign-real-report.md");
const reportJsonPath = process.env.MYROLL_E2E_REPORT_JSON_PATH ?? path.join(artifactsRoot, "scribe-campaign-real-report.json");
const baselineReportJsonPath =
  process.env.MYROLL_E2E_BASELINE_REPORT_JSON ??
  path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../artifacts/e2e/scribe-campaign-real-baseline/before-tightening-report.json");
const journeyLanguage = process.env.MYROLL_E2E_LANGUAGE === "bg" ? "bg" : "en";

test.skip(!enabled, "Set MYROLL_E2E_REAL_LLM=1 to run the real llama.cpp campaign Scribe journey.");

type JsonObject = Record<string, unknown>;
type Campaign = { id: string; name: string };
type Session = { id: string; title: string };
type Scene = { id: string; title: string };
type PlayerDisplay = Record<string, unknown>;
type ProviderProfile = { id: string; label: string; conformance_level: string };
type ContextPackage = { id: string; rendered_prompt: string; source_refs: JsonObject[]; source_classes: string[]; warnings: JsonObject[]; review_status: string };
type TranscriptEvent = { id: string; body: string; order_index: number; created_at: string; updated_at: string };
type BuildBranchResult = {
  run: { id: string; task_kind: string; status: string; repair_attempted: boolean; error_code?: string | null; parse_failure_reason?: string | null };
  proposal_set: null | {
    proposal_set: { id: string; title: string; option_count: number; degraded: boolean; repair_attempted: boolean };
    options: ProposalOption[];
    planning_markers: PlanningMarker[];
    normalization_warnings: JsonObject[];
  };
  rejected_options: JsonObject[];
  warnings: JsonObject[];
};
type ProposalOption = {
  id: string;
  title: string;
  summary: string;
  body: string;
  consequences: string;
  reveals: string;
  stays_hidden: string;
  planning_marker_text: string;
  status: string;
  active_planning_marker_id?: string | null;
};
type PlanningMarker = {
  id: string;
  title: string;
  marker_text: string;
  status: string;
  scope_kind: string;
  provenance: JsonObject;
  lint_warnings: string[];
  canonized_at?: string | null;
  canon_memory_entry_id?: string | null;
};
type BuildRecapResult = {
  run: { id: string; task_kind: string; status: string; repair_attempted: boolean; error_code?: string | null; parse_failure_reason?: string | null };
  bundle: {
    privateRecap?: { title?: string; bodyMarkdown?: string; keyMoments?: JsonObject[] };
    memoryCandidateDrafts?: JsonObject[];
    continuityWarnings?: JsonObject[];
    unresolvedThreads?: string[];
  };
  candidates: Array<{
    id: string;
    title: string;
    body: string;
    claim_strength: string;
    validation_errors: string[];
    source_planning_marker_id?: string | null;
    source_proposal_option_id?: string | null;
    normalization_warnings?: string[];
    normalization_warning_details?: JsonObject[];
  }>;
  rejected_drafts: JsonObject[];
};
type MemoryEntry = { id: string; title: string; body: string; source_planning_marker_id?: string | null; source_proposal_option_id?: string | null };
type RecallResult = { expanded_terms: string[]; hits: Array<{ source_kind: string; title: string; excerpt: string; score: number }> };

type JourneyCheck = {
  name: string;
  pass: boolean;
  severity: "critical" | "warning" | "info";
  details: string;
};

type JourneyReport = {
  generatedAt: string;
  provider: { baseUrl: string; model: string; conformanceLevel?: string };
  campaign: { id?: string; sessionId?: string; sceneId?: string };
  notes: Array<{ label: string; campaignClock: string; eventId: string; orderIndex: number; body: string }>;
  branch: {
    instruction?: string;
    options: Array<Pick<ProposalOption, "title" | "summary" | "body" | "consequences" | "reveals" | "stays_hidden" | "planning_marker_text" | "status">>;
    chosenOptionIndex?: number;
    chosenMarker?: PlanningMarker;
    selectedWithoutMarkerPromptExcerpt?: string;
    futurePromptPlanningExcerpt?: string;
  };
  recap: {
    title?: string;
    bodyMarkdown?: string;
    keyMoments?: JsonObject[];
    candidates: BuildRecapResult["candidates"];
    rejectedDrafts: JsonObject[];
    acceptedMemory: MemoryEntry[];
    recall?: RecallResult;
  };
  bridge: {
    linkedCandidateCount: number;
    droppedMarkerLinkCount: number;
    canonizedMarkerStatus?: string;
    canonizedOptionStatus?: string;
    futurePromptAfterAcceptExcerpt?: string;
  };
  checks: JourneyCheck[];
  observations: string[];
  screenshots: string[];
};

type JourneyScenario = {
  language: "en" | "bg";
  campaignNamePrefix: string;
  campaignDescription: string;
  sessionTitlePrefix: string;
  sceneTitlePrefix: string;
  sceneSummary: string;
  labels: { opening: string; pressure: string; mistaken: string; correction: string; playedBranch: string; resolution: string };
  notes: {
    opening: string;
    pressure: string;
    mistaken: string;
    correction: string;
    playedBranch: (chosenTitle: string) => string;
    resolution: string;
  };
  branchInstruction: string;
  selectedWithoutMarkerInstruction: string;
  futureMarkerInstruction: string;
  recapInstruction: string;
  postAcceptInstruction: string;
  recapFallbackTitle: string;
  recallQuery: string;
  option2Anchor: string;
  option2Patterns: RegExp[];
  recapCoreAnchors: string[];
  chosenPlayedPatterns: RegExp[];
  blueFlamePatterns: RegExp[];
  correctedMistakeForbidden: string[];
};

const scenarios: Record<"en" | "bg", JourneyScenario> = {
  en: {
    language: "en",
    campaignNamePrefix: "Real Campaign Journey",
    campaignDescription: "A dark-fairytale campaign arc around Aureon, Mira, Captain Varos, and the Moon Gate.",
    sessionTitlePrefix: "Moon Gate Session",
    sceneTitlePrefix: "Moon Gate Courtyard",
    sceneSummary: "A dawn-bound gate, a goldsmith patron, and a watch captain who wants leverage.",
    labels: {
      opening: "opening",
      pressure: "pressure",
      mistaken: "mistaken detail",
      correction: "correction",
      playedBranch: "played branch",
      resolution: "resolution",
    },
    notes: {
      opening:
        "[Campaign clock 19:05] Aureon the goldsmith gives Mira a moon-silver coin and says the Moon Gate opens only at dawn. Mira promises to return the coin after the dawn ritual.",
      pressure:
        "[Campaign clock 19:40] Captain Varos arrives with city guards. He wants political leverage over the gate ritual but has not yet betrayed anyone.",
      mistaken: "[Campaign clock 20:05] Dictation mistake: Mira gives Aureon a silver ring before the gate opens.",
      correction:
        "[Campaign clock 20:07 correction] Mira does not give a ring; she keeps Aureon's moon-silver coin as the ritual key.",
      playedBranch: (chosenTitle) =>
        `[Campaign clock 21:10] Played event: the table follows option 2, "${chosenTitle}". In actual play, Captain Varos recognizes that Aureon's moon-silver coin is also a seal tied to royal authority. Varos offers to let the dawn ritual proceed if Mira allows the city to inspect the coin after the gate opens. Mira refuses to surrender the coin before dawn but agrees to parley afterward, and Aureon warns again that the moon-silver coin must be returned at dawn.`,
      resolution:
        "[Campaign clock 21:45] At dawn the Moon Gate opens. The party sees a blue-flame map beyond the gate, and Mira still holds the moon-silver coin.",
    },
    branchInstruction: [
      "The party is stalled at the Moon Gate with Aureon, Mira, and Captain Varos.",
      "Give exactly three distinct branch directions.",
      "Option 2 should be a political negotiation complication around Captain Varos and the dawn ritual.",
      "All options are speculative planning, not played history. Keep planning marker text concise.",
    ].join("\n"),
    selectedWithoutMarkerInstruction: "Follow up after selecting an option but before adopting a marker.",
    futureMarkerInstruction: "What follows from the adopted planning marker?",
    recapInstruction: [
      "Build a private session recap from the played evidence.",
      "Planning markers are GM intent only; do not report them as events unless a later live capture supports them.",
      "Create memoryCandidateDrafts only for directly evidenced or strong-inference facts.",
      "Expected anchors: Aureon, Mira, moon-silver coin, dawn ritual, Captain Varos political negotiation, blue-flame map.",
    ].join("\n"),
    postAcceptInstruction: "Check canonized planning bridge context after memory accept.",
    recapFallbackTitle: "Moon Gate recap",
    recallQuery: "Aureon Mira moon-silver coin Varos dawn",
    option2Anchor: "Varos",
    option2Patterns: [/\bpolitic/i, /\bnegotiat/i, /\bleverage/i, /\btithe/i, /\btoll/i, /\bcity\b/i, /\bcrown\b/i, /\bguard/i],
    recapCoreAnchors: ["Aureon", "Mira", "moon-silver coin", "dawn", "Varos"],
    chosenPlayedPatterns: [/Dawn Complication/i, /royal authority/i, /inspect the coin/i],
    blueFlamePatterns: [/blue-flame/i],
    correctedMistakeForbidden: ["silver ring"],
  },
  bg: {
    language: "bg",
    campaignNamePrefix: "Истински Scribe тест",
    campaignDescription: "Мрачна приказна кампания около Ауреон, Мира, капитан Варос и Лунната порта.",
    sessionTitlePrefix: "Сесия при Лунната порта",
    sceneTitlePrefix: "Дворът на Лунната порта",
    sceneSummary: "Порта, която се отваря на разсъмване, златар-покровител и капитан на стражата, който търси влияние.",
    labels: {
      opening: "откриване",
      pressure: "натиск",
      mistaken: "грешна диктовка",
      correction: "корекция",
      playedBranch: "изигран избор",
      resolution: "развръзка",
    },
    notes: {
      opening:
        "[Кампанейски час 19:05] Ауреон златарят дава на Мира лунно-сребърна монета и казва, че Лунната порта се отваря само на разсъмване. Мира обещава да върне монетата след ритуала на разсъмване.",
      pressure:
        "[Кампанейски час 19:40] Капитан Варос пристига с градската стража. Той иска политическо влияние върху ритуала при портата, но още не е предал никого.",
      mistaken:
        "[Кампанейски час 20:05] Грешка от диктовка: Мира дава на Ауреон сребърен пръстен преди портата да се отвори.",
      correction:
        "[Кампанейски час 20:07 корекция] Мира не дава пръстен; тя пази лунно-сребърната монета на Ауреон като ключ за ритуала.",
      playedBranch: (chosenTitle) =>
        `[Кампанейски час 21:10] Изиграно събитие: масата следва вариант 2, "${chosenTitle}". В реалната игра капитан Варос разбира, че лунно-сребърната монета на Ауреон е и печат, свързан с царска власт. Варос предлага да позволи ритуалът на разсъмване да продължи, ако Мира позволи на града да провери монетата след отварянето на портата. Мира отказва да предаде монетата преди разсъмване, но се съгласява на преговори след това, а Ауреон отново предупреждава, че лунно-сребърната монета трябва да бъде върната на разсъмване.`,
      resolution:
        "[Кампанейски час 21:45] На разсъмване Лунната порта се отваря. Групата вижда синьо-пламенна карта отвъд портата, а Мира все още държи лунно-сребърната монета.",
    },
    branchInstruction: [
      "Групата е блокирана при Лунната порта с Ауреон, Мира и капитан Варос.",
      "Отговори на български. Дай точно три различни посоки за развитие.",
      "Вариант 2 трябва да бъде политическо усложнение за преговори около капитан Варос и ритуала на разсъмване.",
      "Всички варианти са спекулативно планиране, не изиграна история. Дръж текста за planning marker кратък.",
    ].join("\n"),
    selectedWithoutMarkerInstruction: "Продължи след избран вариант, но преди да има приет planning marker.",
    futureMarkerInstruction: "Какво следва от приетия planning marker? Отговори на български.",
    recapInstruction: [
      "Изгради частно резюме на сесията от изиграните доказателства. Отговори на български.",
      "Planning marker-ите са само намерение на ДМ; не ги описвай като събития, освен ако по-късен live capture не ги подкрепя.",
      "Създай memoryCandidateDrafts само за директно доказани факти или силни изводи.",
      "Очаквани котви: Ауреон, Мира, лунно-сребърна монета, ритуал на разсъмване, политически преговори с капитан Варос, синьо-пламенна карта.",
    ].join("\n"),
    postAcceptInstruction: "Провери контекста след canonization bridge и приемането в memory. Отговори на български.",
    recapFallbackTitle: "Резюме при Лунната порта",
    recallQuery: "Ауреон Мира лунно-сребърна монета Варос разсъмване",
    option2Anchor: "Варос",
    option2Patterns: [/полит/i, /преговор/i, /влияние/i, /натиск/i, /страж/i, /град/i, /царск/i, /власт/i],
    recapCoreAnchors: ["Ауреон", "Мира", "лунно-сребър", "разсъм", "Варос"],
    chosenPlayedPatterns: [/царск/i, /власт/i, /провери монет/i, /преговор/i],
    blueFlamePatterns: [/синьо-пламен/i, /син пламък/i, /синя.*карта/i],
    correctedMistakeForbidden: ["сребърен пръстен", "silver ring"],
  },
};
const scenario = scenarios[journeyLanguage];

function ensureDir(filePath: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function screenshotPath(name: string): string {
  fs.mkdirSync(screenshotDir, { recursive: true });
  return path.join(screenshotDir, name);
}

async function okJson<T>(response: APIResponse, label: string): Promise<T> {
  const text = await response.text();
  expect(response.ok(), `${label}: ${response.status()} ${text}`).toBeTruthy();
  return (text ? JSON.parse(text) : null) as T;
}

async function apiPost<T>(request: APIRequestContext, pathName: string, payload?: unknown, label = pathName): Promise<T> {
  return okJson<T>(
    await request.post(`${apiBase}${pathName}`, payload === undefined ? undefined : { data: payload }),
    label
  );
}

async function apiGet<T>(request: APIRequestContext, pathName: string, label = pathName): Promise<T> {
  return okJson<T>(await request.get(`${apiBase}${pathName}`), label);
}

function normalizeText(value: string): string {
  return value.toLowerCase().replace(/\s+/g, " ").trim();
}

function containsAll(value: string, anchors: string[]): boolean {
  const normalized = normalizeText(value);
  return anchors.every((anchor) => normalized.includes(normalizeText(anchor)));
}

function containsAnyPattern(value: string, patterns: RegExp[]): boolean {
  return patterns.some((pattern) => pattern.test(value));
}

function hasSpeculativeLanguage(value: string): boolean {
  return containsAnyPattern(value, [
    /\bif played\b/i,
    /\bpossible consequence/i,
    /\bmust choose\b/i,
    /\bGM is considering\b/i,
    /\bако се изиграе\b/i,
    /\bако бъде изиграно\b/i,
    /\bвъзможна последица\b/i,
    /\bможе\b/i,
    /\bби мог(ъл|ла|ло|ли)\b/i,
    /\bевентуално\b/i,
    /\bвъзможно е\b/i,
    /\bДМ обмисля\b/i,
    /\bGM обмисля\b/i,
  ]);
}

function promptContains(prompt: string, value: string): boolean {
  const excerpt = normalizeText(value).slice(0, 120);
  if (excerpt.length < 30) return false;
  return normalizeText(prompt).includes(excerpt);
}

function addCheck(report: JourneyReport, check: Omit<JourneyCheck, "severity"> & { severity?: JourneyCheck["severity"] }): void {
  report.checks.push({ severity: check.severity ?? "warning", ...check });
}

async function discoverLlmModel(request: APIRequestContext): Promise<string> {
  const preferred = llmModelEnv ?? defaultLlmModel;
  const response = await request.get(`${llmBaseUrl}/models`, { timeout: 15_000 });
  const body = await okJson<{ data?: Array<{ id?: string; status?: { value?: string } }> }>(response, "llama.cpp /models");
  const models = body.data ?? [];
  const ids = models.map((model) => model.id).filter((id): id is string => Boolean(id));
  expect(ids, `No models returned from ${llmBaseUrl}/models`).not.toHaveLength(0);
  if (ids.includes(preferred)) return preferred;
  const loadedQwen = models.find((model) => model.id?.includes("Qwen3.6-35B-A3B") && model.status?.value !== "unloaded");
  if (loadedQwen?.id) return loadedQwen.id;
  throw new Error(`Preferred model ${preferred} was not advertised by llama.cpp. Available examples: ${ids.slice(0, 8).join(", ")}`);
}

function stampTranscriptEvent(eventId: string, timestamp: string): void {
  if (!dbPath) return;
  const script = [
    "import sqlite3, sys",
    "db_path, event_id, timestamp = sys.argv[1:]",
    "con = sqlite3.connect(db_path)",
    "con.execute('UPDATE session_transcript_events SET created_at = ?, updated_at = ? WHERE id = ?', (timestamp, timestamp, event_id))",
    "con.execute('UPDATE scribe_search_index SET source_revision = ?, updated_at = ? WHERE source_kind = ? AND source_id = ?', (timestamp, timestamp, 'session_transcript_event', event_id))",
    "con.commit()",
    "con.close()",
  ].join("\n");
  execFileSync("python3", ["-c", script, dbPath, eventId, timestamp], { stdio: "pipe" });
}

async function createTimedCapture(
  request: APIRequestContext,
  report: JourneyReport,
  campaignId: string,
  sessionId: string,
  sceneId: string,
  label: string,
  campaignClock: string,
  body: string,
): Promise<TranscriptEvent> {
  const event = await apiPost<TranscriptEvent>(
    request,
    `/api/campaigns/${campaignId}/scribe/transcript-events`,
    { session_id: sessionId, scene_id: sceneId, body, source: "dictation" },
    `capture ${label}`,
  );
  stampTranscriptEvent(event.id, campaignClock);
  const refreshed = await apiGet<{ projection: TranscriptEvent[] }>(
    request,
    `/api/campaigns/${campaignId}/scribe/transcript-events?session_id=${sessionId}`,
    "transcript projection",
  );
  const stamped = refreshed.projection.find((item) => item.id === event.id) ?? event;
  report.notes.push({ label, campaignClock, eventId: stamped.id, orderIndex: stamped.order_index, body });
  return stamped;
}

async function setupCampaign(request: APIRequestContext, runId: number): Promise<{ campaign: Campaign; session: Session; scene: Scene; playerBefore: PlayerDisplay }> {
  await request.post(`${apiBase}/api/runtime/clear`);
  await request.post(`${apiBase}/api/player-display/blackout`);
  const campaign = await apiPost<Campaign>(
    request,
    "/api/campaigns",
    {
      name: `${scenario.campaignNamePrefix} ${runId}`,
      description: scenario.campaignDescription,
    },
    "create campaign",
  );
  const session = await apiPost<Session>(
    request,
    `/api/campaigns/${campaign.id}/sessions`,
    { title: `${scenario.sessionTitlePrefix} ${runId}` },
    "create session",
  );
  const scene = await apiPost<Scene>(
    request,
    `/api/campaigns/${campaign.id}/scenes`,
    {
      title: `${scenario.sceneTitlePrefix} ${runId}`,
      session_id: session.id,
      summary: scenario.sceneSummary,
    },
    "create scene",
  );
  await apiPost(request, "/api/runtime/activate-scene", { scene_id: scene.id }, "activate scene");
  const playerBefore = await apiGet<PlayerDisplay>(request, "/api/player-display", "player before");
  return { campaign, session, scene, playerBefore };
}

async function setupProvider(request: APIRequestContext, label: string, modelId: string): Promise<ProviderProfile> {
  const profile = await apiPost<ProviderProfile>(
    request,
    "/api/llm/provider-profiles",
    {
      label,
      vendor: "custom",
      base_url: llmBaseUrl,
      model_id: modelId,
      key_source: { type: "none", ref: null },
    },
    "create provider",
  );
  const tested = await apiPost<{ profile: ProviderProfile; conformance_level: string }>(
    request,
    `/api/llm/provider-profiles/${profile.id}/test`,
    undefined,
    "test provider",
  );
  expect(tested.conformance_level).toMatch(/level_[12]_json_(best_effort|validated)/);
  return tested.profile;
}

async function reviewedContext(
  request: APIRequestContext,
  campaignId: string,
  payload: JsonObject,
  label: string,
): Promise<ContextPackage> {
  const preview = await apiPost<ContextPackage>(request, `/api/campaigns/${campaignId}/llm/context-preview`, payload, `${label} preview`);
  return apiPost<ContextPackage>(request, `/api/llm/context-packages/${preview.id}/review`, undefined, `${label} review`);
}

function writeReport(report: JourneyReport): void {
  if (fs.existsSync(baselineReportJsonPath)) {
    const baseline = JSON.parse(fs.readFileSync(baselineReportJsonPath, "utf-8")) as JourneyReport;
    const baselineChecks = new Map((baseline.checks ?? []).map((check) => [check.name, check.pass]));
    const progressed = report.checks.filter((check) => baselineChecks.get(check.name) === false && check.pass);
    const regressed = report.checks.filter((check) => baselineChecks.get(check.name) === true && !check.pass);
    report.observations.push(
      `Baseline comparison loaded from ${baselineReportJsonPath}: ${progressed.length} named check(s) improved, ${regressed.length} regressed.`,
    );
    report.observations.push(
      `Baseline accepted memory ${baseline.recap?.acceptedMemory?.length ?? 0} -> ${report.recap.acceptedMemory.length}; rejected drafts ${baseline.recap?.rejectedDrafts?.length ?? 0} -> ${report.recap.rejectedDrafts.length}.`,
    );
  }
  ensureDir(reportPath);
  ensureDir(reportJsonPath);
  fs.writeFileSync(reportJsonPath, `${JSON.stringify(report, null, 2)}\n`);
  const lines: string[] = [
    "# Real Scribe Campaign Journey",
    "",
    `Generated: ${report.generatedAt}`,
    `Provider: ${report.provider.model} at ${report.provider.baseUrl}`,
    `Conformance: ${report.provider.conformanceLevel ?? "unknown"}`,
    "",
    "## Notes Captured",
    ...report.notes.map((note) => `- ${note.campaignClock} · #${note.orderIndex} · ${note.label}: ${note.body}`),
    "",
    "## Branch Proposal Output",
    `Instruction: ${report.branch.instruction ?? ""}`,
    "",
    ...report.branch.options.map((option, index) =>
      [
        `### Option ${index + 1}: ${option.title}`,
        `Status: ${option.status}`,
        `Summary: ${option.summary}`,
        `Possible consequences if played: ${option.consequences}`,
        `May reveal: ${option.reveals}`,
        `Stays hidden: ${option.stays_hidden}`,
        `Marker draft: ${option.planning_marker_text}`,
        "",
        option.body,
        "",
      ].join("\n"),
    ),
    `Chosen option index: ${report.branch.chosenOptionIndex ?? "none"}`,
    report.branch.chosenMarker
      ? `Chosen marker: ${report.branch.chosenMarker.title} · ${report.branch.chosenMarker.marker_text}`
      : "Chosen marker: none",
    "",
    "## Recap Output",
    `Title: ${report.recap.title ?? "none"}`,
    "",
    report.recap.bodyMarkdown ?? "",
    "",
    "### Memory Candidates",
    ...report.recap.candidates.map(
      (candidate) =>
        `- ${candidate.claim_strength} · ${candidate.title}: ${candidate.body}` +
        (candidate.source_planning_marker_id ? ` · linked marker ${candidate.source_planning_marker_id}` : "") +
        (candidate.normalization_warnings?.length ? ` · warnings ${candidate.normalization_warnings.join(", ")}` : ""),
    ),
    report.recap.candidates.length ? "" : "- none",
    "",
    "### Accepted Memory",
    ...report.recap.acceptedMemory.map((entry) => `- ${entry.title}: ${entry.body}`),
    report.recap.acceptedMemory.length ? "" : "- none",
    "",
    "### Recall",
    report.recap.recall
      ? [
          `Expanded terms: ${report.recap.recall.expanded_terms.join(", ")}`,
          ...report.recap.recall.hits.map((hit) => `- ${hit.source_kind} · ${hit.title} · score ${hit.score}: ${hit.excerpt}`),
        ].join("\n")
      : "not run",
    "",
    "## Canonization Bridge",
    `Linked candidate count: ${report.bridge.linkedCandidateCount}`,
    `Dropped marker link count: ${report.bridge.droppedMarkerLinkCount}`,
    `Canonized marker status: ${report.bridge.canonizedMarkerStatus ?? "not observed"}`,
    `Canonized option status: ${report.bridge.canonizedOptionStatus ?? "not observed"}`,
    "",
    "## Checks",
    ...report.checks.map((check) => `- ${check.pass ? "PASS" : "FAIL"} [${check.severity}] ${check.name}: ${check.details}`),
    "",
    "## Observations",
    ...report.observations.map((item) => `- ${item}`),
    "",
    "## Screenshots",
    ...report.screenshots.map((item) => `- ${item}`),
    "",
  ];
  fs.writeFileSync(reportPath, lines.join("\n"));
}

test("real campaign Scribe journey records branch choice, planning marker, recap, memory, and recall", async ({ page, request }) => {
  test.setTimeout(360_000);
  const generatedAt = new Date().toISOString();
  const modelId = await discoverLlmModel(request);
  const report: JourneyReport = {
    generatedAt,
    provider: { baseUrl: llmBaseUrl, model: modelId },
    campaign: {},
    notes: [],
    branch: { options: [] },
    recap: { candidates: [], rejectedDrafts: [], acceptedMemory: [] },
    bridge: { linkedCandidateCount: 0, droppedMarkerLinkCount: 0 },
    checks: [],
    observations: [],
    screenshots: [],
  };

  try {
    const runId = Date.now();
    const { campaign, session, scene, playerBefore } = await setupCampaign(request, runId);
    report.campaign = { id: campaign.id, sessionId: session.id, sceneId: scene.id };
    const provider = await setupProvider(request, `llama.cpp campaign journey ${runId}`, modelId);
    report.provider.conformanceLevel = provider.conformance_level;

    await createTimedCapture(
      request,
      report,
      campaign.id,
      session.id,
      scene.id,
      scenario.labels.opening,
      "2026-05-04T19:05:00Z",
      scenario.notes.opening,
    );
    await createTimedCapture(
      request,
      report,
      campaign.id,
      session.id,
      scene.id,
      scenario.labels.pressure,
      "2026-05-04T19:40:00Z",
      scenario.notes.pressure,
    );
    const mistaken = await createTimedCapture(
      request,
      report,
      campaign.id,
      session.id,
      scene.id,
      scenario.labels.mistaken,
      "2026-05-04T20:05:00Z",
      scenario.notes.mistaken,
    );
    const correction = await apiPost<TranscriptEvent>(
      request,
      `/api/scribe/transcript-events/${mistaken.id}/correct`,
      { body: scenario.notes.correction },
      "correct mistaken capture",
    );
    stampTranscriptEvent(correction.id, "2026-05-04T20:07:00Z");
    report.notes.push({
      label: scenario.labels.correction,
      campaignClock: "2026-05-04T20:07:00Z",
      eventId: correction.id,
      orderIndex: correction.order_index,
      body: scenario.notes.correction,
    });

    const branchInstruction = scenario.branchInstruction;
    report.branch.instruction = branchInstruction;
    const branchContext = await reviewedContext(
      request,
      campaign.id,
      {
        session_id: session.id,
        scene_id: scene.id,
        task_kind: "scene.branch_directions",
        scope_kind: "scene",
        visibility_mode: "gm_private",
        gm_instruction: branchInstruction,
      },
      "branch",
    );
    const branchBuild = await apiPost<BuildBranchResult>(
      request,
      `/api/campaigns/${campaign.id}/llm/branch-directions/build`,
      { provider_profile_id: provider.id, context_package_id: branchContext.id },
      "run branch directions",
    );
    expect(branchBuild.proposal_set, "branch output should create a proposal set").not.toBeNull();
    const branchDetail = branchBuild.proposal_set!;
    report.branch.options = branchDetail.options.map((option) => ({
      title: option.title,
      summary: option.summary,
      body: option.body,
      consequences: option.consequences,
      reveals: option.reveals,
      stays_hidden: option.stays_hidden,
      planning_marker_text: option.planning_marker_text,
      status: option.status,
    }));
    addCheck(report, {
      name: "Branch returned exactly three valid options",
      pass: branchDetail.options.length === 3,
      details: `Model returned ${branchDetail.options.length} valid option(s); rejected rows: ${branchBuild.rejected_options.length}; normalization warnings: ${branchDetail.normalization_warnings.length}.`,
    });
    addCheck(report, {
      name: "Option 2 matches requested political Varos direction",
      pass:
        Boolean(branchDetail.options[1]) &&
        containsAll(`${branchDetail.options[1].title} ${branchDetail.options[1].summary} ${branchDetail.options[1].body}`, [scenario.option2Anchor]) &&
        containsAnyPattern(`${branchDetail.options[1].title} ${branchDetail.options[1].summary} ${branchDetail.options[1].body}`, scenario.option2Patterns),
      details: branchDetail.options[1]?.summary ?? "No option 2.",
    });

    const chosen = branchDetail.options[1] ?? branchDetail.options[0];
    report.branch.chosenOptionIndex = branchDetail.options.indexOf(chosen) + 1;
    await apiPost(request, `/api/proposal-options/${chosen.id}/select`, undefined, "select option before marker");
    const selectedNoMarkerContext = await reviewedContext(
      request,
      campaign.id,
      {
        session_id: session.id,
        scene_id: scene.id,
        task_kind: "scene.branch_directions",
        scope_kind: "scene",
        visibility_mode: "gm_private",
        gm_instruction: scenario.selectedWithoutMarkerInstruction,
      },
      "selected without marker branch",
    );
    report.branch.selectedWithoutMarkerPromptExcerpt = selectedNoMarkerContext.rendered_prompt.slice(0, 1200);
    addCheck(report, {
      name: "Selected option without marker stays out of future context",
      pass: !promptContains(selectedNoMarkerContext.rendered_prompt, chosen.body),
      severity: "critical",
      details: "Checked selected option body against the next rendered branch prompt before marker creation.",
    });

    let marker = await apiPost<PlanningMarker>(
      request,
      `/api/proposal-options/${chosen.id}/create-planning-marker`,
      {
        title: chosen.title,
        marker_text: chosen.planning_marker_text,
        scope_kind: "scene",
        session_id: session.id,
        scene_id: scene.id,
      },
      "create planning marker",
    ).catch(async (error: Error) => {
      if (!String(error.message).includes("409")) throw error;
      return apiPost<PlanningMarker>(
        request,
        `/api/proposal-options/${chosen.id}/create-planning-marker`,
        {
          title: chosen.title,
          marker_text: chosen.planning_marker_text,
          scope_kind: "scene",
          session_id: session.id,
          scene_id: scene.id,
          confirm_warnings: true,
        },
        "confirm planning marker",
      );
    });
    report.branch.chosenMarker = marker;

    const futureBranchContext = await reviewedContext(
      request,
      campaign.id,
      {
        session_id: session.id,
        scene_id: scene.id,
        task_kind: "scene.branch_directions",
        scope_kind: "scene",
        visibility_mode: "gm_private",
        gm_instruction: scenario.futureMarkerInstruction,
      },
      "future branch with marker",
    );
    report.branch.futurePromptPlanningExcerpt = futureBranchContext.rendered_prompt.slice(-1500);
    addCheck(report, {
      name: "Active marker enters future context as planning only",
      pass: futureBranchContext.rendered_prompt.includes("GM intent, not played history") && futureBranchContext.rendered_prompt.includes(marker.marker_text),
      severity: "critical",
      details: "Checked future branch prompt for explicit GM intent wording and marker text.",
    });
    addCheck(report, {
      name: "Raw proposal bodies do not enter future context",
      pass: branchDetail.options.every((option) => !promptContains(futureBranchContext.rendered_prompt, option.body)),
      severity: "critical",
      details: "Checked all proposal option body excerpts against future rendered branch prompt.",
    });

    await createTimedCapture(
      request,
      report,
      campaign.id,
      session.id,
      scene.id,
      scenario.labels.playedBranch,
      "2026-05-04T21:10:00Z",
      scenario.notes.playedBranch(chosen.title),
    );
    await createTimedCapture(
      request,
      report,
      campaign.id,
      session.id,
      scene.id,
      scenario.labels.resolution,
      "2026-05-04T21:45:00Z",
      scenario.notes.resolution,
    );

    const recapInstruction = scenario.recapInstruction;
    const recapContext = await reviewedContext(
      request,
      campaign.id,
      {
        session_id: session.id,
        task_kind: "session.build_recap",
        visibility_mode: "gm_private",
        gm_instruction: recapInstruction,
      },
      "recap",
    );
    addCheck(report, {
      name: "Recap context labels planning marker as not played evidence",
      pass: recapContext.rendered_prompt.includes("GM PLANNING CONTEXT, NOT PLAYED EVENTS") && recapContext.rendered_prompt.includes(marker.marker_text),
      severity: "critical",
      details: "Checked final recap prompt for planning-only heading.",
    });
    addCheck(report, {
      name: "Recap prompt renders transcript chronology as first-class metadata",
      pass: recapContext.rendered_prompt.includes("capturedAt: 2026-05-04T21:10:00Z") && recapContext.rendered_prompt.includes("orderIndex: 4"),
      details: "Checked rendered prompt for explicit capturedAt and orderIndex fields.",
    });
    addCheck(report, {
      name: "Corrected capture replaces mistaken original in recap context",
      pass:
        recapContext.rendered_prompt.includes(scenario.notes.correction) &&
        !recapContext.rendered_prompt.includes(scenario.notes.mistaken),
      severity: "critical",
      details: "Checked rendered prompt projection for correction behavior.",
    });

    const recapBuild = await apiPost<BuildRecapResult>(
      request,
      `/api/campaigns/${campaign.id}/llm/session-recap/build`,
      { session_id: session.id, provider_profile_id: provider.id, context_package_id: recapContext.id },
      "run session recap",
    );
    report.recap.title = recapBuild.bundle.privateRecap?.title;
    report.recap.bodyMarkdown = recapBuild.bundle.privateRecap?.bodyMarkdown;
    report.recap.keyMoments = recapBuild.bundle.privateRecap?.keyMoments;
    report.recap.candidates = recapBuild.candidates;
    report.recap.rejectedDrafts = recapBuild.rejected_drafts;
    const recapText = `${report.recap.title ?? ""}\n${report.recap.bodyMarkdown ?? ""}`;
    addCheck(report, {
      name: "Recap includes core played anchors",
      pass: containsAll(recapText, scenario.recapCoreAnchors),
      details: `Expected anchors: ${scenario.recapCoreAnchors.join(", ")}.`,
    });
    addCheck(report, {
      name: "Recap reflects the chosen option after DM records it as played",
      pass:
        containsAnyPattern(recapText, [
          ...scenario.chosenPlayedPatterns,
          new RegExp(chosen.title.replace(/^The\s+/i, "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i"),
        ]) || containsAll(recapText, chosen.summary.split(/\s+/).filter((word) => word.length > 5).slice(0, 2)),
      details: `Chosen option was "${chosen.title}" with summary "${chosen.summary}"; played note used royal-authority/coin-inspection facts instead of copying proposal consequences.`,
    });
    addCheck(report, {
      name: "Recap includes played blue-flame resolution",
      pass: containsAnyPattern(recapText, scenario.blueFlamePatterns),
      details: "Expected the 21:45 played resolution to appear in the recap.",
    });
    addCheck(report, {
      name: "Recap avoids speculative proposal phrasing",
      pass: !hasSpeculativeLanguage(recapText),
      details: "Checked recap body/title for if played, possible consequence, must choose, and GM is considering.",
    });
    addCheck(report, {
      name: "Recap does not repeat corrected ring mistake",
      pass: scenario.correctedMistakeForbidden.every((value) => !normalizeText(recapText).includes(normalizeText(value))),
      severity: "critical",
      details: "The original mistaken capture should not survive projection.",
    });
    addCheck(report, {
      name: "Model produced memory candidates",
      pass: recapBuild.candidates.length > 0,
      details: `${recapBuild.candidates.length} valid candidate(s), ${recapBuild.rejected_drafts.length} rejected draft(s).`,
    });
    const linkedCandidates = recapBuild.candidates.filter((candidate) => candidate.source_planning_marker_id === marker.id);
    const droppedMarkerLinks = recapBuild.candidates.filter((candidate) => candidate.normalization_warnings?.includes("planning_marker_link_ignored"));
    report.bridge.linkedCandidateCount = linkedCandidates.length;
    report.bridge.droppedMarkerLinkCount = droppedMarkerLinks.length;
    addCheck(report, {
      name: "Model linkage quality: recap candidate linked to chosen marker",
      pass: linkedCandidates.length > 0,
      severity: "info",
      details:
        linkedCandidates.length > 0
          ? `${linkedCandidates.length} candidate(s) linked to the chosen planning marker.`
          : `No candidate linked to the chosen marker; dropped-link warnings: ${droppedMarkerLinks.length}. Backend validation remains strict.`,
    });
    addCheck(report, {
      name: "Accepted memory candidates avoid speculative evidence language",
      pass: recapBuild.candidates.every((candidate) => !hasSpeculativeLanguage(`${candidate.title} ${candidate.body}`)),
      details: "Checked valid candidate titles/bodies for speculative proposal wording.",
    });

    await apiPost(
      request,
      `/api/campaigns/${campaign.id}/scribe/session-recaps`,
      {
        session_id: session.id,
        title: report.recap.title ?? scenario.recapFallbackTitle,
        body_markdown: report.recap.bodyMarkdown ?? "No recap body returned.",
        source_llm_run_id: recapBuild.run.id,
        evidence_refs: recapContext.source_refs,
      },
      "save recap",
    );
    for (const candidate of recapBuild.candidates) {
      if (!["directly_evidenced", "strong_inference"].includes(candidate.claim_strength) || candidate.validation_errors.length) continue;
      try {
        const entry = await apiPost<MemoryEntry>(request, `/api/scribe/memory-candidates/${candidate.id}/accept`, undefined, `accept ${candidate.title}`);
        report.recap.acceptedMemory.push(entry);
      } catch (error) {
        report.observations.push(`Could not accept candidate ${candidate.title}: ${String(error)}`);
      }
    }
    addCheck(report, {
      name: "At least one memory candidate accepted",
      pass: report.recap.acceptedMemory.length > 0,
      details: `${report.recap.acceptedMemory.length} accepted memory entry/entries.`,
    });
    const acceptedLinkedMemory = report.recap.acceptedMemory.find((entry) => entry.source_planning_marker_id === marker.id);
    const markerList = await apiGet<{ planning_markers: PlanningMarker[] }>(
      request,
      `/api/campaigns/${campaign.id}/planning-markers`,
      "planning marker list after memory accept",
    );
    const markerAfterAccept = markerList.planning_markers.find((item) => item.id === marker.id);
    const proposalAfterAccept = await apiGet<NonNullable<BuildBranchResult["proposal_set"]>>(
      request,
      `/api/proposal-sets/${branchDetail.proposal_set.id}`,
      "proposal set after memory accept",
    );
    const optionAfterAccept = proposalAfterAccept.options.find((item) => item.id === chosen.id);
    report.bridge.canonizedMarkerStatus = markerAfterAccept?.status;
    report.bridge.canonizedOptionStatus = optionAfterAccept?.status;
    addCheck(report, {
      name: "Linked accept canonizes marker and option when model supplied a valid link",
      pass:
        linkedCandidates.length === 0 ||
        Boolean(acceptedLinkedMemory && markerAfterAccept?.status === "canonized" && optionAfterAccept?.status === "canonized"),
      severity: linkedCandidates.length > 0 ? "critical" : "info",
      details:
        linkedCandidates.length > 0
          ? `acceptedLinkedMemory=${Boolean(acceptedLinkedMemory)} marker=${markerAfterAccept?.status ?? "missing"} option=${optionAfterAccept?.status ?? "missing"}`
          : "No valid linked candidate was produced by the model, so canonization bridge persistence was not exercised in this run.",
    });
    const postAcceptContext = await reviewedContext(
      request,
      campaign.id,
      {
        session_id: session.id,
        scene_id: scene.id,
        task_kind: "scene.branch_directions",
        scope_kind: "scene",
        visibility_mode: "gm_private",
        gm_instruction: scenario.postAcceptInstruction,
      },
      "post-accept branch context",
    );
    report.bridge.futurePromptAfterAcceptExcerpt = postAcceptContext.rendered_prompt.slice(-1500);
    addCheck(report, {
      name: "Future context uses accepted memory rather than raw proposal body",
      pass: !promptContains(postAcceptContext.rendered_prompt, chosen.body),
      severity: "critical",
      details: "Checked post-accept branch prompt against chosen raw proposal body.",
    });
    addCheck(report, {
      name: "Canonized marker leaves active planning context",
      pass: linkedCandidates.length === 0 || !postAcceptContext.rendered_prompt.includes(marker.marker_text),
      severity: linkedCandidates.length > 0 ? "critical" : "info",
      details:
        linkedCandidates.length > 0
          ? "Checked post-accept branch prompt for absence of canonized marker text."
          : "Marker was not canonized because the model did not produce a valid linked candidate.",
    });
    const recall = await apiPost<RecallResult>(
      request,
      `/api/campaigns/${campaign.id}/scribe/recall`,
      { query: scenario.recallQuery, include_draft: false },
      "recall accepted memory",
    );
    report.recap.recall = recall;
    addCheck(report, {
      name: "Recall cites accepted memory",
      pass: recall.hits.some((hit) => hit.source_kind === "campaign_memory_entry"),
      details: `${recall.hits.length} recall hit(s); source kinds: ${recall.hits.map((hit) => hit.source_kind).join(", ")}`,
    });

    const playerAfter = await apiGet<PlayerDisplay>(request, "/api/player-display", "player after");
    addCheck(report, {
      name: "/player payload unchanged after private Scribe journey",
      pass: JSON.stringify(playerAfter) === JSON.stringify(playerBefore),
      severity: "critical",
      details: "Compared /api/player-display before and after captures, branch generation, marker adoption, recap, memory accept, and recall.",
    });

    if (recapContext.rendered_prompt.includes("capturedAt:") && recapContext.rendered_prompt.includes("orderIndex:")) {
      report.observations.push("Recap prompt now renders capturedAt and orderIndex as first-class transcript metadata.");
    } else if (!recapContext.rendered_prompt.includes("Campaign clock")) {
      report.observations.push("Recap prompt does not render explicit capture timestamps unless they are present in the note body.");
    } else {
      report.observations.push("The recap prompt's clearest chronological signal came from campaign-clock text embedded in note bodies.");
    }
    report.observations.push("Proposal canonization remains memory-mediated: the branch becomes canon only after later played evidence produces an accepted memory entry.");

    await page.goto("/gm");
    await expect(page.getByText("Scribe", { exact: true })).toBeVisible();
    const screenshot = screenshotPath(`scribe-campaign-real-${scenario.language}-final.png`);
    await page.screenshot({ path: screenshot, fullPage: true });
    report.screenshots.push(screenshot);
  } finally {
    writeReport(report);
    test.info().annotations.push({ type: "report", description: reportPath });
    test.info().annotations.push({ type: "report-json", description: reportJsonPath });
  }

  const criticalFailures = report.checks.filter((check) => check.severity === "critical" && !check.pass);
  expect(criticalFailures, `Critical journey failures:\n${criticalFailures.map((check) => `${check.name}: ${check.details}`).join("\n")}`).toHaveLength(0);
});
