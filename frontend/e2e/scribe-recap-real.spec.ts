import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type APIRequestContext, type APIResponse, type Page } from "@playwright/test";

const enabled = process.env.MYROLL_E2E_REAL_LLM === "1";
const apiBase = process.env.MYROLL_E2E_API_BASE ?? "http://127.0.0.1:8000";
const llmBaseUrl = (process.env.MYROLL_E2E_LLM_BASE_URL ?? "http://192.168.1.117:1234/v1").replace(/\/$/, "");
const defaultLlmModel = "Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-Q8_K_P";
const llmModelEnv = process.env.MYROLL_E2E_LLM_MODEL;
const screenshotDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../artifacts/playwright");

test.skip(!enabled, "Set MYROLL_E2E_REAL_LLM=1 to run the real llama.cpp Scribe recap journey.");

type Campaign = { id: string; name: string };
type Session = { id: string; title: string };
type Scene = { id: string; title: string };
type ProviderProfile = { id: string; label: string; conformance_level: string };
type ProviderProfilesResponse = { profiles: ProviderProfile[] };
type PlayerDisplay = Record<string, unknown>;
type MemoryEntriesResponse = { entries: Array<{ id: string; title: string; body: string }> };
type TranscriptEventsResponse = { projection: Array<{ id: string; order_index: number; body: string }> };

function screenshotPath(name: string): string {
  fs.mkdirSync(screenshotDir, { recursive: true });
  return path.join(screenshotDir, name);
}

async function okJson<T>(response: APIResponse, label: string): Promise<T> {
  const text = await response.text();
  expect(response.ok(), `${label}: ${response.status()} ${text}`).toBeTruthy();
  return (text ? JSON.parse(text) : null) as T;
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

async function setupCampaign(request: APIRequestContext, runId: number): Promise<{ campaign: Campaign; session: Session; scene: Scene; playerBefore: PlayerDisplay }> {
  await request.post(`${apiBase}/api/runtime/clear`);
  await request.post(`${apiBase}/api/player-display/blackout`);

  const campaign = await okJson<Campaign>(
    await request.post(`${apiBase}/api/campaigns`, {
      data: { name: `Real LLM Recap Campaign ${runId}`, description: "Playwright real LLM recap journey." }
    }),
    "create campaign"
  );
  const session = await okJson<Session>(
    await request.post(`${apiBase}/api/campaigns/${campaign.id}/sessions`, { data: { title: `Real LLM Session ${runId}` } }),
    "create session"
  );
  const scene = await okJson<Scene>(
    await request.post(`${apiBase}/api/campaigns/${campaign.id}/scenes`, {
      data: { title: `Moon Gate Scene ${runId}`, session_id: session.id, summary: "The party studies a dawn-bound gate." }
    }),
    "create scene"
  );
  await okJson(await request.post(`${apiBase}/api/runtime/activate-scene`, { data: { scene_id: scene.id } }), "activate scene");
  const playerBefore = await okJson<PlayerDisplay>(await request.get(`${apiBase}/api/player-display`), "player before");
  return { campaign, session, scene, playerBefore };
}

async function providerConformance(request: APIRequestContext, label: string): Promise<string | null> {
  const body = await okJson<ProviderProfilesResponse>(await request.get(`${apiBase}/api/llm/provider-profiles`), "provider profiles");
  return body.profiles.find((profile) => profile.label === label)?.conformance_level ?? null;
}

async function collectPageProblems(page: Page): Promise<string[]> {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(`console error: ${message.text()}`);
  });
  page.on("pageerror", (error) => {
    problems.push(`page error: ${error.message}`);
  });
  page.on("response", (response) => {
    if (response.status() >= 500) problems.push(`${response.status()} response: ${response.url()}`);
  });
  return problems;
}

test.beforeAll(async ({ request }) => {
  expect((await request.get(`${apiBase}/health`)).ok()).toBe(true);
});

test("real LLM recap journey captures, summarizes, saves memory, recalls, and leaves /player untouched", async ({ page, request }) => {
  test.setTimeout(240_000);
  const problems = await collectPageProblems(page);
  const modelId = await discoverLlmModel(request);
  test.info().annotations.push({ type: "llm-model", description: modelId });

  const runId = Date.now();
  const { campaign, session, playerBefore } = await setupCampaign(request, runId);
  const providerLabel = `llama.cpp real recap ${runId}`;
  const captureText =
    'Aureon the goldsmith gave Mira the moon-silver coin and said, "The gate opens only at dawn." Mira promised to return the coin after the dawn ritual.';

  await page.goto("/gm");
  await expect(page.getByRole("banner").getByText("Backend linked")).toBeVisible();
  const scribe = page.locator('[data-widget-kind="scribe"]');
  await expect(scribe).toBeVisible();
  await page.screenshot({ path: screenshotPath("scribe-recap-real-before.png"), fullPage: true });

  await scribe.getByLabel("Live DM note").fill(captureText);
  const captureResponsePromise = page.waitForResponse(
    (response) => response.url().includes("/scribe/transcript-events") && response.request().method() === "POST"
  );
  await scribe.getByRole("button", { name: "Save", exact: true }).click();
  const captureResponse = await captureResponsePromise;
  expect(captureResponse.ok(), `capture POST returned ${captureResponse.status()}: ${await captureResponse.text()}`).toBeTruthy();
  await expect(scribe.getByText(captureText)).toBeVisible();

  const transcript = await okJson<TranscriptEventsResponse>(
    await request.get(`${apiBase}/api/campaigns/${campaign.id}/scribe/transcript-events?session_id=${session.id}`),
    "transcript after capture"
  );
  expect(transcript.projection).toHaveLength(1);
  expect(transcript.projection[0].order_index).toBe(0);

  await scribe.locator("summary").filter({ hasText: "Provider" }).click();
  await scribe.getByLabel("Label").fill(providerLabel);
  await scribe.getByLabel("Vendor").selectOption("custom");
  await scribe.getByLabel("Base URL").fill(llmBaseUrl);
  await scribe.getByLabel("Model").fill(modelId);
  await scribe.getByLabel("Key source").selectOption("none");
  await scribe.getByRole("button", { name: "Save provider" }).click();
  await expect.poll(() => providerConformance(request, providerLabel), { timeout: 10_000 }).toBe("unverified");
  await expect(scribe.getByRole("button", { name: "Test provider" })).toBeEnabled({ timeout: 10_000 });
  await scribe.getByRole("button", { name: "Test provider" }).click();
  await expect
    .poll(() => providerConformance(request, providerLabel), { timeout: 60_000 })
    .toMatch(/level_[12]_json_(best_effort|validated)/);

  await scribe.getByPlaceholder("Optional focus for the recap.").fill(
    [
      "Build a private recap from the live capture.",
      "Return exactly one memoryCandidateDraft for the moon-silver coin promise.",
      `The memory candidate evidence quote should be exactly: ${captureText}`,
      "Use the source id shown in CONTEXT EVIDENCE for the evidenceRefs id."
    ].join("\n")
  );
  await scribe.getByRole("button", { name: "Build Context Preview" }).click();
  await expect(scribe.getByLabel("Scribe inspection mode")).toContainText("unreviewed");
  await expect(scribe.getByLabel("Rendered prompt preview")).toContainText(captureText);
  await page.screenshot({ path: screenshotPath("scribe-recap-real-reviewed-context-before.png"), fullPage: true });

  await scribe.getByRole("button", { name: "Review Context" }).click();
  await expect(scribe.getByLabel("Scribe inspection mode")).toContainText("reviewed");
  await scribe.getByRole("button", { name: "Build Recap" }).click();
  await expect(scribe.getByText("Reviewed Recap Draft")).toBeVisible({ timeout: 120_000 });
  await expect(scribe.getByLabel("Normalized output JSON")).toContainText("memoryCandidateDrafts");
  await page.screenshot({ path: screenshotPath("scribe-recap-real-draft.png"), fullPage: true });

  await scribe.getByRole("button", { name: "Save Recap" }).click();
  await expect.poll(async () => {
    const response = await request.get(`${apiBase}/api/campaigns/${campaign.id}/scribe/session-recaps?session_id=${session.id}`);
    const body = await okJson<{ recaps: unknown[] }>(response, "session recaps");
    return body.recaps.length;
  }, { timeout: 10_000 }).toBeGreaterThan(0);

  await expect(scribe.getByRole("button", { name: "Accept into Memory" }).first()).toBeVisible({ timeout: 15_000 });
  await scribe.getByRole("button", { name: "Accept into Memory" }).first().click();
  await expect.poll(async () => {
    const response = await request.get(`${apiBase}/api/campaigns/${campaign.id}/scribe/memory-entries?session_id=${session.id}`);
    const body = await okJson<MemoryEntriesResponse>(response, "memory entries");
    return body.entries.length;
  }, { timeout: 10_000 }).toBe(1);

  await scribe.getByLabel("Scribe recall query").fill("moon-silver coin dawn");
  await scribe.getByRole("button", { name: "Recall", exact: true }).click();
  await expect(scribe.getByText("campaign_memory_entry")).toBeVisible({ timeout: 10_000 });
  await page.screenshot({ path: screenshotPath("scribe-recap-real-memory-recall.png"), fullPage: true });

  const entries = await okJson<MemoryEntriesResponse>(
    await request.get(`${apiBase}/api/campaigns/${campaign.id}/scribe/memory-entries?session_id=${session.id}`),
    "memory entries final"
  );
  expect(entries.entries[0].body).toContain("moon-silver coin");
  const playerAfter = await okJson<PlayerDisplay>(await request.get(`${apiBase}/api/player-display`), "player after");
  expect(playerAfter).toEqual(playerBefore);
  expect(problems).toEqual([]);
});
