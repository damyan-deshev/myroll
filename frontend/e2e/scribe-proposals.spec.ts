import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const screenshotDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../artifacts/playwright");
const docScreenshotDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../docs/screenshots/scribe-faq");

function screenshotPath(name: string): string {
  fs.mkdirSync(screenshotDir, { recursive: true });
  return path.join(screenshotDir, name);
}

function docScreenshotPath(name: string): string {
  fs.mkdirSync(docScreenshotDir, { recursive: true });
  return path.join(docScreenshotDir, name);
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

test("Scribe branch proposal visual inspection keeps planning private", async ({ page }) => {
  let proposalBuilt = false;
  let markerActive = false;
  let markerAttempt = 0;
  const playerPayloads: unknown[] = [];
  const activeMarker = {
    id: "m1",
    campaign_id: "c1",
    session_id: "s1",
    scene_id: "sc1",
    source_proposal_option_id: "opt1",
    scope_kind: "scene",
    status: "active",
    title: "Political debt",
    marker_text: "Varos betrayed the party.",
    original_marker_text: "GM is considering developing Varos as a political creditor.",
    lint_warnings: ["canonish_wording"],
    provenance: { proposalSetId: "ps1", proposalOptionId: "opt1", llmRunId: "run1", contextPackageId: "ctx-branch" },
    edited_at: "2026-05-04T00:00:00Z",
    edited_from_source: true,
    expires_at: null,
    created_at: "2026-05-04T00:00:00Z",
    updated_at: "2026-05-04T00:00:00Z"
  };
  const proposalSet = {
    proposal_set: {
      id: "ps1",
      campaign_id: "c1",
      session_id: "s1",
      scene_id: "sc1",
      llm_run_id: "run1",
      context_package_id: "ctx-branch",
      task_kind: "scene.branch_directions",
      scope_kind: "scene",
      title: "Bridge branch options",
      status: "proposed",
      option_count: 2,
      selected_count: 0,
      active_marker_count: markerActive ? 1 : 0,
      rejected_count: 0,
      saved_count: 0,
      has_warnings: true,
      warning_count: 1,
      degraded: true,
      repair_attempted: false,
      created_at: "2026-05-04T00:00:00Z",
      updated_at: "2026-05-04T00:00:00Z"
    },
    options: [
      {
        id: "opt1",
        proposal_set_id: "ps1",
        option_index: 0,
        stable_option_key: "political_debt",
        title: "Political debt",
        summary: "Make Varos helpful but costly.",
        body: "RAW PROPOSAL BODY: draft-only branch text that must not enter future context.",
        consequences: "Varos asks for a favor later if this is played.",
        reveals: "Varos has leverage.",
        stays_hidden: "The patron remains hidden.",
        proposed_delta: { possible: "debt" },
        planning_marker_text: "GM is considering developing Varos as a political creditor.",
        status: markerActive ? "selected" : "proposed",
        selected_at: markerActive ? "2026-05-04T00:00:00Z" : null,
        canonized_at: null,
        active_planning_marker_id: markerActive ? "m1" : null,
        created_at: "2026-05-04T00:00:00Z",
        updated_at: "2026-05-04T00:00:00Z"
      },
      {
        id: "opt2",
        proposal_set_id: "ps1",
        option_index: 1,
        stable_option_key: "broken_bridge",
        title: "Broken bridge",
        summary: "Move the tension to the bridge itself.",
        body: "Second raw branch body.",
        consequences: "Travel changes if played.",
        reveals: "Old damage matters.",
        stays_hidden: "The saboteur remains hidden.",
        proposed_delta: { possible: "bridge" },
        planning_marker_text: "GM is considering making the bridge failure the immediate pressure.",
        status: "proposed",
        selected_at: null,
        canonized_at: null,
        active_planning_marker_id: null,
        created_at: "2026-05-04T00:00:00Z",
        updated_at: "2026-05-04T00:00:00Z"
      }
    ],
    planning_markers: [],
    run: {
      id: "run1",
      campaign_id: "c1",
      session_id: "s1",
      provider_profile_id: "p1",
      context_package_id: "ctx-branch",
      parent_run_id: null,
      task_kind: "scene.branch_directions",
      status: "succeeded",
      error_code: null,
      error_message: null,
      parse_failure_reason: null,
      repair_attempted: false,
      request_metadata: { payloadRetention: "metadata_only" },
      response_text: null,
      normalized_output: null,
      prompt_tokens_estimate: 100,
      duration_ms: 41,
      cancel_requested_at: null,
      created_at: "2026-05-04T00:00:00Z",
      updated_at: "2026-05-04T00:00:00Z"
    },
    context_package: null,
    normalization_warnings: [{ code: "degraded_option_count", expected: "3-5", accepted: 2 }]
  };

  await page.route("**/*", async (route) => {
    const url = route.request().url();
    if (url.endsWith("/health")) return route.fulfill(json({ status: "ok", db: "ok", schema_version: "20260504_0016", db_path: "data/db", time: "z" }));
    if (url.endsWith("/api/meta")) return route.fulfill(json({ app: "myroll", version: "dev", db_path: "data/db", schema_version: "20260504_0016", seed_version: "seed", expected_seed_version: "seed" }));
    if (url.endsWith("/api/player-display")) {
      playerPayloads.push(playerState);
      return route.fulfill(json(playerState));
    }
    if (url.endsWith("/api/workspace/widgets")) return route.fulfill(json({ updated_at: "z", widgets: [{ id: "w1", scope_type: "global", scope_id: null, kind: "scribe", title: "Scribe", x: 24, y: 72, width: 820, height: 760, z_index: 10, locked: false, minimized: false, config: {}, created_at: "z", updated_at: "z" }] }));
    if (url.endsWith("/api/campaigns")) return route.fulfill(json([{ id: "c1", name: "Campaign", description: "", created_at: "z", updated_at: "z" }]));
    if (url.endsWith("/api/runtime")) return route.fulfill(json({ active_campaign_id: "c1", active_campaign_name: "Campaign", active_session_id: "s1", active_session_title: "Opening", active_scene_id: "sc1", active_scene_title: "Bridge", updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/sessions")) return route.fulfill(json([{ id: "s1", campaign_id: "c1", title: "Opening", starts_at: null, ended_at: null, created_at: "z", updated_at: "z" }]));
    if (url.endsWith("/api/campaigns/c1/scenes")) return route.fulfill(json([{ id: "sc1", campaign_id: "c1", session_id: "s1", title: "Bridge", summary: "", created_at: "z", updated_at: "z" }]));
    if (url.includes("/api/campaigns/c1/scribe/transcript-events")) return route.fulfill(json({ events: [], projection: [], updated_at: "z" }));
    if (url.endsWith("/api/llm/provider-profiles")) return route.fulfill(json({ profiles: [{ id: "p1", label: "Fixture provider", vendor: "custom", base_url: "http://127.0.0.1:9999/v1", model_id: "fixture", key_source: { type: "none", ref: null }, conformance_level: "level_2_json_validated", capabilities: {}, last_probe_result: null, probed_at: "z", created_at: "z", updated_at: "z" }], updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/scribe/memory-candidates")) return route.fulfill(json({ candidates: [], updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/scribe/aliases")) return route.fulfill(json([]));
    if (url.endsWith("/api/campaigns/c1/public-snippets")) return route.fulfill(json({ snippets: [], updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/scribe/session-recaps?session_id=s1")) return route.fulfill(json({ recaps: [], updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/scribe/memory-entries?session_id=s1")) return route.fulfill(json({ entries: [], updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/proposal-sets")) return route.fulfill(json({ proposal_sets: proposalBuilt ? [proposalSet.proposal_set] : [], updated_at: "z" }));
    if (url.endsWith("/api/proposal-sets/ps1")) return route.fulfill(json(proposalSet));
    if (url.endsWith("/api/campaigns/c1/planning-markers")) return route.fulfill(json({ planning_markers: markerActive ? [activeMarker] : [], updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/llm/context-preview")) return route.fulfill(json({ id: "ctx-branch", campaign_id: "c1", session_id: "s1", scene_id: "sc1", task_kind: "scene.branch_directions", scope_kind: "scene", visibility_mode: "gm_private", gm_instruction: "Make Varos political.", source_refs: [{ kind: "scene", id: "sc1", sourceClass: "scene", lane: "canon", visibility: "gm_private" }], rendered_prompt: "Rendered branch prompt. GM PLANNING CONTEXT, NOT PLAYED EVENTS.", source_ref_hash: "hash", source_classes: ["scene"], warnings: [], review_status: "unreviewed", reviewed_at: null, reviewed_by: null, token_estimate: 123, created_at: "z", updated_at: "z" }));
    if (url.endsWith("/api/llm/context-packages/ctx-branch/review")) return route.fulfill(json({ id: "ctx-branch", campaign_id: "c1", session_id: "s1", scene_id: "sc1", task_kind: "scene.branch_directions", scope_kind: "scene", visibility_mode: "gm_private", gm_instruction: "Make Varos political.", source_refs: [{ kind: "scene", id: "sc1", sourceClass: "scene", lane: "canon", visibility: "gm_private" }], rendered_prompt: "Rendered branch prompt. GM PLANNING CONTEXT, NOT PLAYED EVENTS.", source_ref_hash: "hash", source_classes: ["scene"], warnings: [], review_status: "reviewed", reviewed_at: "z", reviewed_by: "local_gm", token_estimate: 123, created_at: "z", updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/llm/branch-directions/build")) {
      proposalBuilt = true;
      return route.fulfill(json({ run: proposalSet.run, proposal_set: proposalSet, rejected_options: [], warnings: proposalSet.normalization_warnings }));
    }
    if (url.endsWith("/api/proposal-options/opt1/create-planning-marker")) {
      markerAttempt += 1;
      if (markerAttempt === 1) return route.fulfill(json({ error: { code: "marker_lint_confirmation_required", message: "Planning marker wording needs explicit confirmation" } }, 409));
      markerActive = true;
      return route.fulfill(json(activeMarker));
    }
    return route.continue();
  });

  await page.goto("/gm/floating");
  const playerBefore = await page.evaluate(async () => fetch("/api/player-display").then((response) => response.json()));
  await expect(page.getByText("Proposal Cockpit")).toBeVisible();
  await page.screenshot({ path: screenshotPath("scribe-proposals-before.png"), fullPage: true });

  await page.getByPlaceholder("What kind of directions should Scribe explore?").fill("Make Varos political.");
  await page.getByRole("button", { name: "Preview Branch Context", exact: true }).click();
  await page.getByText("Branch Diagnostics").click();
  await expect(page.getByText(/scene · unreviewed/)).toBeVisible();
  await page.getByRole("button", { name: "Review Branch Context", exact: true }).click();
  await expect(page.getByText(/scene · reviewed/)).toBeVisible();
  await page.screenshot({ path: screenshotPath("scribe-proposals-reviewed-context.png"), fullPage: true });

  await page.getByRole("button", { name: "Run Branch Directions", exact: true }).click();
  await expect(page.getByText("Degraded output: 2 options")).toBeVisible();
  await expect(page.getByText("Possible consequences if played").first()).toBeVisible();
  await page.screenshot({ path: screenshotPath("scribe-proposals-cards-degraded.png"), fullPage: true });

  await page.getByRole("button", { name: "Adopt as Planning Direction" }).first().click();
  await page.getByLabel("Planning marker text").fill("Varos betrayed the party.");
  await page.getByRole("button", { name: "Create Planning Marker" }).click();
  await expect(page.getByText(/Confirm again/)).toBeVisible();
  await page.getByRole("button", { name: "Confirm and Adopt" }).click();
  await expect(page.getByText("Active Planning Markers")).toBeVisible();
  await page.screenshot({ path: screenshotPath("scribe-proposals-marker-active.png"), fullPage: true });

  const playerAfter = await page.evaluate(async () => fetch("/api/player-display").then((response) => response.json()));
  expect(playerAfter).toEqual(playerBefore);
  expect(playerPayloads).toHaveLength(2);
});

test("Scribe FAQ captures requested option mismatch recovery flow", async ({ page }) => {
  let proposalBuilt = false;
  let markerActive = false;
  const activeMarker = {
    id: "m-slot2",
    campaign_id: "c1",
    session_id: "s1",
    scene_id: "sc1",
    source_proposal_option_id: "opt2",
    scope_kind: "scene",
    status: "active",
    title: "Reworked Option 2: witness protocol",
    marker_text: "GM is considering a corrected social testimony route around Sera, Marek, and the clockwork seal.",
    original_marker_text: "GM is considering a magical anomaly around the clockwork seal.",
    lint_warnings: [],
    provenance: { proposalSetId: "ps-slot", proposalOptionId: "opt2", llmRunId: "run-slot", contextPackageId: "ctx-slot" },
    edited_at: "2026-05-04T00:00:00Z",
    edited_from_source: true,
    expires_at: null,
    created_at: "2026-05-04T00:00:00Z",
    updated_at: "2026-05-04T00:00:00Z"
  };
  const optionRows = () => [
    {
      id: "opt1",
      proposal_set_id: "ps-slot",
      option_index: 0,
      stable_option_key: "archive_delay",
      title: "Archive delay",
      summary: "Move pressure to a procedural delay in the archive.",
      body: "Draft-only option 1 body.",
      consequences: "The hearing pauses while records are checked.",
      reveals: "The archive clerk has a conflict.",
      stays_hidden: "Who changed the seal remains hidden.",
      proposed_delta: {},
      planning_marker_text: "GM is considering an archive delay.",
      status: "proposed",
      selected_at: null,
      canonized_at: null,
      active_planning_marker_id: null,
      created_at: "2026-05-04T00:00:00Z",
      updated_at: "2026-05-04T00:00:00Z"
    },
    {
      id: "opt2",
      proposal_set_id: "ps-slot",
      option_index: 1,
      stable_option_key: "wrong_slot",
      title: markerActive ? "Reworked Option 2: witness protocol" : "Option 2: clockwork anomaly",
      summary: markerActive
        ? "Sera forces Marek into a public witness protocol around testimony and the clockwork seal."
        : "The clockwork seal behaves strangely, but the option misses the requested social testimony focus.",
      body: "Draft-only option 2 body. It needs GM review before becoming planning context.",
      consequences: "If played, the GM decides whether to use the anomaly or rewrite it as testimony pressure.",
      reveals: "The seal's chain of custody may matter.",
      stays_hidden: "Whether Marek is lying stays hidden.",
      proposed_delta: {},
      planning_marker_text: markerActive
        ? "GM is considering a corrected social testimony route around Sera, Marek, and the clockwork seal."
        : "GM is considering a magical anomaly around the clockwork seal.",
      status: markerActive ? "selected" : "proposed",
      selected_at: markerActive ? "2026-05-04T00:00:00Z" : null,
      canonized_at: null,
      active_planning_marker_id: markerActive ? "m-slot2" : null,
      created_at: "2026-05-04T00:00:00Z",
      updated_at: "2026-05-04T00:00:00Z"
    },
    {
      id: "opt3",
      proposal_set_id: "ps-slot",
      option_index: 2,
      stable_option_key: "private_bargain",
      title: "Private bargain",
      summary: "Move the scene to a private bargain after the hearing.",
      body: "Draft-only option 3 body.",
      consequences: "The party gains leverage but owes a favor.",
      reveals: "The judge wants the case quiet.",
      stays_hidden: "The sponsor remains hidden.",
      proposed_delta: {},
      planning_marker_text: "GM is considering a private bargain after the hearing.",
      status: "proposed",
      selected_at: null,
      canonized_at: null,
      active_planning_marker_id: null,
      created_at: "2026-05-04T00:00:00Z",
      updated_at: "2026-05-04T00:00:00Z"
    }
  ];
  const proposalSetDetail = () => ({
    proposal_set: {
      id: "ps-slot",
      campaign_id: "c1",
      session_id: "s1",
      scene_id: "sc1",
      llm_run_id: "run-slot",
      context_package_id: "ctx-slot",
      task_kind: "scene.branch_directions",
      scope_kind: "scene",
      title: "Inquest branch options",
      status: "proposed",
      option_count: 3,
      selected_count: markerActive ? 1 : 0,
      active_marker_count: markerActive ? 1 : 0,
      rejected_count: 0,
      saved_count: 0,
      has_warnings: true,
      warning_count: 1,
      degraded: false,
      repair_attempted: false,
      created_at: "2026-05-04T00:00:00Z",
      updated_at: "2026-05-04T00:00:00Z"
    },
    options: optionRows(),
    planning_markers: markerActive ? [activeMarker] : [],
    run: {
      id: "run-slot",
      campaign_id: "c1",
      session_id: "s1",
      provider_profile_id: "p1",
      context_package_id: "ctx-slot",
      parent_run_id: null,
      task_kind: "scene.branch_directions",
      status: "succeeded",
      error_code: null,
      error_message: null,
      parse_failure_reason: null,
      repair_attempted: false,
      request_metadata: { payloadRetention: "metadata_only" },
      response_text: null,
      normalized_output: null,
      prompt_tokens_estimate: 100,
      duration_ms: 41,
      cancel_requested_at: null,
      created_at: "2026-05-04T00:00:00Z",
      updated_at: "2026-05-04T00:00:00Z"
    },
    context_package: null,
    normalization_warnings: [
      {
        code: "requested_slot_may_not_match",
        slot: 2,
        reason: "low_requirement_overlap",
        requirement: "Option 2 should be social testimony pressure around Sera, Marek, and the clockwork seal."
      }
    ]
  });

  await page.route("**/*", async (route) => {
    const url = route.request().url();
    if (url.endsWith("/health")) return route.fulfill(json({ status: "ok", db: "ok", schema_version: "20260504_0016", db_path: "data/db", time: "z" }));
    if (url.endsWith("/api/meta")) return route.fulfill(json({ app: "myroll", version: "dev", db_path: "data/db", schema_version: "20260504_0016", seed_version: "seed", expected_seed_version: "seed" }));
    if (url.endsWith("/api/player-display")) return route.fulfill(json(playerState));
    if (url.endsWith("/api/workspace/widgets")) return route.fulfill(json({ updated_at: "z", widgets: [{ id: "w1", scope_type: "global", scope_id: null, kind: "scribe", title: "Scribe", x: 24, y: 72, width: 900, height: 820, z_index: 10, locked: false, minimized: false, config: {}, created_at: "z", updated_at: "z" }] }));
    if (url.endsWith("/api/campaigns")) return route.fulfill(json([{ id: "c1", name: "Campaign", description: "", created_at: "z", updated_at: "z" }]));
    if (url.endsWith("/api/runtime")) return route.fulfill(json({ active_campaign_id: "c1", active_campaign_name: "Campaign", active_session_id: "s1", active_session_title: "Opening", active_scene_id: "sc1", active_scene_title: "Bridge", updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/sessions")) return route.fulfill(json([{ id: "s1", campaign_id: "c1", title: "Opening", starts_at: null, ended_at: null, created_at: "z", updated_at: "z" }]));
    if (url.endsWith("/api/campaigns/c1/scenes")) return route.fulfill(json([{ id: "sc1", campaign_id: "c1", session_id: "s1", title: "Bridge", summary: "", created_at: "z", updated_at: "z" }]));
    if (url.includes("/api/campaigns/c1/scribe/transcript-events")) return route.fulfill(json({ events: [], projection: [], updated_at: "z" }));
    if (url.endsWith("/api/llm/provider-profiles")) return route.fulfill(json({ profiles: [{ id: "p1", label: "Fixture provider", vendor: "custom", base_url: "http://127.0.0.1:9999/v1", model_id: "fixture", key_source: { type: "none", ref: null }, conformance_level: "level_2_json_validated", capabilities: {}, last_probe_result: null, probed_at: "z", created_at: "z", updated_at: "z" }], updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/scribe/memory-candidates")) return route.fulfill(json({ candidates: [], updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/scribe/aliases")) return route.fulfill(json([]));
    if (url.endsWith("/api/campaigns/c1/public-snippets")) return route.fulfill(json({ snippets: [], updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/scribe/session-recaps?session_id=s1")) return route.fulfill(json({ recaps: [], updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/scribe/memory-entries?session_id=s1")) return route.fulfill(json({ entries: [], updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/proposal-sets")) return route.fulfill(json({ proposal_sets: proposalBuilt ? [proposalSetDetail().proposal_set] : [], updated_at: "z" }));
    if (url.endsWith("/api/proposal-sets/ps-slot")) return route.fulfill(json(proposalSetDetail()));
    if (url.endsWith("/api/campaigns/c1/planning-markers")) return route.fulfill(json({ planning_markers: markerActive ? [activeMarker] : [], updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/llm/context-preview")) return route.fulfill(json({ id: "ctx-slot", campaign_id: "c1", session_id: "s1", scene_id: "sc1", task_kind: "scene.branch_directions", scope_kind: "scene", visibility_mode: "gm_private", gm_instruction: "Option 2 should be social testimony pressure around Sera, Marek, and the clockwork seal.", source_refs: [], rendered_prompt: "Rendered branch prompt.", source_ref_hash: "hash", source_classes: ["scene"], warnings: [], review_status: "unreviewed", reviewed_at: null, reviewed_by: null, token_estimate: 123, created_at: "z", updated_at: "z" }));
    if (url.endsWith("/api/llm/context-packages/ctx-slot/review")) return route.fulfill(json({ id: "ctx-slot", campaign_id: "c1", session_id: "s1", scene_id: "sc1", task_kind: "scene.branch_directions", scope_kind: "scene", visibility_mode: "gm_private", gm_instruction: "Option 2 should be social testimony pressure around Sera, Marek, and the clockwork seal.", source_refs: [], rendered_prompt: "Rendered branch prompt.", source_ref_hash: "hash", source_classes: ["scene"], warnings: [], review_status: "reviewed", reviewed_at: "z", reviewed_by: "local_gm", token_estimate: 123, created_at: "z", updated_at: "z" }));
    if (url.endsWith("/api/campaigns/c1/llm/branch-directions/build")) {
      proposalBuilt = true;
      return route.fulfill(json({ run: proposalSetDetail().run, proposal_set: proposalSetDetail(), rejected_options: [], warnings: proposalSetDetail().normalization_warnings }));
    }
    if (url.endsWith("/api/proposal-options/opt2/create-planning-marker")) {
      markerActive = true;
      return route.fulfill(json(activeMarker));
    }
    return route.continue();
  });

  await page.goto("/gm/floating");
  await page.getByPlaceholder("What kind of directions should Scribe explore?").fill(
    "Option 2 should be social testimony pressure around Sera, Marek, and the clockwork seal."
  );
  await page.getByRole("button", { name: "Preview Branch Context", exact: true }).click();
  await page.getByRole("button", { name: "Review Branch Context", exact: true }).click();
  await page.getByRole("button", { name: "Run Branch Directions", exact: true }).click();

  const firstSlotWarning = page.getByText("Requested option 2 may not match the GM instruction. Review before adopting.").first();
  await expect(firstSlotWarning).toBeVisible();
  const optionTwoCard = page.locator(".scribe-proposal-card").filter({ hasText: "Option 2: clockwork anomaly" });
  await optionTwoCard.scrollIntoViewIfNeeded();
  await expect(optionTwoCard.getByText("Requested option 2 may not match the GM instruction. Review before adopting.")).toBeVisible();
  await optionTwoCard.screenshot({ path: docScreenshotPath("requested-slot-warning-proposals.png") });

  await optionTwoCard.getByRole("button", { name: "Adopt as Planning Direction" }).click();
  await page.getByLabel("Planning marker title").fill("Reworked Option 2: witness protocol");
  await page.getByLabel("Planning marker text").fill(
    "GM is considering a corrected social testimony route around Sera, Marek, and the clockwork seal."
  );
  const adoptEditor = page.locator(".scribe-review-block").filter({ hasText: "Adopt planning marker" });
  await adoptEditor.scrollIntoViewIfNeeded();
  await adoptEditor.screenshot({ path: docScreenshotPath("requested-slot-warning-adopt-edit.png") });

  await page.getByRole("button", { name: "Create Planning Marker" }).click();
  const activePlanningBadge = page.getByText("Active planning", { exact: true });
  await activePlanningBadge.scrollIntoViewIfNeeded();
  await expect(activePlanningBadge).toBeVisible();
  await page.locator(".scribe-memory").filter({ hasText: "Active Planning Markers" }).screenshot({
    path: docScreenshotPath("requested-slot-warning-corrected-marker.png")
  });
});
