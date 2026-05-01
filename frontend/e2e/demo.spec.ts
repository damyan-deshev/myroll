import { spawn, execFileSync, type ChildProcessWithoutNullStreams } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const apiBase = process.env.MYROLL_E2E_API_BASE ?? "http://127.0.0.1:8000";
const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const screenshotDir = path.resolve(projectRoot, "artifacts/playwright");
const demoDataDir = process.env.MYROLL_E2E_DATA_DIR ?? path.join(projectRoot, "data/demo");

function screenshotPath(name: string): string {
  fs.mkdirSync(screenshotDir, { recursive: true });
  return path.join(screenshotDir, name);
}

async function waitForHealth(request: APIRequestContext, baseUrl: string, timeoutMs = 45_000): Promise<void> {
  const started = Date.now();
  let lastError: unknown = null;
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await request.get(`${baseUrl}/health`);
      if (response.ok()) return;
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Timed out waiting for ${baseUrl}/health: ${String(lastError)}`);
}

async function waitForFrontend(page: Page, url: string, timeoutMs = 45_000): Promise<void> {
  const started = Date.now();
  let lastError: unknown = null;
  while (Date.now() - started < timeoutMs) {
    try {
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 5_000 });
      return;
    } catch (error) {
      lastError = error;
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
  throw new Error(`Timed out waiting for frontend ${url}: ${String(lastError)}`);
}

test.beforeAll(async ({ request }) => {
  await waitForHealth(request, apiBase);
});

test("English demo profile exports, restores, and preserves explicit public publish", async ({ page, context, request }) => {
  test.setTimeout(150_000);
  const problems: string[] = [];
  const privatePlayerRequests: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(`gm console error: ${message.text()}`);
  });
  page.on("pageerror", (error) => problems.push(`gm page error: ${error.message}`));

  const campaignsResponse = await request.get(`${apiBase}/api/campaigns`);
  expect(campaignsResponse.ok()).toBe(true);
  const campaigns = (await campaignsResponse.json()) as Array<{ id: string; name: string }>;
  const campaign = campaigns.find((candidate) => candidate.name === "Chronicle of the Lantern Vale");
  expect(campaign).toBeTruthy();

  const scenesResponse = await request.get(`${apiBase}/api/campaigns/${campaign!.id}/scenes`);
  const scenes = (await scenesResponse.json()) as Array<{ id: string; title: string }>;
  const scene = scenes.find((candidate) => candidate.title === "Workshop of Stolen Time");
  expect(scene).toBeTruthy();

  const widgetsResponse = await request.get(`${apiBase}/api/workspace/widgets`);
  const widgets = ((await widgetsResponse.json()) as { widgets: Array<{ id: string; kind: string }> }).widgets;
  const storageWidget = widgets.find((widget) => widget.kind === "storage_demo");
  const sceneContextWidget = widgets.find((widget) => widget.kind === "scene_context");
  const playerWidget = widgets.find((widget) => widget.kind === "player_display");
  expect(storageWidget).toBeTruthy();
  expect(sceneContextWidget).toBeTruthy();
  expect(playerWidget).toBeTruthy();
  await request.patch(`${apiBase}/api/workspace/widgets/${sceneContextWidget!.id}`, {
    data: { x: 20, y: 90, width: 480, height: 680, z_index: 70 }
  });
  await request.patch(`${apiBase}/api/workspace/widgets/${storageWidget!.id}`, {
    data: { x: 520, y: 90, width: 430, height: 300, z_index: 71 }
  });
  await request.patch(`${apiBase}/api/workspace/widgets/${playerWidget!.id}`, {
    data: { x: 970, y: 90, width: 390, height: 300, z_index: 72 }
  });

  await request.post(`${apiBase}/api/player-display/blackout`);
  const beforeActivation = await (await request.get(`${apiBase}/api/player-display`)).json();
  await request.post(`${apiBase}/api/runtime/activate-scene`, { data: { scene_id: scene!.id } });
  const afterActivation = await (await request.get(`${apiBase}/api/player-display`)).json();
  expect(afterActivation.revision).toBe(beforeActivation.revision);
  expect(afterActivation.mode).toBe("blackout");

  await page.goto("/gm");
  await expect(page.getByRole("button", { name: "Chronicle of the Lantern Vale" })).toBeVisible();
  await expect(page.locator('[data-widget-kind="storage_demo"]')).toContainText("demo");
  await expect(page.locator('[data-widget-kind="storage_demo"]')).toContainText("inactive");
  await page.screenshot({ path: screenshotPath("gm-demo-lantern-vale-overview.png") });
  await page.screenshot({ path: screenshotPath("gm-storage-demo-status.png") });

  const player = await context.newPage();
  player.on("request", (requestInfo) => {
    const url = requestInfo.url();
    if (url.includes("/api/") && !url.includes("/api/player-display") && !url.endsWith("/health")) {
      privatePlayerRequests.push(url);
    }
  });
  await player.goto("/player");
  await expect(player.locator(".player-blackout")).toBeVisible();

  await request.patch(`${apiBase}/api/scenes/${scene!.id}/context`, {
    data: {
      staged_display_mode: "active_map",
      staged_public_snippet_id: null
    }
  });
  const publishMap = await request.post(`${apiBase}/api/scenes/${scene!.id}/publish-staged-display`);
  expect(publishMap.ok()).toBe(true);
  await player.reload({ waitUntil: "domcontentloaded" });
  await expect(player.locator(".player-map")).toBeVisible({ timeout: 6_000 });
  await player.screenshot({ path: screenshotPath("player-demo-staged-map.png") });

  const sceneContext = await (await request.get(`${apiBase}/api/scenes/${scene!.id}/context`)).json();
  const linkedSnippet = sceneContext.public_snippets[0];
  expect(linkedSnippet).toBeTruthy();
  await request.patch(`${apiBase}/api/scenes/${scene!.id}/context`, {
    data: {
      staged_display_mode: "public_snippet",
      staged_public_snippet_id: linkedSnippet.public_snippet_id
    }
  });
  const publishSnippet = await request.post(`${apiBase}/api/scenes/${scene!.id}/publish-staged-display`);
  expect(publishSnippet.ok()).toBe(true);
  await player.reload({ waitUntil: "domcontentloaded" });
  await expect(player.locator(".player-text")).toContainText("The Lantern Children", { timeout: 6_000 });
  await expect(player.locator(".player-text")).not.toContainText("PRIVATE SECRET");
  await player.screenshot({ path: screenshotPath("player-demo-public-snippet.png") });

  const exportResponse = page.waitForResponse(
    (response) => response.url().endsWith("/api/storage/export") && response.request().method() === "POST"
  );
  await page
    .locator('[data-widget-kind="storage_demo"]')
    .getByRole("button", { name: "Export" })
    .evaluate((button) => (button as HTMLButtonElement).click());
  expect((await exportResponse).ok()).toBe(true);
  await page.screenshot({ path: screenshotPath("gm-demo-export-created.png") });

  const status = await (await request.get(`${apiBase}/api/storage/status`)).json();
  expect(status.latest_export.archive_name).toMatch(/\.export\.tar\.gz$/);
  const archivePath = path.join(demoDataDir, "exports", status.latest_export.archive_name);
  expect(fs.existsSync(archivePath)).toBe(true);

  const restoredDir = fs.mkdtempSync(path.join(os.tmpdir(), "myroll-restored-demo-"));
  execFileSync(path.join(projectRoot, "scripts/restore_export.sh"), [archivePath, restoredDir], {
    cwd: projectRoot,
    env: { ...process.env, MYROLL_VENV_DIR: path.join(projectRoot, ".venv") },
    stdio: "pipe"
  });
  expect(fs.existsSync(path.join(restoredDir, "myroll.dev.sqlite3"))).toBe(true);
  expect(fs.existsSync(path.join(restoredDir, "assets"))).toBe(true);

  const restoredApiBase = "http://127.0.0.1:18001";
  const restoredUiBase = "http://127.0.0.1:15174";
  const restoredBackend = spawn(path.join(projectRoot, "scripts/start_backend.sh"), {
    cwd: projectRoot,
    env: {
      ...process.env,
      MYROLL_VENV_DIR: path.join(projectRoot, ".venv"),
      MYROLL_DATA_DIR: restoredDir,
      MYROLL_DB_PATH: path.join(restoredDir, "myroll.dev.sqlite3"),
      MYROLL_ASSET_DIR: path.join(restoredDir, "assets"),
      MYROLL_BACKUP_DIR: path.join(restoredDir, "backups"),
      MYROLL_EXPORT_DIR: path.join(restoredDir, "exports"),
      MYROLL_SEED_MODE: "none",
      MYROLL_HOST: "127.0.0.1",
      MYROLL_PORT: "18001"
    }
  });
  const restoredVite = spawn("npm", ["--prefix", "frontend", "run", "dev", "--", "--host", "127.0.0.1", "--port", "15174"], {
    cwd: projectRoot,
    env: {
      ...process.env,
      VITE_API_BASE_URL: restoredApiBase
    }
  });
  const children: ChildProcessWithoutNullStreams[] = [restoredBackend, restoredVite];
  try {
    await waitForHealth(request, restoredApiBase, 60_000);
    const restoredCampaigns = (await (await request.get(`${restoredApiBase}/api/campaigns`)).json()) as Array<{ name: string }>;
    expect(restoredCampaigns.some((item) => item.name === "Chronicle of the Lantern Vale")).toBe(true);
    const restoredDisplay = await (await request.get(`${restoredApiBase}/api/player-display`)).json();
    expect(restoredDisplay.mode).toBe("text");
    const restoredPage = await context.newPage();
    await waitForFrontend(restoredPage, `${restoredUiBase}/gm`, 60_000);
    await expect(restoredPage.locator(".brand")).toContainText("Myroll", { timeout: 10_000 });
    await restoredPage.screenshot({ path: screenshotPath("gm-demo-restored-overview.png") });
    await restoredPage.close();
  } finally {
    for (const child of children) {
      if (!child.killed) child.kill("SIGTERM");
    }
  }

  await request.post(`${apiBase}/api/player-display/blackout`);
  await expect(player.locator(".player-blackout")).toBeVisible({ timeout: 6_000 });
  await player.close();

  expect(privatePlayerRequests).toEqual([]);
  expect(problems).toEqual([]);
});
