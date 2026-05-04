import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const screenshotDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../artifacts/playwright");

function screenshotPath(name: string): string {
  fs.mkdirSync(screenshotDir, { recursive: true });
  return path.join(screenshotDir, name);
}

function json(body: unknown, status = 200) {
  return {
    status,
    contentType: "application/json",
    body: JSON.stringify(body)
  };
}

const playerState = {
  mode: "blackout",
  title: "Blackout",
  subtitle: null,
  active_campaign_id: "c1",
  active_campaign_name: "Campaign",
  active_session_id: "s1",
  active_session_title: "Opening",
  active_scene_id: "sc1",
  active_scene_title: "Bridge",
  payload: {},
  revision: 1,
  identify_revision: 0,
  identify_until: null,
  updated_at: "2026-05-04T00:00:00Z"
};

const provider = {
  id: "p1",
  label: "Fixture provider",
  vendor: "custom",
  base_url: "http://127.0.0.1:9999/v1",
  model_id: "fixture",
  key_source: { type: "none", ref: null },
  conformance_level: "level_2_json_validated",
  capabilities: {},
  last_probe_result: null,
  probed_at: "z",
  created_at: "z",
  updated_at: "z"
};

function contextPackage(reviewStatus: "unreviewed" | "reviewed") {
  return {
    id: "ctx-public",
    campaign_id: "c1",
    session_id: "s1",
    scene_id: null,
    task_kind: "session.player_safe_recap",
    scope_kind: "session",
    visibility_mode: "public_safe",
    gm_instruction: "Draft a player-safe recap from curated sources.",
    source_refs: [
      {
        kind: "session_recap",
        id: "r1",
        sourceClass: "memory_entry",
        lane: "canon",
        visibility: "public_safe",
        title: "Moon Gate",
        body: "The party repaired the moon gate in public."
      }
    ],
    rendered_prompt: "PUBLIC-SAFE CONTEXT:\nThe party repaired the moon gate in public.",
    source_ref_hash: "hash-public",
    source_classes: ["memory_entry"],
    context_options: { includeUnshownPublicSnippets: false, excludedSourceRefs: [] },
    warnings: [],
    review_status: reviewStatus,
    reviewed_at: reviewStatus === "reviewed" ? "z" : null,
    reviewed_by: reviewStatus === "reviewed" ? "local_gm" : null,
    token_estimate: 123,
    created_at: "z",
    updated_at: "z"
  };
}

test("Scribe player-safe recap visual inspection does not publish", async ({ page }) => {
  let recapEligible = false;
  let createdSnippet = false;
  const playerPayloads: unknown[] = [];
  const recaps = () => [
    {
      id: "r1",
      campaign_id: "c1",
      session_id: "s1",
      source_llm_run_id: null,
      title: "Moon Gate",
      body_markdown: "The party repaired the moon gate in public.",
      evidence_refs: [],
      public_safe: recapEligible,
      sensitivity_reason: recapEligible ? null : "private_note",
      created_at: "z",
      updated_at: recapEligible ? "z2" : "z"
    }
  ];
  const createdPublicSnippet = {
    id: "sn1",
    campaign_id: "c1",
    note_id: null,
    title: "Moon Gate",
    body: "The party repaired the moon gate. Unknown to the party, this wording needs review.",
    format: "markdown",
    creation_source: "llm_scribe",
    source_llm_run_id: "run-public",
    source_draft_hash: "draft-hash",
    safety_warnings: [{ code: "unknown_to_party", severity: "high", message: "May reveal something unknown to the players." }],
    last_published_at: null,
    publication_count: 0,
    created_at: "z",
    updated_at: "z"
  };

  await page.route("**/*", async (route) => {
    const url = route.request().url();
    if (url.endsWith("/health")) return route.fulfill(json({ status: "ok", db: "ok", schema_version: "20260504_0016", db_path: "data/db", time: "z" }));
    if (url.endsWith("/api/meta")) return route.fulfill(json({ app: "myroll", version: "dev", db_path: "data/db", schema_version: "20260504_0016", seed_version: "seed", expected_seed_version: "seed" }));
    if (url.endsWith("/api/player-display")) {
      playerPayloads.push(playerState);
      return route.fulfill(json(playerState));
    }
    if (url.endsWith("/api/workspace/widgets")) return route.fulfill(json({ updated_at: "z", widgets: [{ id: "w1", scope_type: "global", scope_id: null, kind: "scribe", title: "Scribe", x: 24, y: 72, width: 900, height: 820, z_index: 10, locked: false, minimized: false, config: {}, created_at: "z", updated_at: "z" }] }));
    if (url.endsWith("/api/campaigns")) return route.fulfill(json([{ id: "c1", name: "Campaign", description: "", created_at: "z", updated_at: "z" }]));
    if (url.endsWith("/api/runtime")) return route.fulfill(json({ active_campaign_id: "c1", active_campaign_name: "Campaign", active_session_id: "s1", active_session_title: "Opening", active_scene_id: "sc1", active_scene_title: "Bridge", updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/sessions")) return route.fulfill(json([{ id: "s1", campaign_id: "c1", title: "Opening", starts_at: null, ended_at: null, created_at: "z", updated_at: "z" }]));
    if (url.endsWith("/api/campaigns/c1/scenes")) return route.fulfill(json([{ id: "sc1", campaign_id: "c1", session_id: "s1", title: "Bridge", summary: "", created_at: "z", updated_at: "z" }]));
    if (url.includes("/api/campaigns/c1/scribe/transcript-events")) return route.fulfill(json({ events: [], projection: [], updated_at: "z" }));
    if (url.endsWith("/api/llm/provider-profiles")) return route.fulfill(json({ profiles: [provider], updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/scribe/memory-candidates")) return route.fulfill(json({ candidates: [], updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/scribe/aliases")) return route.fulfill(json([]));
    if (url.endsWith("/api/campaigns/c1/proposal-sets")) return route.fulfill(json({ proposal_sets: [], updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/planning-markers")) return route.fulfill(json({ planning_markers: [], updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/public-snippets")) {
      if (route.request().method() === "POST") {
        createdSnippet = true;
        return route.fulfill(json(createdPublicSnippet, 201));
      }
      return route.fulfill(json({ snippets: createdSnippet ? [createdPublicSnippet] : [], updated_at: "z" }));
    }
    if (url.endsWith("/api/campaigns/c1/scribe/session-recaps?session_id=s1")) return route.fulfill(json({ recaps: recaps(), updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/scribe/memory-entries?session_id=s1")) return route.fulfill(json({ entries: [], updated_at: "z" }));
    if (url.endsWith("/api/scribe/session-recaps/r1/public-safety")) {
      recapEligible = true;
      return route.fulfill(json(recaps()[0]));
    }
    if (url.endsWith("/api/campaigns/c1/llm/context-preview")) return route.fulfill(json(contextPackage("unreviewed"), 201));
    if (url.endsWith("/api/llm/context-packages/ctx-public/review")) return route.fulfill(json(contextPackage("reviewed")));
    if (url.endsWith("/api/campaigns/c1/llm/player-safe-recap/build")) {
      return route.fulfill(
        json({
          run: {
            id: "run-public",
            campaign_id: "c1",
            session_id: "s1",
            provider_profile_id: "p1",
            context_package_id: "ctx-public",
            parent_run_id: null,
            task_kind: "session.player_safe_recap",
            status: "succeeded",
            error_code: null,
            error_message: null,
            parse_failure_reason: null,
            repair_attempted: false,
            request_metadata: { payloadRetention: "metadata_only" },
            response_text: null,
            normalized_output: null,
            prompt_tokens_estimate: 100,
            duration_ms: 42,
            cancel_requested_at: null,
            created_at: "z",
            updated_at: "z"
          },
          public_snippet_draft: {
            title: "Moon Gate",
            bodyMarkdown: "The party repaired the moon gate."
          },
          source_draft_hash: "draft-hash",
          warnings: []
        })
      );
    }
    if (url.endsWith("/api/campaigns/c1/scribe/public-safety-warnings")) {
      return route.fulfill(
        json({
          warnings: [{ code: "unknown_to_party", severity: "high", message: "May reveal something unknown to the players.", matched_text: "Unknown to the party" }],
          content_hash: "scan-hash",
          ack_required: true
        })
      );
    }
    return route.continue();
  });

  await page.goto("/gm/floating");
  const playerBefore = await page.evaluate(async () => fetch("/api/player-display").then((response) => response.json()));
  await expect(page.getByText("Player-Safe Recap", { exact: true }).first()).toBeVisible();
  await page.screenshot({ path: screenshotPath("scribe-player-safe-before.png"), fullPage: true });

  await page.getByRole("button", { name: "Mark eligible" }).click();
  await expect(page.getByText("Eligible for public-safe context").first()).toBeVisible();
  await page.getByPlaceholder("Public-facing focus. With no curated sources, provide at least 40 characters.").fill("Draft a player-safe recap from curated sources.");
  await page.getByRole("button", { name: "Preview Public-Safe Context", exact: true }).click();
  await expect(page.getByText(/unreviewed · 1 included/)).toBeVisible();
  await page.getByRole("button", { name: "Review Public-Safe Context", exact: true }).click();
  await expect(page.getByText(/reviewed · 1 included/)).toBeVisible();
  await page.screenshot({ path: screenshotPath("scribe-player-safe-reviewed.png"), fullPage: true });

  await page.getByRole("button", { name: "Run Player-Safe Recap", exact: true }).click();
  await expect(page.getByText("Draft Public Snippet")).toBeVisible();
  await page.getByLabel("Player-safe snippet body").fill("The party repaired the moon gate. Unknown to the party, this wording needs review.");
  await page.getByRole("button", { name: "Scan Warnings", exact: true }).click();
  await expect(page.getByText("high: unknown_to_party")).toBeVisible();
  await page.getByRole("button", { name: "Acknowledge Warnings", exact: true }).click();
  await page.screenshot({ path: screenshotPath("scribe-player-safe-warning-ack.png"), fullPage: true });

  await page.getByRole("button", { name: "Create PublicSnippet", exact: true }).click();
  await expect(page.getByText("Created snippet. It is not published until you use the existing display action.")).toBeVisible();
  const playerAfter = await page.evaluate(async () => fetch("/api/player-display").then((response) => response.json()));
  expect(playerAfter).toEqual(playerBefore);
  expect(playerPayloads).toHaveLength(2);
});
