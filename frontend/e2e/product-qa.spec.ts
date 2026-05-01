import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import zlib from "node:zlib";

import { expect, test, type Page } from "@playwright/test";

const apiBase = process.env.MYROLL_E2E_API_BASE ?? "http://127.0.0.1:8000";
const screenshotDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../artifacts/playwright");

function screenshotPath(name: string): string {
  fs.mkdirSync(screenshotDir, { recursive: true });
  return path.join(screenshotDir, name);
}

const crcTable = new Uint32Array(256).map((_, index) => {
  let value = index;
  for (let bit = 0; bit < 8; bit += 1) {
    value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
  }
  return value >>> 0;
});

function crc32(buffer: Buffer): number {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function pngChunk(type: string, data: Buffer): Buffer {
  const typeBuffer = Buffer.from(type, "ascii");
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length, 0);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(Buffer.concat([typeBuffer, data])), 0);
  return Buffer.concat([length, typeBuffer, data, crc]);
}

function writePngFixture(filePath: string, colorShift = 0): void {
  const width = 360;
  const height = 220;
  const raw = Buffer.alloc((width * 3 + 1) * height);
  for (let y = 0; y < height; y += 1) {
    const row = y * (width * 3 + 1);
    raw[row] = 0;
    for (let x = 0; x < width; x += 1) {
      const offset = row + 1 + x * 3;
      raw[offset] = 25 + ((colorShift + Math.round((x / width) * 190)) % 210);
      raw[offset + 1] = 60 + Math.round((y / height) * 140);
      raw[offset + 2] = 150 + (colorShift % 80);
    }
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = 2;
  ihdr[10] = 0;
  ihdr[11] = 0;
  ihdr[12] = 0;
  fs.writeFileSync(
    filePath,
    Buffer.concat([
      Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
      pngChunk("IHDR", ihdr),
      pngChunk("IDAT", zlib.deflateSync(raw)),
      pngChunk("IEND", Buffer.alloc(0))
    ])
  );
}

function collectPageProblems(page: Page, label: string, problems: string[]): void {
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(`${label} console error: ${message.text()}`);
  });
  page.on("pageerror", (error) => {
    problems.push(`${label} page error: ${error.message}`);
  });
  page.on("response", (response) => {
    if (response.status() >= 500) problems.push(`${label} ${response.status()} response: ${response.url()}`);
  });
}

test.beforeAll(async ({ request }) => {
  const response = await request.get(`${apiBase}/health`);
  expect(response.ok()).toBe(true);
});

test("product QA full user journey across GM, assets, maps, and player display", async ({ page, request }) => {
  test.setTimeout(75_000);
  const problems: string[] = [];
  const privatePlayerRequests: string[] = [];
  collectPageProblems(page, "gm", problems);

  await request.post(`${apiBase}/api/workspace/widgets/reset`);
  await request.post(`${apiBase}/api/runtime/clear`);
  await request.post(`${apiBase}/api/player-display/blackout`);

  await page.goto("/gm/floating");
  await expect(page.getByRole("banner").getByText("Backend linked")).toBeVisible();

  const runId = Date.now();
  const campaignName = `QA Campaign ${runId}`;
  const sessionTitle = `QA Session ${runId}`;
  const sceneTitle = `QA Scene ${runId}`;
  const handoutName = `QA Handout ${runId}`;
  const mapName = `QA Map ${runId}`;

  await page.getByPlaceholder("New campaign").fill(campaignName);
  await page.getByPlaceholder("New campaign").press("Enter");
  await expect(page.getByText(campaignName)).toBeVisible();
  await page.getByPlaceholder("New session").fill(sessionTitle);
  await page.getByPlaceholder("New session").press("Enter");
  await expect(page.locator('[data-widget-kind="sessions"]')).toContainText(sessionTitle);
  await page.getByPlaceholder("New scene").fill(sceneTitle);
  await page.getByPlaceholder("New scene").press("Enter");
  await expect(page.locator('[data-widget-kind="scenes"]')).toContainText(sceneTitle);
  await page.getByRole("button", { name: "Activate scene", exact: true }).click();
  await expect(page.locator('[data-widget-kind="runtime"]')).toContainText(sceneTitle);

  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Open / Reconnect" }).click();
  const player = await popupPromise;
  collectPageProblems(player, "player", problems);
  player.on("request", (requestInfo) => {
    const url = requestInfo.url();
    if (url.includes("/api/") && !url.includes("/api/player-display") && !url.endsWith("/health")) {
      privatePlayerRequests.push(url);
    }
  });
  await player.waitForLoadState("domcontentloaded");
  await expect(page.locator('[data-widget-kind="player_display"]').getByText("connected", { exact: true })).toBeVisible({
    timeout: 6_000
  });

  await page.getByRole("button", { name: "Show active scene" }).click();
  await expect(player.locator(".player-scene-title")).toContainText(sceneTitle);

  const widgetsResponse = await request.get(`${apiBase}/api/workspace/widgets`);
  expect(widgetsResponse.ok()).toBe(true);
  const widgetsBody = await widgetsResponse.json();
  const assetWidget = widgetsBody.widgets.find((widget: { kind: string }) => widget.kind === "asset_library");
  const mapWidget = widgetsBody.widgets.find((widget: { kind: string }) => widget.kind === "map_display");
  const playerWidget = widgetsBody.widgets.find((widget: { kind: string }) => widget.kind === "player_display");
  expect(assetWidget).toBeTruthy();
  expect(mapWidget).toBeTruthy();
  expect(playerWidget).toBeTruthy();
  await request.patch(`${apiBase}/api/workspace/widgets/${assetWidget.id}`, {
    data: { x: 24, y: 72, width: 430, height: 560, z_index: 130 }
  });
  await request.patch(`${apiBase}/api/workspace/widgets/${mapWidget.id}`, {
    data: { x: 480, y: 72, width: 680, height: 700, z_index: 140 }
  });
  await request.patch(`${apiBase}/api/workspace/widgets/${playerWidget.id}`, {
    data: { x: 1184, y: 72, width: 380, height: 330, z_index: 150 }
  });
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.locator('[data-widget-kind="runtime"]')).toContainText(sceneTitle);

  const handoutFixture = screenshotPath("qa-handout-fixture.png");
  const mapFixture = screenshotPath("qa-map-fixture.png");
  writePngFixture(handoutFixture, 15);
  writePngFixture(mapFixture, 70);

  const assetPanel = page.locator('[data-widget-kind="asset_library"]');
  await expect(assetPanel).toBeVisible();
  await assetPanel.getByLabel("Asset kind").selectOption("handout_image");
  await assetPanel.getByLabel("Asset visibility").selectOption("public_displayable");
  await assetPanel.getByLabel("Asset name").fill(handoutName);
  await assetPanel.getByLabel("Asset tags").fill("qa, handout");
  await assetPanel.getByLabel("Asset file").setInputFiles(handoutFixture);
  await assetPanel.getByRole("button", { name: /Upload/ }).click();
  await expect(assetPanel.getByText(handoutName)).toBeVisible();

  await assetPanel.getByPlaceholder("Public caption").fill("QA projected handout");
  await assetPanel.getByRole("button", { name: /Send to player/ }).click();
  await expect(player.locator(".player-image-media")).toBeVisible();
  await expect(player.locator(".player-caption")).toContainText("QA projected handout");
  await player.screenshot({ path: screenshotPath("qa-player-image.png") });

  await assetPanel.getByLabel("Asset kind").selectOption("map_image");
  await assetPanel.getByLabel("Asset visibility").selectOption("public_displayable");
  await assetPanel.getByLabel("Asset name").fill(mapName);
  await assetPanel.getByLabel("Asset tags").fill("qa, map");
  await assetPanel.getByLabel("Asset file").setInputFiles(mapFixture);
  await assetPanel.getByRole("button", { name: /Upload/ }).click();
  await expect(assetPanel.getByText(mapName)).toBeVisible();

  const mapPanel = page.locator('[data-widget-kind="map_display"]');
  await expect(mapPanel.getByLabel("Map image asset")).toContainText(mapName);
  await mapPanel.getByRole("button", { name: "Create map" }).click();
  await expect(mapPanel.getByLabel("Campaign maps")).toContainText(mapName);
  await mapPanel.getByRole("button", { name: "Assign active" }).click();
  await expect(mapPanel.getByLabel("Scene maps")).toContainText(`Active · ${mapName}`);
  await expect(mapPanel.locator(".map-renderer img")).toBeVisible();

  const gmGrid = mapPanel.getByLabel("GM grid");
  if (!(await gmGrid.isChecked())) await gmGrid.check();
  await mapPanel.getByLabel("Grid size").fill("44");
  await mapPanel.getByLabel("Grid offset X").fill("5");
  await mapPanel.getByLabel("Grid offset Y").fill("7");
  await mapPanel.getByLabel("Grid color").fill("#33ffcc");
  await mapPanel.getByLabel("Grid opacity").fill("0.50");
  await mapPanel.getByRole("button", { name: "Save grid" }).click();
  await expect(mapPanel.locator(".map-grid line")).not.toHaveCount(0);

  await mapPanel.getByRole("button", { name: /Send map/ }).click();
  await expect(player.locator(".player-map .map-renderer img")).toBeVisible();
  await expect(player.locator(".player-map .map-grid line")).not.toHaveCount(0);
  await page.screenshot({ path: screenshotPath("qa-gm-map-ready.png") });
  await player.screenshot({ path: screenshotPath("qa-player-map.png") });

  await mapPanel.getByRole("button", { name: /Enable hidden fog/ }).click();
  await expect(mapPanel.getByText(/Revision 1/)).toBeVisible();
  await mapPanel.getByRole("button", { name: /Send map/ }).click();
  await expect(player.locator(".player-map canvas")).toBeVisible();

  const fogLayer = mapPanel.locator(".fog-interaction");
  await expect(fogLayer).toBeVisible();

  await fogLayer.hover({ position: { x: 120, y: 90 } });
  await page.mouse.down();
  await fogLayer.hover({ position: { x: 360, y: 250 } });
  await page.mouse.up();
  await expect(mapPanel.getByText(/Revision 2/)).toBeVisible();
  await page.screenshot({ path: screenshotPath("gm-fog-edit-overlay.png") });
  await expect(player.locator(".player-map canvas")).toBeVisible();
  await player.screenshot({ path: screenshotPath("player-fog-reveal-rect.png") });

  await mapPanel.getByLabel("Fog mode").selectOption("hide");
  await fogLayer.hover({ position: { x: 180, y: 130 } });
  await page.mouse.down();
  await fogLayer.hover({ position: { x: 270, y: 200 } });
  await page.mouse.up();
  await expect(mapPanel.getByText(/Revision 3/)).toBeVisible();
  await player.screenshot({ path: screenshotPath("player-fog-hide-rect.png") });

  await mapPanel.getByLabel("Fog tool").selectOption("brush");
  await mapPanel.getByLabel("Fog mode").selectOption("reveal");
  await mapPanel.getByLabel("Brush radius").fill("18");
  await fogLayer.hover({ position: { x: 420, y: 120 } });
  await page.mouse.down();
  await fogLayer.hover({ position: { x: 520, y: 220 } });
  await page.mouse.up();
  await expect(mapPanel.getByText(/Revision 4/)).toBeVisible();
  await player.screenshot({ path: screenshotPath("player-fog-brush.png") });

  await player.reload({ waitUntil: "domcontentloaded" });
  await expect(player.locator(".player-map canvas")).toBeVisible();

  await player.route("**/api/player-display/fog/**/mask**", (route) => route.abort("failed"));
  await player.reload({ waitUntil: "domcontentloaded" });
  await expect(player.getByText("Map unavailable")).toBeVisible();
  await player.screenshot({ path: screenshotPath("player-fog-mask-unavailable.png") });
  await player.unroute("**/api/player-display/fog/**/mask**");

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.locator('[data-widget-kind="runtime"]')).toContainText(sceneTitle);
  await expect(page.locator('[data-widget-kind="map_display"]')).toContainText(mapName);
  await page.screenshot({ path: screenshotPath("qa-gm-after-refresh.png") });

  await page.getByRole("button", { name: "Blackout" }).click();
  await expect(player.locator(".player-blackout")).toBeVisible();
  await expect(player.getByText(sceneTitle)).toBeHidden();

  expect(privatePlayerRequests).toEqual([]);
  expect(problems.filter((problem) => !problem.includes("player console error: Failed to load resource: net::ERR_FAILED"))).toEqual([]);
});
