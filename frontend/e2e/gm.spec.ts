import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import zlib from "node:zlib";

import { expect, test } from "@playwright/test";

const apiBase = process.env.MYROLL_E2E_API_BASE ?? "http://127.0.0.1:8000";
const screenshotDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../artifacts/playwright");
const transportNamespace = "myroll.playerDisplay";

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

function writePngFixture(filePath: string): void {
  const width = 320;
  const height = 180;
  const raw = Buffer.alloc((width * 3 + 1) * height);
  for (let y = 0; y < height; y += 1) {
    const row = y * (width * 3 + 1);
    raw[row] = 0;
    for (let x = 0; x < width; x += 1) {
      const offset = row + 1 + x * 3;
      raw[offset] = 30 + Math.round((x / width) * 190);
      raw[offset + 1] = 70 + Math.round((y / height) * 130);
      raw[offset + 2] = 170;
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

test.beforeAll(async ({ request }) => {
  const response = await request.get(`${apiBase}/health`);
  expect(response.ok()).toBe(true);
});

test("GM cockpit visual flow creates and activates state, then persists widget layout", async ({ page, request }) => {
  await request.post(`${apiBase}/api/workspace/widgets/reset`);
  await request.post(`${apiBase}/api/runtime/clear`);

  await page.goto("/gm/floating");
  await expect(page.locator(".brand")).toHaveText("Myroll");
  await expect(page.getByText("Backend linked")).toBeVisible();
  await expect(page.locator('[data-widget-kind="backend_status"]')).toBeVisible();

  await page.screenshot({ path: screenshotPath("gm-cockpit-initial.png") });

  const runId = Date.now();
  const campaignName = `Playwright Campaign ${runId}`;
  const sessionTitle = `Playwright Session ${runId}`;
  const sceneTitle = `Playwright Scene ${runId}`;

  await page.getByPlaceholder("New campaign").fill(campaignName);
  await page.getByPlaceholder("New campaign").press("Enter");
  await expect(page.getByText(campaignName)).toBeVisible();

  await page.getByPlaceholder("New session").fill(sessionTitle);
  await page.getByPlaceholder("New session").press("Enter");
  await expect(page.locator('[data-widget-kind="sessions"]')).toContainText(sessionTitle);

  await page.getByPlaceholder("New scene").fill(sceneTitle);
  await page.getByPlaceholder("New scene").press("Enter");
  await expect(page.locator('[data-widget-kind="scenes"]')).toContainText(sceneTitle);

  await expect(page.getByRole("button", { name: "Activate scene", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Activate scene", exact: true }).click();
  await expect(page.locator('[data-widget-kind="runtime"]')).toContainText(sceneTitle);

  await page.screenshot({ path: screenshotPath("gm-cockpit-created-and-active.png") });

  const statusWidget = page.locator('[data-widget-kind="backend_status"]');
  const titlebar = statusWidget.locator(".widget-titlebar");
  const before = await statusWidget.boundingBox();
  const handle = await titlebar.boundingBox();
  expect(before).not.toBeNull();
  expect(handle).not.toBeNull();

  await page.mouse.move(handle!.x + handle!.width / 2, handle!.y + handle!.height / 2);
  await page.mouse.down();
  await page.mouse.move(handle!.x + handle!.width / 2 + 56, handle!.y + handle!.height / 2, { steps: 10 });
  await page.mouse.up();
  await expect(statusWidget.locator(".save-indicator")).toBeHidden();

  const widgetsResponse = await request.get(`${apiBase}/api/workspace/widgets`);
  expect(widgetsResponse.ok()).toBe(true);
  const widgetsBody = await widgetsResponse.json();
  const persisted = widgetsBody.widgets.find((widget: { kind: string }) => widget.kind === "backend_status");
  expect(persisted.x).toBeGreaterThan(24);
  expect(persisted.y).toBe(72);

  await page.reload({ waitUntil: "domcontentloaded" });
  const reloadedStatusWidget = page.locator('[data-widget-kind="backend_status"]').first();
  await expect(reloadedStatusWidget).toBeVisible();
  await expect(page.locator('[data-widget-kind="runtime"]')).toContainText(sceneTitle);
  await expect(page.locator('[data-widget-kind="sessions"]')).toContainText(sessionTitle);
  await expect(page.locator('[data-widget-kind="scenes"]')).toContainText(sceneTitle);
  const after = await reloadedStatusWidget.boundingBox();
  expect(after).not.toBeNull();
  expect(after!.x).toBeGreaterThan(before!.x + 40);

  await page.screenshot({ path: screenshotPath("gm-cockpit-layout-persisted.png") });
});

test("GM shell renders a visual degraded state when backend calls fail", async ({ page }) => {
  await page.route("**/health", (route) => route.abort("failed"));
  await page.route("**/api/**", (route) => route.abort("failed"));

  await page.goto("/gm/floating");
  await expect(page.getByText("Workspace layout unavailable")).toBeVisible();
  await expect(page.getByRole("banner").getByText("Backend unavailable")).toBeVisible();
  await expect(page.locator('[data-widget-kind="backend_status"]')).toBeVisible();

  await page.screenshot({ path: screenshotPath("gm-degraded-backend-unavailable.png") });
});

test("GM docked surfaces render focused workbenches", async ({ page }) => {
  await page.goto("/gm");
  await expect(page.getByRole("banner").getByText("Backend linked")).toBeVisible();
  await expect(page.locator(".surface-nav a.active")).toContainText("Overview");
  await expect(page.locator('[data-widget-kind="campaigns"]')).toBeVisible();
  await expect(page.locator('[data-widget-kind="scene_context"]')).toBeVisible();
  await expect(page.locator('[data-widget-kind="player_display"]')).toBeVisible();
  await page.screenshot({ path: screenshotPath("gm-overview-surface.png") });

  await page.goto("/gm/map");
  await expect(page.locator(".surface-nav a.active")).toContainText("Map");
  await expect(page.locator('[data-widget-kind="map_display"]')).toBeVisible();
  await expect(page.locator('[data-widget-kind="player_display"]')).toBeVisible();
  await page.screenshot({ path: screenshotPath("gm-map-surface.png") });

  await page.goto("/gm/library");
  await expect(page.locator('[data-widget-kind="asset_library"]')).toBeVisible();
  await expect(page.locator('[data-widget-kind="notes"]')).toBeVisible();

  await page.goto("/gm/actors");
  await expect(page.locator('[data-widget-kind="party_tracker"]')).toBeVisible();

  await page.goto("/gm/combat");
  await expect(page.locator('[data-widget-kind="combat_tracker"]')).toBeVisible();

  await page.goto("/gm/scene");
  await expect(page.locator('[data-widget-kind="scene_context"]')).toBeVisible();
  await expect(page.locator('[data-widget-kind="runtime"]')).toBeVisible();
});

test("local player display visual flow", async ({ page, request }) => {
  await request.post(`${apiBase}/api/workspace/widgets/reset`);
  await request.post(`${apiBase}/api/runtime/clear`);
  await request.post(`${apiBase}/api/player-display/blackout`);

  await page.goto("/gm/floating");
  await expect(page.locator('[data-widget-kind="player_display"]')).toBeVisible();

  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Open / Reconnect" }).click();
  const player = await popupPromise;
  await player.waitForLoadState("domcontentloaded");

  await expect(page.locator('[data-widget-kind="player_display"]').getByText("connected", { exact: true })).toBeVisible({
    timeout: 6_000
  });
  await page.screenshot({ path: screenshotPath("gm-player-display-connected.png") });

  await page.getByRole("button", { name: "Intermission" }).click();
  await expect(player.locator(".player-intermission")).toContainText("Intermission");
  await player.screenshot({ path: screenshotPath("player-intermission.png") });

  const runId = Date.now();
  const campaignName = `Player Campaign ${runId}`;
  const sessionTitle = `Player Session ${runId}`;
  const sceneTitle = `Player Scene ${runId}`;

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

  await page.getByRole("button", { name: "Show active scene" }).click();
  await expect(player.locator(".player-scene-title")).toContainText(sceneTitle);
  await player.screenshot({ path: screenshotPath("player-scene-title.png") });

  await player.reload({ waitUntil: "domcontentloaded" });
  await expect(player.locator(".player-scene-title")).toContainText(sceneTitle);

  await page.getByRole("button", { name: "Identify" }).click();
  await expect(player.locator(".identify-overlay")).toBeVisible();
  await player.screenshot({ path: screenshotPath("player-identify-overlay.png") });
  await expect(player.locator(".identify-overlay")).toBeHidden({ timeout: 5_000 });

  await player.route("**/api/player-display", (route) => route.abort("failed"));
  await player.evaluate((namespace) => {
    window.postMessage(
      {
        namespace,
        type: "display-state-changed",
        displayWindowId: "playwright",
        revision: 999,
        identify_revision: 0,
        sentAt: new Date().toISOString()
      },
      window.location.origin
    );
  }, transportNamespace);
  await expect(player.getByText("Reconnecting")).toBeVisible();
  await expect(player.locator(".player-scene-title")).toContainText(sceneTitle);
  await player.screenshot({ path: screenshotPath("player-reconnecting-last-known-state.png") });

  await player.unroute("**/api/player-display");
  await page.getByRole("button", { name: "Blackout" }).click();
  await expect(player.locator(".player-blackout")).toBeVisible();
  await expect(player.getByText(sceneTitle)).toBeHidden();
  await player.screenshot({ path: screenshotPath("player-blackout.png") });

  await player.route("**/api/player-display", (route) => route.abort("failed"));
  await player.evaluate((namespace) => {
    window.postMessage(
      {
        namespace,
        type: "display-state-changed",
        displayWindowId: "playwright",
        revision: 1000,
        identify_revision: 0,
        sentAt: new Date().toISOString()
      },
      window.location.origin
    );
  }, transportNamespace);
  await expect(player.locator(".player-blackout")).toBeVisible();
  await expect(player.getByText("Reconnecting")).toBeHidden();
});

test("asset image display visual flow", async ({ page, request }) => {
  await request.post(`${apiBase}/api/workspace/widgets/reset`);
  await request.post(`${apiBase}/api/runtime/clear`);
  await request.post(`${apiBase}/api/player-display/blackout`);

  const widgetsResponse = await request.get(`${apiBase}/api/workspace/widgets`);
  expect(widgetsResponse.ok()).toBe(true);
  const widgetsBody = await widgetsResponse.json();
  const assetWidget = widgetsBody.widgets.find((widget: { kind: string }) => widget.kind === "asset_library");
  expect(assetWidget).toBeTruthy();
  await request.patch(`${apiBase}/api/workspace/widgets/${assetWidget.id}`, {
    data: { x: 24, y: 72, width: 460, height: 500, z_index: 120 }
  });

  const fixturePath = screenshotPath("asset-fixture.png");
  writePngFixture(fixturePath);
  const assetName = `Signal Tower ${Date.now()}`;

  await page.goto("/gm/floating");
  const assetPanel = page.locator('[data-widget-kind="asset_library"]');
  await expect(assetPanel).toBeVisible();
  await assetPanel.getByLabel("Asset visibility").selectOption("public_displayable");
  await assetPanel.getByLabel("Asset name").fill(assetName);
  await assetPanel.getByLabel("Asset tags").fill("signal, handout");
  await assetPanel.getByLabel("Asset file").setInputFiles(fixturePath);
  await assetPanel.getByRole("button", { name: /Upload/ }).click();
  await expect(assetPanel.getByText(assetName)).toBeVisible();

  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Open / Reconnect" }).click();
  const player = await popupPromise;
  await player.waitForLoadState("domcontentloaded");
  await expect(page.locator('[data-widget-kind="player_display"]').getByText("connected", { exact: true })).toBeVisible({
    timeout: 6_000
  });

  await assetPanel.getByPlaceholder("Public caption").fill("Projected handout");
  await assetPanel.getByRole("button", { name: /Send to player/ }).click();
  await expect(player.locator(".player-image-media")).toBeVisible();
  await expect(player.locator(".player-caption")).toContainText("Projected handout");
  await player.screenshot({ path: screenshotPath("player-image-fit.png") });

  await player.reload({ waitUntil: "domcontentloaded" });
  await expect(player.locator(".player-image-media")).toBeVisible();

  const failingPlayer = await page.context().newPage();
  await failingPlayer.route("**/api/player-display/assets/**/blob", (route) => route.abort("failed"));
  await failingPlayer.goto("/player");
  await expect(failingPlayer.getByText("Image unavailable")).toBeVisible();
  await failingPlayer.screenshot({ path: screenshotPath("player-image-unavailable.png") });
  await failingPlayer.close();

  await page.getByRole("button", { name: "Blackout" }).click();
  await expect(player.locator(".player-blackout")).toBeVisible();
  await expect(player.locator(".player-image-media")).toBeHidden();
  await player.screenshot({ path: screenshotPath("player-image-blackout.png") });
});

test("map display visual flow", async ({ page, request }) => {
  await request.post(`${apiBase}/api/workspace/widgets/reset`);
  await request.post(`${apiBase}/api/runtime/clear`);
  await request.post(`${apiBase}/api/player-display/blackout`);

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
    data: { x: 24, y: 72, width: 430, height: 500, z_index: 130 }
  });
  await request.patch(`${apiBase}/api/workspace/widgets/${playerWidget.id}`, {
    data: { x: 1184, y: 72, width: 380, height: 330, z_index: 150 }
  });

  const fixturePath = screenshotPath("map-fixture.png");
  const portraitFixturePath = screenshotPath("portrait-fixture.png");
  writePngFixture(fixturePath);
  writePngFixture(portraitFixturePath);

  await page.goto("/gm/floating");
  const runId = Date.now();
  const campaignName = `Map Campaign ${runId}`;
  const sessionTitle = `Map Session ${runId}`;
  const sceneTitle = `Map Scene ${runId}`;
  const mapName = `Harbor Battle Map ${runId}`;
  const portraitName = `Portrait Token ${runId}`;

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

  await request.patch(`${apiBase}/api/workspace/widgets/${mapWidget.id}`, {
    data: { x: 480, y: 72, width: 680, height: 650, z_index: 140 }
  });
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.locator('[data-widget-kind="runtime"]')).toContainText(sceneTitle);

  const assetPanel = page.locator('[data-widget-kind="asset_library"]');
  await expect(assetPanel).toBeVisible();
  await assetPanel.getByLabel("Asset kind").selectOption("map_image");
  await assetPanel.getByLabel("Asset visibility").selectOption("public_displayable");
  await assetPanel.getByLabel("Asset name").fill(mapName);
  await assetPanel.getByLabel("Asset tags").fill("map, harbor");
  await assetPanel.getByLabel("Asset file").setInputFiles(portraitFixturePath);
  await assetPanel.getByRole("button", { name: /Upload/ }).click();
  await expect(assetPanel.getByText(mapName)).toBeVisible();

  await assetPanel.getByLabel("Asset kind").selectOption("npc_portrait");
  await assetPanel.getByLabel("Asset visibility").selectOption("public_displayable");
  await assetPanel.getByLabel("Asset name").fill(portraitName);
  await assetPanel.getByLabel("Asset tags").fill("portrait, token");
  await assetPanel.getByLabel("Asset file").setInputFiles(fixturePath);
  await assetPanel.getByRole("button", { name: /Upload/ }).click();
  await expect(assetPanel.getByText(portraitName)).toBeVisible();

  const mapPanel = page.locator('[data-widget-kind="map_display"]');
  await expect(mapPanel).toBeVisible();
  await expect(mapPanel.getByLabel("Map image asset")).toContainText(mapName);
  await mapPanel.getByRole("button", { name: "Create map" }).click();
  await expect(mapPanel.getByLabel("Campaign maps")).toContainText(mapName);
  await mapPanel.getByRole("button", { name: "Assign active" }).click();
  await expect(mapPanel.getByLabel("Scene maps")).toContainText(`Active · ${mapName}`);
  await expect(mapPanel.locator(".map-renderer img")).toBeVisible();

  const gmGrid = mapPanel.getByLabel("GM grid");
  if (!(await gmGrid.isChecked())) await gmGrid.check();
  await mapPanel.getByLabel("Grid size").fill("40");
  await mapPanel.getByLabel("Grid offset X").fill("4");
  await mapPanel.getByLabel("Grid offset Y").fill("6");
  await mapPanel.getByLabel("Grid color").fill("#00ffcc");
  await mapPanel.getByLabel("Grid opacity").fill("0.55");
  await mapPanel.getByRole("button", { name: "Save grid" }).click();
  await expect(mapPanel.locator(".map-grid line")).not.toHaveCount(0);

  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Open / Reconnect" }).click();
  const player = await popupPromise;
  await player.waitForLoadState("domcontentloaded");
  await expect(page.locator('[data-widget-kind="player_display"]').getByText("connected", { exact: true })).toBeVisible({
    timeout: 6_000
  });

  await mapPanel.getByRole("button", { name: /Send map/ }).click();
  await expect(player.locator(".player-map .map-renderer img")).toBeVisible();
  await expect(player.locator(".player-map .map-grid line")).not.toHaveCount(0);
  await player.screenshot({ path: screenshotPath("player-map-fit-grid.png") });

  await mapPanel.getByText("Tokens", { exact: true }).scrollIntoViewIfNeeded();
  await mapPanel.getByLabel("Token name").fill("Hidden Label Guard");
  await mapPanel.getByLabel("Token visibility").selectOption("player_visible");
  await mapPanel.getByLabel("Token label visibility").selectOption("hidden");
  await mapPanel.getByLabel("Token shape").selectOption("square");
  await mapPanel.getByRole("button", { name: /Create center/ }).click();
  await expect(player.locator(".map-token")).toHaveCount(1);
  await expect(player.getByText("Hidden Label Guard")).toBeHidden();
  await player.screenshot({ path: screenshotPath("player-token-visible-label-hidden.png") });

  await mapPanel.getByLabel("Token name").fill("Captain Portrait");
  await mapPanel.getByLabel("Token visibility").selectOption("player_visible");
  await mapPanel.getByLabel("Token label visibility").selectOption("player_visible");
  await mapPanel.getByLabel("Token shape").selectOption("portrait");
  await expect(mapPanel.getByLabel("Token portrait asset")).toContainText(portraitName);
  await mapPanel.getByLabel("Token portrait asset").selectOption({ label: `${portraitName} · public_displayable` });
  await mapPanel.getByLabel("Token width").fill("48");
  await mapPanel.getByLabel("Token height").fill("48");
  await mapPanel.getByRole("button", { name: /Create center/ }).click();
  await expect(player.getByText("Captain Portrait")).toBeVisible();
  await expect(player.locator(".map-token.shape-portrait img")).toBeVisible();
  await player.screenshot({ path: screenshotPath("player-token-portrait.png") });

  await mapPanel.getByLabel("Token rotation").fill("35");
  await mapPanel.getByRole("button", { name: "Save token" }).click();
  await expect(mapPanel.getByText("Saved").last()).toBeVisible();
  await page.screenshot({ path: screenshotPath("gm-tokens-editing.png") });

  await mapPanel.getByText("Fog", { exact: true }).scrollIntoViewIfNeeded();
  await mapPanel.getByRole("button", { name: /Enable hidden fog/ }).click();
  await mapPanel.getByRole("button", { name: /Send map/ }).click();
  await mapPanel.getByText("Tokens", { exact: true }).scrollIntoViewIfNeeded();
  await mapPanel.getByLabel("Token name").fill("Fog Ambusher");
  await mapPanel.getByLabel("Token visibility").selectOption("hidden_until_revealed");
  await mapPanel.getByLabel("Token label visibility").selectOption("player_visible");
  await mapPanel.getByLabel("Token shape").selectOption("marker");
  await mapPanel.getByLabel("Token portrait asset").selectOption("");
  await mapPanel.getByRole("button", { name: /Create center/ }).click();
  await expect(player.getByText("Fog Ambusher")).toBeHidden();
  await mapPanel.getByText("Fog", { exact: true }).scrollIntoViewIfNeeded();
  await mapPanel.getByRole("button", { name: /Reveal all/ }).click();
  await expect(player.getByText("Fog Ambusher")).toBeVisible();
  await player.screenshot({ path: screenshotPath("player-token-revealed-by-fog.png") });

  await player.reload({ waitUntil: "domcontentloaded" });
  await expect(player.locator(".player-map .map-renderer img")).toBeVisible();
  await expect(player.getByText("Fog Ambusher")).toBeVisible();

  const failingPlayer = await page.context().newPage();
  await failingPlayer.route("**/api/player-display/assets/**/blob", (route) => route.abort("failed"));
  await failingPlayer.goto("/player");
  await expect(failingPlayer.getByText("Map unavailable")).toBeVisible();
  await failingPlayer.screenshot({ path: screenshotPath("player-map-unavailable.png") });
  await failingPlayer.close();

  await page.getByRole("button", { name: "Blackout" }).click();
  await expect(player.locator(".player-blackout")).toBeVisible();
  await expect(player.locator(".player-map .map-renderer img")).toBeHidden();
  await player.screenshot({ path: screenshotPath("player-map-blackout.png") });
});

test("notes public snippet visual flow", async ({ page, request }) => {
  await request.post(`${apiBase}/api/workspace/widgets/reset`);
  await request.post(`${apiBase}/api/runtime/clear`);
  await request.post(`${apiBase}/api/player-display/blackout`);

  await page.goto("/gm/floating");
  const runId = Date.now();
  const campaignName = `Notes Campaign ${runId}`;
  const sessionTitle = `Notes Session ${runId}`;
  const sceneTitle = `Notes Scene ${runId}`;
  const noteTitle = `Private Note ${runId}`;
  const snippetTitle = `Public Clue ${runId}`;
  const safeText = `The bell tolls twice at moonrise ${runId}.`;
  const secretText = `SECRET DO NOT SHOW ${runId}`;

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

  const widgetsResponse = await request.get(`${apiBase}/api/workspace/widgets`);
  expect(widgetsResponse.ok()).toBe(true);
  const widgetsBody = await widgetsResponse.json();
  const notesWidget = widgetsBody.widgets.find((widget: { kind: string }) => widget.kind === "notes");
  const playerWidget = widgetsBody.widgets.find((widget: { kind: string }) => widget.kind === "player_display");
  expect(notesWidget).toBeTruthy();
  expect(playerWidget).toBeTruthy();
  await request.patch(`${apiBase}/api/workspace/widgets/${notesWidget.id}`, {
    data: { x: 24, y: 72, width: 720, height: 820, z_index: 170 }
  });
  await request.patch(`${apiBase}/api/workspace/widgets/${playerWidget.id}`, {
    data: { x: 780, y: 72, width: 380, height: 330, z_index: 180 }
  });
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.locator('[data-widget-kind="runtime"]')).toContainText(sceneTitle);

  const notesPanel = page.locator('[data-widget-kind="notes"]');
  await expect(notesPanel).toBeVisible();
  await notesPanel.getByPlaceholder("Private note title").fill(noteTitle);
  await notesPanel.getByPlaceholder("private, clue").fill("clue, public");
  const privateBody = notesPanel.getByLabel("Private note body");
  await privateBody.fill(`${safeText}\n\n${secretText}`);
  await notesPanel.getByRole("button", { name: /New note/ }).click();
  await expect(notesPanel.getByText(noteTitle)).toBeVisible();

  await notesPanel.getByPlaceholder("Public title").fill(snippetTitle);
  await privateBody.evaluate((element, length) => {
    const textarea = element as HTMLTextAreaElement;
    textarea.focus();
    textarea.setSelectionRange(0, length);
    textarea.dispatchEvent(new Event("select", { bubbles: true }));
  }, safeText.length);
  await notesPanel.getByRole("button", { name: "Copy selection to snippet" }).click();
  await expect(notesPanel.getByText(snippetTitle)).toBeVisible();

  await privateBody.fill(`Changed private note\n\n${secretText}\n\nA different private clue.`);
  await notesPanel.getByRole("button", { name: "Save note" }).click();
  await expect(notesPanel.getByLabel("Public snippet preview")).toContainText(safeText);
  await expect(notesPanel.getByLabel("Public snippet preview")).not.toContainText(secretText);
  await page.screenshot({ path: screenshotPath("gm-notes-snippet-preview.png") });

  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Open / Reconnect" }).click();
  const player = await popupPromise;
  await player.waitForLoadState("domcontentloaded");
  await expect(page.locator('[data-widget-kind="player_display"]').getByText("connected", { exact: true })).toBeVisible({
    timeout: 6_000
  });

  await notesPanel.getByRole("button", { name: /Publish/ }).click();
  await expect(player.locator(".player-text")).toContainText(safeText);
  await expect(player.locator(".player-text")).not.toContainText(secretText);
  await player.screenshot({ path: screenshotPath("player-public-snippet.png") });

  await player.reload({ waitUntil: "domcontentloaded" });
  await expect(player.locator(".player-text")).toContainText(safeText);
  await expect(player.locator(".player-text")).not.toContainText(secretText);
  await player.screenshot({ path: screenshotPath("player-public-snippet-after-refresh.png") });

  await page.locator('[data-widget-kind="player_display"]').getByRole("button", { name: "Blackout" }).click();
  await expect(player.locator(".player-blackout")).toBeVisible();
  await expect(player.getByText(safeText)).toBeHidden();
  await player.screenshot({ path: screenshotPath("player-snippet-blackout.png") });
});

test("scene context staging visual flow", async ({ page, request }) => {
  test.setTimeout(60_000);
  await request.post(`${apiBase}/api/workspace/widgets/reset`);
  await request.post(`${apiBase}/api/runtime/clear`);
  await request.post(`${apiBase}/api/player-display/intermission`);

  const widgetsResponse = await request.get(`${apiBase}/api/workspace/widgets`);
  expect(widgetsResponse.ok()).toBe(true);
  const widgetsBody = await widgetsResponse.json();
  const sceneContextWidget = widgetsBody.widgets.find((widget: { kind: string }) => widget.kind === "scene_context");
  const playerWidget = widgetsBody.widgets.find((widget: { kind: string }) => widget.kind === "player_display");
  expect(sceneContextWidget).toBeTruthy();
  expect(playerWidget).toBeTruthy();
  await request.patch(`${apiBase}/api/workspace/widgets/${sceneContextWidget.id}`, {
    data: { x: 840, y: 72, width: 560, height: 820, z_index: 190 }
  });
  await request.patch(`${apiBase}/api/workspace/widgets/${playerWidget.id}`, {
    data: { x: 440, y: 72, width: 380, height: 330, z_index: 200 }
  });

  await page.goto("/gm/floating");
  const runId = Date.now();
  const campaignName = `Scene Context Campaign ${runId}`;
  const sessionTitle = `Scene Context Session ${runId}`;
  const sceneTitle = `Scene Context Scene ${runId}`;
  const mapName = `Scene Context Map ${runId}`;
  const safeSnippet = `Public staged clue ${runId}`;
  const privateSecret = `PRIVATE SCENE CONTEXT SECRET ${runId}`;

  await page.getByPlaceholder("New campaign").fill(campaignName);
  await page.getByPlaceholder("New campaign").press("Enter");
  await expect(page.getByText(campaignName)).toBeVisible();
  await page.getByPlaceholder("New session").fill(sessionTitle);
  await page.getByPlaceholder("New session").press("Enter");
  await expect(page.locator('[data-widget-kind="sessions"]')).toContainText(sessionTitle);
  await page.getByPlaceholder("New scene").fill(sceneTitle);
  await page.getByPlaceholder("New scene").press("Enter");
  await expect(page.locator('[data-widget-kind="scenes"]')).toContainText(sceneTitle);

  const campaigns = await (await request.get(`${apiBase}/api/campaigns`)).json();
  const campaign = campaigns.find((item: { name: string }) => item.name === campaignName);
  expect(campaign).toBeTruthy();
  const sessions = await (await request.get(`${apiBase}/api/campaigns/${campaign.id}/sessions`)).json();
  const session = sessions.find((item: { title: string }) => item.title === sessionTitle);
  const scenes = await (await request.get(`${apiBase}/api/campaigns/${campaign.id}/scenes`)).json();
  const scene = scenes.find((item: { title: string }) => item.title === sceneTitle);
  expect(session).toBeTruthy();
  expect(scene).toBeTruthy();

  const fixturePath = screenshotPath("scene-context-map-fixture.png");
  writePngFixture(fixturePath);
  const assetResponse = await request.post(`${apiBase}/api/campaigns/${campaign.id}/assets/upload`, {
    multipart: {
      kind: "map_image",
      visibility: "public_displayable",
      name: mapName,
      tags: "scene, context",
      file: {
        name: "scene-context-map.png",
        mimeType: "image/png",
        buffer: fs.readFileSync(fixturePath)
      }
    }
  });
  expect(assetResponse.ok()).toBe(true);
  const asset = await assetResponse.json();
  const mapResponse = await request.post(`${apiBase}/api/campaigns/${campaign.id}/maps`, {
    data: { asset_id: asset.id, name: mapName }
  });
  expect(mapResponse.ok()).toBe(true);
  const campaignMap = await mapResponse.json();
  const sceneMapResponse = await request.post(`${apiBase}/api/campaigns/${campaign.id}/scenes/${scene.id}/maps`, {
    data: { map_id: campaignMap.id, is_active: true, player_fit_mode: "fit", player_grid_visible: true }
  });
  expect(sceneMapResponse.ok()).toBe(true);
  const noteResponse = await request.post(`${apiBase}/api/campaigns/${campaign.id}/notes`, {
    data: {
      title: `Scene Context Note ${runId}`,
      private_body: `${safeSnippet}\n\n${privateSecret}`,
      scene_id: scene.id
    }
  });
  const note = await noteResponse.json();
  const snippetResponse = await request.post(`${apiBase}/api/campaigns/${campaign.id}/public-snippets`, {
    data: { note_id: note.id, title: `Scene Context Snippet ${runId}`, body: safeSnippet, format: "markdown" }
  });
  const snippet = await snippetResponse.json();
  const entityResponse = await request.post(`${apiBase}/api/campaigns/${campaign.id}/entities`, {
    data: { kind: "npc", name: `Scene Context NPC ${runId}`, notes: privateSecret, tags: ["private-context"] }
  });
  const entity = await entityResponse.json();
  const encounterResponse = await request.post(`${apiBase}/api/campaigns/${campaign.id}/combat-encounters`, {
    data: { title: `Scene Context Encounter ${runId}`, session_id: session.id, scene_id: scene.id }
  });
  const encounter = await encounterResponse.json();
  await request.post(`${apiBase}/api/combat-encounters/${encounter.id}/combatants`, {
    data: { name: `Private Enemy ${runId}`, notes: privateSecret, public_visible: false }
  });
  await request.post(`${apiBase}/api/scenes/${scene.id}/entity-links`, {
    data: { entity_id: entity.id, role: "threat", sort_order: 0, notes: "GM-only scene context note" }
  });
  await request.post(`${apiBase}/api/scenes/${scene.id}/public-snippet-links`, {
    data: { public_snippet_id: snippet.id, sort_order: 0 }
  });
  await request.patch(`${apiBase}/api/scenes/${scene.id}/context`, {
    data: {
      active_encounter_id: encounter.id,
      staged_display_mode: "public_snippet",
      staged_public_snippet_id: snippet.id
    }
  });

  await page.reload({ waitUntil: "domcontentloaded" });
  await page.locator('[data-widget-kind="campaigns"]').getByText(campaignName).click();
  await expect(page.locator('[data-widget-kind="scenes"]')).toContainText(sceneTitle);
  await page.locator('[data-widget-kind="scenes"]').getByText(sceneTitle).click();
  const sceneContextPanel = page.locator('[data-widget-kind="scene_context"]');
  await expect(sceneContextPanel).toContainText(mapName);
  await expect(sceneContextPanel).toContainText(`Scene Context Snippet ${runId}`);
  await expect(sceneContextPanel).toContainText(`Scene Context NPC ${runId}`);
  await page.screenshot({ path: screenshotPath("gm-scene-context-configured.png") });

  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Open / Reconnect" }).click();
  const player = await popupPromise;
  await player.waitForLoadState("domcontentloaded");
  await expect(player.locator(".player-intermission")).toContainText("Intermission");
  await player.screenshot({ path: screenshotPath("player-scene-context-before-publish.png") });

  await sceneContextPanel.getByRole("button", { name: /Activate privately/ }).click();
  await expect(page.locator('[data-widget-kind="runtime"]')).toContainText(sceneTitle);
  await expect(player.locator(".player-intermission")).toContainText("Intermission");
  await page.screenshot({ path: screenshotPath("gm-scene-context-after-activation.png") });

  await sceneContextPanel.getByRole("button", { name: /Publish staged display/ }).click();
  await expect(player.locator(".player-text")).toContainText(safeSnippet);
  await expect(player.locator(".player-text")).not.toContainText(privateSecret);
  await player.screenshot({ path: screenshotPath("player-scene-context-after-publish.png") });
});

test("party tracker visual flow", async ({ page, request }) => {
  test.setTimeout(75_000);
  await request.post(`${apiBase}/api/workspace/widgets/reset`);
  await request.post(`${apiBase}/api/runtime/clear`);
  await request.post(`${apiBase}/api/player-display/blackout`);

  const widgetsResponse = await request.get(`${apiBase}/api/workspace/widgets`);
  expect(widgetsResponse.ok()).toBe(true);
  const widgetsBody = await widgetsResponse.json();
  const assetWidget = widgetsBody.widgets.find((widget: { kind: string }) => widget.kind === "asset_library");
  const partyWidget = widgetsBody.widgets.find((widget: { kind: string }) => widget.kind === "party_tracker");
  const playerWidget = widgetsBody.widgets.find((widget: { kind: string }) => widget.kind === "player_display");
  expect(assetWidget).toBeTruthy();
  expect(partyWidget).toBeTruthy();
  expect(playerWidget).toBeTruthy();
  await request.patch(`${apiBase}/api/workspace/widgets/${assetWidget.id}`, {
    data: { x: 24, y: 72, width: 430, height: 430, z_index: 160 }
  });
  await request.patch(`${apiBase}/api/workspace/widgets/${partyWidget.id}`, {
    data: { x: 480, y: 72, width: 760, height: 820, z_index: 170 }
  });
  await request.patch(`${apiBase}/api/workspace/widgets/${playerWidget.id}`, {
    data: { x: 1264, y: 72, width: 380, height: 330, z_index: 180 }
  });

  const runId = Date.now();
  const campaignName = `Party Campaign ${runId}`;
  const entityName = `Aria QA ${runId}`;
  const displayName = `Aria ${runId}`;
  const portraitName = `Party Portrait ${runId}`;
  const secretNotes = `PRIVATE PARTY NOTES ${runId}`;
  const privateTag = `private-party-tag-${runId}`;
  const fixturePath = screenshotPath("party-portrait-fixture.png");
  writePngFixture(fixturePath);

  await page.goto("/gm/floating");
  await expect(page.getByText("Backend linked")).toBeVisible();
  await page.getByPlaceholder("New campaign").fill(campaignName);
  await page.getByPlaceholder("New campaign").press("Enter");
  await expect(page.getByText(campaignName)).toBeVisible();
  const assetPanel = page.locator('[data-widget-kind="asset_library"]');
  const partyPanel = page.locator('[data-widget-kind="party_tracker"]');
  await page.locator('[data-widget-kind="campaigns"]').getByRole("button", { name: campaignName }).click({ force: true });
  await expect(assetPanel.getByText("Blue Forest Road Map")).toHaveCount(0);
  await expect(partyPanel.getByText("Errin · pc")).toHaveCount(0);

  await assetPanel.getByLabel("Asset kind").selectOption("npc_portrait");
  await assetPanel.getByLabel("Asset visibility").selectOption("public_displayable");
  await assetPanel.getByLabel("Asset name").fill(portraitName);
  await assetPanel.getByLabel("Asset tags").fill("party, portrait");
  await assetPanel.getByLabel("Asset file").setInputFiles(fixturePath);
  await assetPanel.getByRole("button", { name: /Upload/ }).click();
  await expect(assetPanel.getByText(portraitName)).toBeVisible();

  await expect(partyPanel).toBeVisible();
  await partyPanel.getByLabel("Entity kind").selectOption("pc");
  await partyPanel.getByLabel("Entity name").fill(entityName);
  await partyPanel.getByLabel("Entity display name").fill(displayName);
  await partyPanel.getByLabel("Entity visibility").selectOption("public_known");
  await expect(partyPanel.getByLabel("Entity portrait")).toContainText(portraitName);
  await partyPanel.getByLabel("Entity portrait").selectOption({ label: `${portraitName} · public_displayable` });
  await partyPanel.getByLabel("Entity tags").fill(privateTag);
  await partyPanel.getByLabel("Entity notes").fill(secretNotes);
  await partyPanel.getByRole("button", { name: /New entity/ }).click();
  await expect(partyPanel.getByText(`${entityName} · pc`)).toBeVisible();

  async function createField(key: string, label: string, type: string, options = "") {
    await partyPanel.getByRole("button", { name: "Clear field form" }).click();
    await expect(partyPanel.getByLabel("Custom field key")).toBeEnabled();
    await partyPanel.getByLabel("Custom field key").fill(key);
    await partyPanel.getByLabel("Custom field label").fill(label);
    await partyPanel.getByLabel("Custom field type").selectOption(type);
    if (options) await partyPanel.getByLabel("Custom field options").fill(options);
    await partyPanel.getByRole("button", { name: /New field/ }).click();
    await expect(partyPanel.getByText(`${label} · ${type}`)).toBeVisible();
  }

  await createField("hp", "HP", "resource");
  await createField("role", "Role", "select", "Leader, Scout");
  await createField("traits", "Traits", "multi_select", "Brave, Cautious");
  await createField("emblem", "Emblem", "image");

  await partyPanel.getByPlaceholder("current/max").fill("22/31");
  await partyPanel.locator("label").filter({ hasText: "Role" }).locator("select").selectOption("Scout");
  await partyPanel.getByPlaceholder("multi_select").fill("Brave, Cautious");
  await partyPanel.locator("label").filter({ hasText: "Emblem" }).locator("select").selectOption({ label: portraitName });
  await partyPanel.getByRole("button", { name: "Save values" }).click();

  await partyPanel.getByRole("button", { name: "Add selected PC" }).click();
  for (const label of ["HP", "Role", "Traits", "Emblem"]) {
    const row = partyPanel.locator(".party-field-row").filter({ hasText: label });
    await row.locator("input[type=checkbox]").nth(0).check();
    await row.locator("input[type=checkbox]").nth(1).check();
  }
  await partyPanel.getByLabel("Party layout").selectOption("standard");
  await partyPanel.getByRole("button", { name: "Save party" }).click();
  await expect(partyPanel.locator(".party-card-preview")).toContainText(displayName);
  await page.screenshot({ path: screenshotPath("gm-party-tracker-editing.png") });

  await page.reload({ waitUntil: "domcontentloaded" });
  await page.locator('[data-widget-kind="campaigns"]').getByText(campaignName).click();
  const reloadedPartyPanel = page.locator('[data-widget-kind="party_tracker"]');
  await expect(reloadedPartyPanel).toContainText(displayName);
  await expect(reloadedPartyPanel.locator(".party-card-preview")).toContainText("HP: 22/31");
  await page.screenshot({ path: screenshotPath("gm-party-tracker-after-refresh.png") });

  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Open / Reconnect" }).click();
  const player = await popupPromise;
  await player.waitForLoadState("domcontentloaded");
  await expect(page.locator('[data-widget-kind="player_display"]').getByText("connected", { exact: true })).toBeVisible({
    timeout: 6_000
  });

  await reloadedPartyPanel.getByRole("button", { name: /Publish party/ }).click();
  await expect(player.locator(".player-party")).toContainText(displayName);
  await expect(player.locator(".player-party")).toContainText("HP");
  await expect(player.locator(".player-party")).toContainText("22/31");
  await expect(player.locator(".player-party")).toContainText("Role");
  await expect(player.locator(".player-party")).toContainText("Scout");
  await expect(player.locator(".player-party")).not.toContainText(secretNotes);
  await expect(player.locator(".player-party")).not.toContainText(privateTag);
  await player.screenshot({ path: screenshotPath("player-party-cards.png") });

  await player.reload({ waitUntil: "domcontentloaded" });
  await expect(player.locator(".player-party")).toContainText(displayName);

  await page.locator('[data-widget-kind="player_display"]').getByRole("button", { name: "Blackout" }).click();
  await expect(player.locator(".player-blackout")).toBeVisible();
  await expect(player.getByText(displayName)).toBeHidden();
  await player.screenshot({ path: screenshotPath("player-party-blackout.png") });
});

test("combat tracker visual flow", async ({ page, request }) => {
  test.setTimeout(75_000);
  await request.post(`${apiBase}/api/workspace/widgets/reset`);
  await request.post(`${apiBase}/api/runtime/clear`);
  await request.post(`${apiBase}/api/player-display/blackout`);

  const widgetsResponse = await request.get(`${apiBase}/api/workspace/widgets`);
  expect(widgetsResponse.ok()).toBe(true);
  const widgetsBody = await widgetsResponse.json();
  const combatWidget = widgetsBody.widgets.find((widget: { kind: string }) => widget.kind === "combat_tracker");
  const playerWidget = widgetsBody.widgets.find((widget: { kind: string }) => widget.kind === "player_display");
  expect(combatWidget).toBeTruthy();
  expect(playerWidget).toBeTruthy();
  await request.patch(`${apiBase}/api/workspace/widgets/${combatWidget.id}`, {
    data: { x: 480, y: 72, width: 780, height: 820, z_index: 190 }
  });
  await request.patch(`${apiBase}/api/workspace/widgets/${playerWidget.id}`, {
    data: { x: 1284, y: 72, width: 380, height: 330, z_index: 200 }
  });

  const runId = Date.now();
  const campaignName = `Combat Campaign ${runId}`;
  const sessionTitle = `Combat Session ${runId}`;
  const sceneTitle = `Combat Scene ${runId}`;
  const pcName = `Aria Combat ${runId}`;
  const safeStatus = `Blessed ${runId}`;
  const secretCondition = `PRIVATE CONDITION ${runId}`;
  const secretNote = `PRIVATE COMBAT NOTE ${runId}`;
  const enemyName = `Hidden Enemy ${runId}`;

  const campaignResponse = await request.post(`${apiBase}/api/campaigns`, {
    data: { name: campaignName, description: "Combat tracker QA" }
  });
  expect(campaignResponse.ok()).toBe(true);
  const campaign = await campaignResponse.json();
  const sessionResponse = await request.post(`${apiBase}/api/campaigns/${campaign.id}/sessions`, {
    data: { title: sessionTitle }
  });
  const session = await sessionResponse.json();
  const sceneResponse = await request.post(`${apiBase}/api/campaigns/${campaign.id}/scenes`, {
    data: { title: sceneTitle, session_id: session.id }
  });
  const scene = await sceneResponse.json();
  const entityResponse = await request.post(`${apiBase}/api/campaigns/${campaign.id}/entities`, {
    data: { kind: "pc", name: pcName, display_name: pcName, visibility: "public_known", notes: "PRIVATE ENTITY NOTE" }
  });
  expect(entityResponse.ok()).toBe(true);
  const entity = await entityResponse.json();
  await request.post(`${apiBase}/api/runtime/activate-scene`, { data: { scene_id: scene.id } });

  await page.goto("/gm/floating");
  await expect(page.getByText("Backend linked")).toBeVisible();
  await page.locator('[data-widget-kind="campaigns"]').getByText(campaignName).click();
  const combatPanel = page.locator('[data-widget-kind="combat_tracker"]');
  await expect(combatPanel).toBeVisible();

  await combatPanel.getByLabel("Encounter title").fill(`Deck Fight ${runId}`);
  await combatPanel.getByRole("button", { name: /New encounter/ }).click();
  await expect(combatPanel).toContainText(`Deck Fight ${runId}`);
  await expect(combatPanel).toContainText("round 1");

  await combatPanel.getByLabel("Combatant entity").selectOption(entity.id);
  await combatPanel.getByLabel("Combatant disposition").selectOption("pc");
  await combatPanel.getByLabel("Combatant name").fill(pcName);
  await combatPanel.getByLabel("Combatant initiative").fill("18");
  await combatPanel.getByLabel("Combatant AC").fill("15");
  await combatPanel.getByLabel("Combatant HP current").fill("22");
  await combatPanel.getByLabel("Combatant HP max").fill("31");
  await combatPanel.getByLabel("Combatant temp HP").fill("3");
  await combatPanel.getByLabel("Combatant public status").fill(safeStatus);
  await combatPanel.getByLabel("Combatant private conditions").fill(secretCondition);
  await combatPanel.getByLabel("Combatant notes").fill(secretNote);
  await combatPanel.locator("label").filter({ hasText: "Public initiative" }).locator("input").check();
  await combatPanel.getByRole("button", { name: /Add combatant/ }).click();
  await expect(combatPanel.locator(".combat-order-list")).toContainText(pcName);

  await combatPanel.getByLabel("Combatant entity").selectOption("");
  await combatPanel.getByLabel("Combatant name").fill(enemyName);
  await combatPanel.getByLabel("Combatant disposition").selectOption("enemy");
  await combatPanel.getByLabel("Combatant initiative").fill("14");
  await combatPanel.getByLabel("Combatant AC").fill("13");
  await combatPanel.getByLabel("Combatant HP current").fill("18");
  await combatPanel.getByLabel("Combatant HP max").fill("18");
  await combatPanel.getByLabel("Combatant public status").fill("");
  await combatPanel.getByLabel("Combatant private conditions").fill(`SECRET ENEMY ${runId}`);
  await combatPanel.getByLabel("Combatant notes").fill(`PRIVATE ENEMY NOTE ${runId}`);
  const publicInitiativeToggle = combatPanel.locator("label").filter({ hasText: "Public initiative" }).locator("input");
  if (await publicInitiativeToggle.isChecked()) await publicInitiativeToggle.uncheck();
  await combatPanel.getByRole("button", { name: /Add combatant/ }).click();
  await expect(combatPanel.locator(".combat-order-list")).toContainText(enemyName);

  await combatPanel.getByRole("button", { name: `Move ${enemyName} up` }).click();
  await combatPanel.getByRole("button", { name: "Next turn" }).click();
  await page.screenshot({ path: screenshotPath("gm-combat-tracker-editing.png") });

  await page.reload({ waitUntil: "domcontentloaded" });
  await page.locator('[data-widget-kind="campaigns"]').getByText(campaignName).click();
  const reloadedCombatPanel = page.locator('[data-widget-kind="combat_tracker"]');
  await expect(reloadedCombatPanel.locator(".combat-order-list")).toContainText(pcName);
  await expect(reloadedCombatPanel.locator(".combat-order-list")).toContainText(enemyName);
  await page.screenshot({ path: screenshotPath("gm-combat-tracker-after-refresh.png") });

  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Open / Reconnect" }).click();
  const player = await popupPromise;
  await player.waitForLoadState("domcontentloaded");
  await expect(page.locator('[data-widget-kind="player_display"]').getByText("connected", { exact: true })).toBeVisible({
    timeout: 6_000
  });

  await reloadedCombatPanel.getByRole("button", { name: /Publish initiative/ }).click();
  await expect(player.locator(".player-initiative")).toContainText(pcName);
  await expect(player.locator(".player-initiative")).toContainText(safeStatus);
  await expect(player.locator(".player-initiative")).not.toContainText(enemyName);
  await expect(player.locator(".player-initiative")).not.toContainText("HP");
  await expect(player.locator(".player-initiative")).not.toContainText("AC");
  await expect(player.locator(".player-initiative")).not.toContainText(secretCondition);
  await expect(player.locator(".player-initiative")).not.toContainText(secretNote);
  await player.screenshot({ path: screenshotPath("player-initiative-order.png") });

  await page.locator('[data-widget-kind="player_display"]').getByRole("button", { name: "Blackout" }).click();
  await expect(player.locator(".player-blackout")).toBeVisible();
  await expect(player.getByText(pcName)).toBeHidden();
  await player.screenshot({ path: screenshotPath("player-initiative-blackout.png") });
});

test("player display initial backend failure is visibly degraded", async ({ page }) => {
  await page.route("**/api/player-display", (route) => route.abort("failed"));

  await page.goto("/player");

  await expect(page.getByText("Player display unavailable")).toBeVisible();
  await page.screenshot({ path: screenshotPath("player-degraded-backend-unavailable.png") });
});
