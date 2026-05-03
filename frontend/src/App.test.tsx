import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  App,
  applyWidgetPatch,
  AssetLibraryWidget,
  BackendStatusWidget,
  CombatTrackerWidget,
  MapDisplayWidget,
  NotesWidget,
  PartyTrackerWidget,
  PlayerDisplayWidget,
  SceneContextWidget,
  StorageDemoWidget,
  WidgetFrame
} from "./App";
import { MapRenderer } from "./map/MapRenderer";
import { PlayerDisplayApp, PlayerDisplaySurface } from "./player-display/PlayerDisplayApp";
import { SafeMarkdownRenderer } from "./SafeMarkdownRenderer";
import type { ReactElement } from "react";
import type {
  Asset,
  CombatEncounter,
  CustomFieldDefinition,
  EntityRecord,
  FogMask,
  MapRecord,
  MapRenderPayload,
  Note,
  PartyTrackerConfig,
  PlayerDisplayState,
  PublicSnippet,
  SceneMap,
  SceneMapToken,
  WorkspaceWidget
} from "./types";

beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    clearRect: vi.fn(),
    drawImage: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    getImageData: vi.fn(() => ({ data: new Uint8ClampedArray(120 * 80 * 4) })),
    putImageData: vi.fn(),
    fillRect: vi.fn(),
    globalCompositeOperation: "source-over"
  } as unknown as CanvasRenderingContext2D);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const widget: WorkspaceWidget = {
  id: "11111111-1111-4111-8111-111111111111",
  scope_type: "global",
  scope_id: null,
  kind: "backend_status",
  title: "Backend Status",
  x: 10,
  y: 20,
  width: 320,
  height: 220,
  z_index: 1,
  locked: false,
  minimized: false,
  config: {},
  created_at: "2026-04-27T00:00:00Z",
  updated_at: "2026-04-27T00:00:00Z"
};

const playerDisplayState: PlayerDisplayState = {
  mode: "scene_title",
  title: "Lantern Bridge",
  subtitle: "Opening Night",
  active_campaign_id: "c1",
  active_campaign_name: "Witchlight Gothic Trauma Edition",
  active_session_id: "s1",
  active_session_title: "Opening Night",
  active_scene_id: "sc1",
  active_scene_title: "Lantern Bridge",
  payload: {},
  revision: 2,
  identify_revision: 0,
  identify_until: null,
  updated_at: "2026-04-27T00:00:00Z"
};

const asset: Asset = {
  id: "33333333-3333-4333-8333-333333333333",
  campaign_id: "c1",
  kind: "handout_image",
  visibility: "public_displayable",
  name: "Storm Gate",
  mime_type: "image/png",
  byte_size: 1024,
  checksum: "abc",
  relative_path: "ab/abc.png",
  original_filename: "storm.png",
  width: 640,
  height: 360,
  duration_ms: null,
  tags: ["clue"],
  created_at: "2026-04-27T00:00:00Z",
  updated_at: "2026-04-27T00:00:00Z"
};

const mapAsset: Asset = {
  ...asset,
  id: "55555555-5555-4555-8555-555555555555",
  kind: "map_image",
  name: "Harbor Map",
  width: 320,
  height: 180
};

const mapRecord: MapRecord = {
  id: "66666666-6666-4666-8666-666666666666",
  campaign_id: "c1",
  asset_id: mapAsset.id,
  asset_name: mapAsset.name,
  asset_visibility: "public_displayable",
  asset_url: `/api/assets/${mapAsset.id}/blob`,
  name: "Harbor Map",
  width: 320,
  height: 180,
  grid_enabled: true,
  grid_size_px: 40,
  grid_offset_x: 0,
  grid_offset_y: 0,
  grid_color: "#FFFFFF",
  grid_opacity: 0.35,
  created_at: "2026-04-27T00:00:00Z",
  updated_at: "2026-04-27T00:00:00Z"
};

const sceneMap: SceneMap = {
  id: "77777777-7777-4777-8777-777777777777",
  campaign_id: "c1",
  scene_id: "sc1",
  map_id: mapRecord.id,
  is_active: false,
  player_fit_mode: "fit",
  player_grid_visible: true,
  map: mapRecord,
  created_at: "2026-04-27T00:00:00Z",
  updated_at: "2026-04-27T00:00:00Z"
};

const fogMask: FogMask = {
  id: "88888888-8888-4888-8888-888888888888",
  campaign_id: "c1",
  scene_id: "sc1",
  scene_map_id: sceneMap.id,
  enabled: true,
  revision: 1,
  width: 320,
  height: 180,
  mask_url: `/api/scene-maps/${sceneMap.id}/fog/mask?revision=1`,
  updated_at: "2026-04-27T00:00:00Z"
};

const mapToken: SceneMapToken = {
  id: "99999999-9999-4999-8999-999999999999",
  campaign_id: "c1",
  scene_id: "sc1",
  scene_map_id: sceneMap.id,
  entity_id: null,
  asset_id: null,
  asset_name: null,
  asset_visibility: null,
  asset_url: null,
  name: "Dock Guard",
  x: 80,
  y: 60,
  width: 38,
  height: 38,
  rotation: 0,
  z_index: 0,
  visibility: "player_visible",
  label_visibility: "player_visible",
  shape: "circle",
  color: "#D94841",
  border_color: "#FFFFFF",
  opacity: 1,
  status: [],
  created_at: "2026-04-27T00:00:00Z",
  updated_at: "2026-04-27T00:00:00Z"
};

const note: Note = {
  id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  campaign_id: "c1",
  source_id: "source-id",
  session_id: "s1",
  scene_id: "sc1",
  asset_id: null,
  title: "Private clue note",
  private_body: "Safe clue text.\n\nSECRET: do not show this.",
  tags: ["clue"],
  source_label: "Internal Notes",
  created_at: "2026-04-27T00:00:00Z",
  updated_at: "2026-04-27T00:00:00Z"
};

const publicSnippet: PublicSnippet = {
  id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  campaign_id: "c1",
  note_id: note.id,
  title: "Safe clue",
  body: "Safe clue text.",
  format: "markdown",
  created_at: "2026-04-27T00:00:00Z",
  updated_at: "2026-04-27T00:00:00Z"
};

const partyEntity: EntityRecord = {
  id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  campaign_id: "c1",
  kind: "pc",
  name: "Aria Vell",
  display_name: "Aria",
  visibility: "public_known",
  portrait_asset_id: asset.id,
  portrait_asset_name: asset.name,
  portrait_asset_visibility: "public_displayable",
  tags: ["private-tag"],
  notes: "PRIVATE ENTITY NOTE",
  field_values: { level: 5, hp: { current: 22, max: 31 }, secret: "PRIVATE FIELD" },
  created_at: "2026-04-27T00:00:00Z",
  updated_at: "2026-04-27T00:00:00Z"
};

const levelField: CustomFieldDefinition = {
  id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
  campaign_id: "c1",
  key: "level",
  label: "Level",
  field_type: "number",
  applies_to: ["pc"],
  required: false,
  default_value: null,
  options: [],
  public_by_default: true,
  sort_order: 1,
  created_at: "2026-04-27T00:00:00Z",
  updated_at: "2026-04-27T00:00:00Z"
};

const hpField: CustomFieldDefinition = {
  ...levelField,
  id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
  key: "hp",
  label: "HP",
  field_type: "resource",
  public_by_default: false,
  sort_order: 2
};

const partyTracker: PartyTrackerConfig = {
  id: "ffffffff-ffff-4fff-8fff-ffffffffffff",
  campaign_id: "c1",
  layout: "standard",
  members: [],
  fields: [
    {
      id: "12121212-1212-4212-8212-121212121212",
      field_definition_id: levelField.id,
      sort_order: 0,
      public_visible: true,
      field: levelField
    }
  ],
  updated_at: "2026-04-27T00:00:00Z"
};

const combatEncounter: CombatEncounter = {
  id: "abababab-abab-4aba-8aba-abababababab",
  campaign_id: "c1",
  session_id: "s1",
  scene_id: "sc1",
  title: "Deck Fight",
  status: "active",
  round: 1,
  active_combatant_id: "acacacac-acac-4aca-8aca-acacacacacac",
  combatants: [
    {
      id: "acacacac-acac-4aca-8aca-acacacacacac",
      campaign_id: "c1",
      encounter_id: "abababab-abab-4aba-8aba-abababababab",
      entity_id: partyEntity.id,
      token_id: mapToken.id,
      name: "Aria",
      disposition: "pc",
      initiative: 18,
      order_index: 0,
      armor_class: 15,
      hp_current: 22,
      hp_max: 31,
      hp_temp: 3,
      conditions: [{ label: "PRIVATE CONDITION" }],
      public_status: ["Blessed"],
      notes: "PRIVATE COMBAT NOTE",
      public_visible: true,
      is_defeated: false,
      portrait_asset_id: asset.id,
      portrait_asset_name: asset.name,
      created_at: "2026-04-27T00:00:00Z",
      updated_at: "2026-04-27T00:00:00Z"
    },
    {
      id: "adadadad-adad-4ada-8ada-adadadadadad",
      campaign_id: "c1",
      encounter_id: "abababab-abab-4aba-8aba-abababababab",
      entity_id: null,
      token_id: null,
      name: "Hidden Enemy",
      disposition: "enemy",
      initiative: 14,
      order_index: 1,
      armor_class: 13,
      hp_current: 18,
      hp_max: 18,
      hp_temp: 0,
      conditions: [],
      public_status: [],
      notes: "PRIVATE ENEMY NOTE",
      public_visible: false,
      is_defeated: false,
      portrait_asset_id: null,
      portrait_asset_name: null,
      created_at: "2026-04-27T00:00:00Z",
      updated_at: "2026-04-27T00:00:00Z"
    }
  ],
  created_at: "2026-04-27T00:00:00Z",
  updated_at: "2026-04-27T00:00:00Z"
};

function jsonResponse(body: unknown, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    statusText: ok ? "OK" : "Error",
    text: () => Promise.resolve(JSON.stringify(body))
  } as Response);
}

describe("GM shell widgets", () => {
  it("renders backend status healthy state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/health")) {
          return jsonResponse({
            status: "ok",
            db: "ok",
            schema_version: "20260504_0015",
            db_path: "data/myroll.dev.sqlite3",
            time: "2026-04-27T00:00:00Z"
          });
        }
        return jsonResponse({
          app: "myroll",
          version: "dev",
          db_path: "data/myroll.dev.sqlite3",
          schema_version: "20260504_0015",
          seed_version: "2026-04-27-v12",
          expected_seed_version: "2026-04-27-v12"
        });
      })
    );

    renderWithClient(<BackendStatusWidget />);

    expect(await screen.findByText("myroll")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("20260504_0015")).toBeInTheDocument());
  });

  it("renders backend unavailable state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("offline")))
    );

    renderWithClient(<BackendStatusWidget />);

    expect(await screen.findByText("Backend unavailable")).toBeInTheDocument();
  });

  it("renders storage status and runs backup/export actions", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/storage/backup")) {
        return jsonResponse({
          archive_name: "myroll.test.20260428T010203Z.pre-migration.sqlite3",
          byte_size: 4096,
          created_at: "2026-04-28T01:02:03Z",
          download_url: null
        });
      }
      if (url.endsWith("/api/storage/export")) {
        return jsonResponse({
          archive_name: "myroll.20260428T010203Z.export.tar.gz",
          byte_size: 8192,
          created_at: "2026-04-28T01:02:03Z",
          download_url: "/api/storage/exports/myroll.20260428T010203Z.export.tar.gz"
        });
      }
      return jsonResponse({
        profile: "demo",
        db_path: ".../myroll.dev.sqlite3",
        asset_dir: ".../assets",
        backup_dir: ".../backups",
        export_dir: ".../exports",
        db_size_bytes: 1024,
        asset_size_bytes: 2048,
        latest_backup: null,
        latest_export: null,
        schema_version: "20260504_0015",
        seed_version: "2026-04-27-v12",
        expected_seed_version: "2026-04-27-v12",
        private_demo_name_map_active: true
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const openMock = vi.fn();
    vi.stubGlobal("open", openMock);

    renderWithClient(<StorageDemoWidget />);

    expect(await screen.findByText("demo")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Backup DB" }));
    await userEvent.click(screen.getByRole("button", { name: "Export" }));
    expect(await screen.findByText(/Created export:/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Download" }));

    expect(fetchMock).toHaveBeenCalledWith("/api/storage/backup", expect.objectContaining({ method: "POST" }));
    expect(fetchMock).toHaveBeenCalledWith("/api/storage/export", expect.objectContaining({ method: "POST" }));
    expect(openMock).toHaveBeenCalledWith("/api/storage/exports/myroll.20260428T010203Z.export.tar.gz", "_blank", "noopener,noreferrer");
  });

  it("renders functional and disabled placeholder widgets", async () => {
    window.history.pushState({}, "", "/gm/floating");
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/workspace/widgets")) {
          return jsonResponse({
            updated_at: "2026-04-27T00:00:00Z",
            widgets: [
              widget,
              {
                ...widget,
                id: "22222222-2222-4222-8222-222222222222",
                kind: "notes",
                title: "Notes",
                x: 360,
                config: { placeholder: true }
              },
              {
                ...widget,
                id: "33333333-3333-4333-8333-333333333330",
                kind: "dice_roller",
                title: "Dice Roller",
                x: 720,
                config: { placeholder: true }
              }
            ]
          });
        }
        if (url.endsWith("/api/campaigns")) return jsonResponse([]);
        if (url.endsWith("/api/runtime")) {
          return jsonResponse({
            active_campaign_id: null,
            active_campaign_name: null,
            active_session_id: null,
            active_session_title: null,
            active_scene_id: null,
            active_scene_title: null,
            updated_at: "2026-04-27T00:00:00Z"
          });
        }
        if (url.endsWith("/health")) {
          return jsonResponse({ status: "ok", db: "ok", schema_version: "20260504_0015", db_path: "data/db", time: "z" });
        }
        return jsonResponse({
          app: "myroll",
          version: "dev",
          db_path: "data/db",
          schema_version: "20260504_0015",
          seed_version: "2026-04-27-v12",
          expected_seed_version: "2026-04-27-v12"
        });
      })
    );

    renderWithClient(<App />);

    expect(await screen.findByText("Backend Status")).toBeInTheDocument();
    expect(await screen.findByText("Notes")).toBeInTheDocument();
    expect(screen.getByText("Not wired yet")).toBeInTheDocument();
  });

  it("renders proposal cockpit degraded output and marker confirmation flow", async () => {
    window.history.pushState({}, "", "/gm/floating");
    let markerAttempt = 0;
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
        title: "Branch options",
        status: "proposed",
        option_count: 2,
        selected_count: 0,
        active_marker_count: 0,
        rejected_count: 0,
        saved_count: 0,
        has_warnings: true,
        warning_count: 1,
        degraded: true,
        repair_attempted: false,
        created_at: "2026-04-27T00:00:00Z",
        updated_at: "2026-04-27T00:00:00Z"
      },
      options: [
        {
          id: "opt1",
          proposal_set_id: "ps1",
          stable_option_key: "option_1",
          title: "Political debt",
          summary: "Make Varos useful but costly.",
          body: "RAW PROPOSAL BODY: draft-only future.",
          consequences: "Varos asks for a later favor.",
          reveals: "Varos has leverage.",
          stays_hidden: "The patron remains hidden.",
          proposed_delta: { possible: "debt" },
          planning_marker_text: "GM is considering developing Varos as a political creditor.",
          status: "proposed",
          selected_at: null,
          canonized_at: null,
          active_planning_marker_id: null,
          created_at: "2026-04-27T00:00:00Z",
          updated_at: "2026-04-27T00:00:00Z"
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
        request_metadata: {},
        response_text: null,
        normalized_output: null,
        prompt_tokens_estimate: 100,
        duration_ms: 42,
        cancel_requested_at: null,
        created_at: "2026-04-27T00:00:00Z",
        updated_at: "2026-04-27T00:00:00Z"
      },
      context_package: null,
      normalization_warnings: [{ code: "degraded_option_count", expected: "3-5", accepted: 2 }]
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/workspace/widgets")) return jsonResponse({ updated_at: "z", widgets: [{ ...widget, kind: "scribe", title: "Scribe" }] });
      if (url.endsWith("/api/campaigns")) return jsonResponse([{ id: "c1", name: "Campaign", description: "", created_at: "z", updated_at: "z" }]);
      if (url.endsWith("/api/runtime")) {
        return jsonResponse({
          active_campaign_id: "c1",
          active_campaign_name: "Campaign",
          active_session_id: "s1",
          active_session_title: "Opening",
          active_scene_id: "sc1",
          active_scene_title: "Bridge",
          updated_at: "z"
        });
      }
      if (url.endsWith("/api/campaigns/c1/sessions")) return jsonResponse([{ id: "s1", campaign_id: "c1", title: "Opening", starts_at: null, ended_at: null, created_at: "z", updated_at: "z" }]);
      if (url.endsWith("/api/campaigns/c1/scenes")) return jsonResponse([{ id: "sc1", campaign_id: "c1", session_id: "s1", title: "Bridge", summary: "", created_at: "z", updated_at: "z" }]);
      if (url.includes("/api/campaigns/c1/scribe/transcript-events")) return jsonResponse({ events: [], projection: [], updated_at: "z" });
      if (url.endsWith("/api/llm/provider-profiles")) {
        return jsonResponse({
          profiles: [
            {
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
            }
          ],
          updated_at: "z"
        });
      }
      if (url.endsWith("/api/campaigns/c1/scribe/memory-candidates")) return jsonResponse({ candidates: [], updated_at: "z" });
      if (url.endsWith("/api/campaigns/c1/scribe/aliases")) return jsonResponse([]);
      if (url.endsWith("/api/campaigns/c1/proposal-sets")) return jsonResponse({ proposal_sets: [], updated_at: "z" });
      if (url.endsWith("/api/proposal-sets/ps1")) return jsonResponse(proposalSet);
      if (url.endsWith("/api/campaigns/c1/planning-markers")) return jsonResponse({ planning_markers: [], updated_at: "z" });
      if (url.endsWith("/api/campaigns/c1/llm/context-preview")) {
        return jsonResponse({
          id: "ctx-branch",
          campaign_id: "c1",
          session_id: "s1",
          scene_id: "sc1",
          task_kind: "scene.branch_directions",
          scope_kind: "scene",
          visibility_mode: "gm_private",
          gm_instruction: JSON.parse(String(init?.body)).gm_instruction,
          source_refs: [{ kind: "scene", id: "sc1", sourceClass: "scene", lane: "canon", visibility: "gm_private" }],
          rendered_prompt: "Rendered branch prompt",
          source_ref_hash: "hash",
          source_classes: ["scene"],
          warnings: [],
          review_status: "unreviewed",
          reviewed_at: null,
          reviewed_by: null,
          token_estimate: 123,
          created_at: "z",
          updated_at: "z"
        });
      }
      if (url.endsWith("/api/llm/context-packages/ctx-branch/review")) return jsonResponse({ ...JSON.parse(JSON.stringify({ id: "ctx-branch" })), campaign_id: "c1", session_id: "s1", scene_id: "sc1", task_kind: "scene.branch_directions", scope_kind: "scene", visibility_mode: "gm_private", gm_instruction: "focus", source_refs: [], rendered_prompt: "Rendered branch prompt", source_ref_hash: "hash", source_classes: ["scene"], warnings: [], review_status: "reviewed", reviewed_at: "z", reviewed_by: "local_gm", token_estimate: 123, created_at: "z", updated_at: "z" });
      if (url.endsWith("/api/campaigns/c1/llm/branch-directions/build")) return jsonResponse({ run: proposalSet.run, proposal_set: proposalSet, rejected_options: [], warnings: proposalSet.normalization_warnings });
      if (url.endsWith("/api/proposal-options/opt1/create-planning-marker")) {
        markerAttempt += 1;
        if (markerAttempt === 1) return jsonResponse({ error: { code: "marker_lint_confirmation_required", message: "Needs confirmation" } }, false, 409);
        return jsonResponse({ id: "m1", campaign_id: "c1", session_id: "s1", scene_id: "sc1", source_proposal_option_id: "opt1", scope_kind: "scene", status: "active", title: "Political debt", marker_text: "Varos betrayed the party.", original_marker_text: "GM is considering developing Varos as a political creditor.", lint_warnings: ["canonish_wording"], provenance: {}, edited_at: "z", edited_from_source: true, expires_at: null, created_at: "z", updated_at: "z" });
      }
      if (url.endsWith("/health")) return jsonResponse({ status: "ok", db: "ok", schema_version: "20260504_0015", db_path: "data/db", time: "z" });
      return jsonResponse({ app: "myroll", version: "dev", db_path: "data/db", schema_version: "20260504_0015", seed_version: "seed", expected_seed_version: "seed" });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(<App />);

    expect(await screen.findByText("Proposal Cockpit")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("What kind of directions should Scribe explore?"), { target: { value: "Make Varos political." } });
    await userEvent.click(screen.getByRole("button", { name: "Preview Branch Context" }));
    expect(await screen.findByText(/scene · unreviewed/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Review Branch Context" }));
    expect(await screen.findByText(/scene · reviewed/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Run Branch Directions" }));
    expect(await screen.findByText("Degraded output: 2 options")).toBeInTheDocument();
    expect(screen.getByText("Possible consequences if played")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Adopt as Planning Direction" }));
    fireEvent.change(screen.getByLabelText("Planning marker text"), { target: { value: "Varos betrayed the party." } });
    await userEvent.click(screen.getByRole("button", { name: "Create Planning Marker" }));
    expect(await screen.findByText(/Confirm again/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Confirm and Adopt" }));

    await waitFor(() => expect(markerAttempt).toBe(2));
  });

  it("keeps local widget position when marking save as failed", () => {
    const moved = applyWidgetPatch([widget], widget.id, { x: 500, y: 600 });
    expect(moved[0].x).toBe(500);
    expect(moved[0].y).toBe(600);

    render(
      <WidgetFrame widget={moved[0]} saveStatus="error">
        <div>Body</div>
      </WidgetFrame>
    );

    expect(screen.getByText("Unsaved")).toBeInTheDocument();
  });

  it("renders runtime labels from returned runtime state", async () => {
    window.history.pushState({}, "", "/gm/floating");
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/workspace/widgets")) {
          return jsonResponse({
            updated_at: "2026-04-27T00:00:00Z",
            widgets: [{ ...widget, kind: "runtime", title: "Runtime" }]
          });
        }
        if (url.endsWith("/api/campaigns")) return jsonResponse([]);
        if (url.endsWith("/api/runtime")) {
          return jsonResponse({
            active_campaign_id: "c1",
            active_campaign_name: "Witchlight Gothic Trauma Edition",
            active_session_id: "s1",
            active_session_title: "Opening Night",
            active_scene_id: "sc1",
            active_scene_title: "Lantern Bridge",
            updated_at: "2026-04-27T00:00:00Z"
          });
        }
        return jsonResponse([]);
      })
    );

    renderWithClient(<App />);

    await waitFor(() => {
      expect(screen.getByText("Witchlight Gothic Trauma Edition")).toBeInTheDocument();
      expect(screen.getByText("Lantern Bridge")).toBeInTheDocument();
    });
  });

  it("stages scene context privately and publishes only through explicit action", async () => {
    const sceneContextResponse = {
      scene: {
        id: "sc1",
        campaign_id: "c1",
        session_id: "s1",
        title: "Lantern Bridge",
        summary: "A tense crossing",
        created_at: "2026-04-27T00:00:00Z",
        updated_at: "2026-04-27T00:00:00Z"
      },
      context: {
        id: "context-id",
        campaign_id: "c1",
        scene_id: "sc1",
        active_encounter_id: combatEncounter.id,
        staged_display_mode: "public_snippet",
        staged_public_snippet_id: publicSnippet.id,
        created_at: "2026-04-27T00:00:00Z",
        updated_at: "2026-04-27T00:00:00Z"
      },
      active_map: { ...sceneMap, is_active: true },
      notes: [note],
      public_snippets: [
        {
          id: "scene-snippet-link",
          campaign_id: "c1",
          scene_id: "sc1",
          public_snippet_id: publicSnippet.id,
          sort_order: 0,
          snippet: publicSnippet,
          created_at: "2026-04-27T00:00:00Z",
          updated_at: "2026-04-27T00:00:00Z"
        }
      ],
      entities: [
        {
          id: "scene-entity-link",
          campaign_id: "c1",
          scene_id: "sc1",
          entity_id: partyEntity.id,
          role: "featured",
          sort_order: 0,
          notes: "GM-only link note",
          entity: partyEntity,
          created_at: "2026-04-27T00:00:00Z",
          updated_at: "2026-04-27T00:00:00Z"
        }
      ],
      active_encounter: combatEncounter,
      updated_at: "2026-04-27T00:00:00Z"
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/scenes/sc1/context")) return jsonResponse(sceneContextResponse);
      if (url.endsWith("/api/campaigns/c1/entities")) return jsonResponse({ entities: [partyEntity], updated_at: partyEntity.updated_at });
      if (url.endsWith("/api/campaigns/c1/public-snippets")) return jsonResponse({ snippets: [publicSnippet], updated_at: publicSnippet.updated_at });
      if (url.endsWith("/api/campaigns/c1/combat-encounters")) return jsonResponse({ encounters: [combatEncounter], updated_at: combatEncounter.updated_at });
      if (url.endsWith("/api/runtime/activate-scene")) {
        return jsonResponse({
          active_campaign_id: "c1",
          active_campaign_name: "Witchlight",
          active_session_id: "s1",
          active_session_title: "Opening Night",
          active_scene_id: "sc1",
          active_scene_title: "Lantern Bridge",
          updated_at: "2026-04-27T00:00:00Z"
        });
      }
      if (url.endsWith("/api/scenes/sc1/publish-staged-display")) {
        return jsonResponse({ ...playerDisplayState, mode: "text", title: publicSnippet.title, payload: { type: "public_snippet", body: publicSnippet.body } });
      }
      return jsonResponse(sceneContextResponse);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(
      <SceneContextWidget
        campaigns={[]}
        sessions={[{ id: "s1", campaign_id: "c1", title: "Opening Night", starts_at: null, ended_at: null, created_at: "z", updated_at: "z" }]}
        scenes={[sceneContextResponse.scene]}
        runtime={{ ...playerDisplayState, updated_at: "z" }}
        selectedCampaign={null}
        selectedCampaignId="c1"
        selectedSessionId="s1"
        selectedSceneId="sc1"
        setSelectedCampaignId={() => undefined}
        setSelectedSessionId={() => undefined}
        setSelectedSceneId={() => undefined}
      />
    );

    expect((await screen.findAllByText("Lantern Bridge")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Private clue note")).toBeInTheDocument();
    expect(screen.getByText("Harbor Map")).toBeInTheDocument();
    expect(screen.getAllByText("Safe clue").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: /Activate privately/ }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/runtime/activate-scene", expect.objectContaining({ method: "POST" })));
    expect(fetchMock).not.toHaveBeenCalledWith(expect.stringContaining("/api/player-display/show"), expect.any(Object));

    fireEvent.click(screen.getByRole("button", { name: "Save staging" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/scenes/sc1/context",
        expect.objectContaining({ method: "PATCH", body: expect.stringContaining("\"staged_display_mode\":\"public_snippet\"") })
      )
    );

    fireEvent.click(screen.getByRole("button", { name: /Publish staged display/ }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith("/api/scenes/sc1/publish-staged-display", expect.objectContaining({ method: "POST" }))
    );
  });

  it("calls player display commands from the GM widget", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/player-display/intermission")) {
        return jsonResponse({ ...playerDisplayState, mode: "intermission", title: "Intermission", revision: 3 });
      }
      return jsonResponse(playerDisplayState);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(<PlayerDisplayWidget />);

    expect(await screen.findByText("scene_title")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Intermission" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/player-display/intermission",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("uploads assets and sends public images from the asset widget", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/campaigns/c1/assets/upload-batch")) {
        expect(init?.body).toBeInstanceOf(FormData);
        expect(init?.headers).toBeUndefined();
        return jsonResponse({ results: [{ filename: "storm.png", asset, map: null, error: null }] }, true, 201);
      }
      if (url.endsWith("/api/campaigns/c1/assets")) return jsonResponse([asset]);
      if (url.endsWith("/api/player-display/show-image")) {
        return jsonResponse({
          ...playerDisplayState,
          mode: "image",
          title: asset.name,
          payload: {
            type: "image",
            asset_id: asset.id,
            asset_url: `/api/player-display/assets/${asset.id}/blob`,
            fit_mode: "fit"
          },
          revision: 5
        });
      }
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(
      <AssetLibraryWidget
        campaigns={[]}
        sessions={[]}
        scenes={[]}
        selectedCampaign={null}
        selectedCampaignId="c1"
        selectedSessionId={null}
        selectedSceneId={null}
        setSelectedCampaignId={() => undefined}
        setSelectedSessionId={() => undefined}
        setSelectedSceneId={() => undefined}
      />
    );

    expect(await screen.findByText("Storm Gate")).toBeInTheDocument();
    expect(screen.queryByLabelText("Auto-create maps")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Asset kind"), { target: { value: "map_image" } });
    const autoCreateMaps = screen.getByLabelText("Auto-create maps") as HTMLInputElement;
    expect(autoCreateMaps.checked).toBe(false);
    fireEvent.click(autoCreateMaps);
    fireEvent.change(screen.getByLabelText("Asset files"), {
      target: { files: [new File(["fake"], "storm.png", { type: "image/png" })] }
    });
    fireEvent.click(screen.getByRole("button", { name: /Upload/ }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/campaigns/c1/assets/upload-batch", expect.any(Object)));
    expect(await screen.findByText("storm.png")).toBeInTheDocument();
    const uploadBody = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/api/campaigns/c1/assets/upload-batch"))?.[1]?.body as FormData;
    expect(uploadBody.get("kind")).toBe("map_image");
    expect(uploadBody.get("auto_create_maps")).toBe("true");

    fireEvent.click(screen.getByRole("button", { name: /Send to player/ }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/player-display/show-image",
        expect.objectContaining({ method: "POST" })
      )
    );
  });

  it("copies selected note text into an independent public snippet and publishes it", async () => {
    const createdSnippet = { ...publicSnippet, id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc" };
    let snippetCreated = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/campaigns/c1/notes")) {
        if (init?.method === "POST") return jsonResponse(note, true, 201);
        return jsonResponse({ notes: [note], updated_at: note.updated_at });
      }
      if (url.endsWith(`/api/notes/${note.id}`)) {
        if (init?.method === "PATCH") return jsonResponse({ ...note, private_body: "Changed private text" });
        return jsonResponse(note);
      }
      if (url.endsWith("/api/campaigns/c1/notes/import-upload")) return jsonResponse(note, true, 201);
      if (url.endsWith("/api/campaigns/c1/public-snippets")) {
        if (init?.method === "POST") {
          snippetCreated = true;
          return jsonResponse(createdSnippet, true, 201);
        }
        return jsonResponse({ snippets: snippetCreated ? [createdSnippet, publicSnippet] : [publicSnippet], updated_at: publicSnippet.updated_at });
      }
      if (url.endsWith(`/api/public-snippets/${publicSnippet.id}`)) return jsonResponse(publicSnippet);
      if (url.endsWith("/api/campaigns/c1/assets")) return jsonResponse([]);
      if (url.endsWith("/api/player-display/show-snippet")) {
        return jsonResponse({
          ...playerDisplayState,
          mode: "text",
          title: createdSnippet.title,
          payload: {
            type: "public_snippet",
            snippet_id: createdSnippet.id,
            title: createdSnippet.title,
            body: createdSnippet.body,
            format: "markdown"
          },
          revision: 12
        });
      }
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(
      <NotesWidget
        campaigns={[]}
        sessions={[{ id: "s1", campaign_id: "c1", title: "Session", starts_at: null, ended_at: null, created_at: note.created_at, updated_at: note.updated_at }]}
        scenes={[{ id: "sc1", campaign_id: "c1", session_id: "s1", title: "Scene", summary: null, created_at: note.created_at, updated_at: note.updated_at }]}
        selectedCampaign={null}
        selectedCampaignId="c1"
        selectedSessionId="s1"
        selectedSceneId="sc1"
        setSelectedCampaignId={() => undefined}
        setSelectedSessionId={() => undefined}
        setSelectedSceneId={() => undefined}
      />
    );

    const noteBody = (await screen.findByLabelText("Private note body")) as HTMLTextAreaElement;
    await waitFor(() => expect(noteBody.value).toContain("SECRET: do not show this."));
    noteBody.setSelectionRange(0, "Safe clue text.".length);
    fireEvent.select(noteBody);
    fireEvent.click(screen.getByRole("button", { name: "Copy selection to snippet" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/campaigns/c1/public-snippets",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ note_id: note.id, title: publicSnippet.title, body: "Safe clue text.", format: "markdown" })
        })
      )
    );
    fireEvent.change(noteBody, { target: { value: "Changed private text" } });
    fireEvent.click(screen.getByRole("button", { name: "Save note" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(`/api/notes/${note.id}`, expect.objectContaining({ method: "PATCH" })));
    fireEvent.click(screen.getByRole("button", { name: /Publish/ }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/player-display/show-snippet",
        expect.objectContaining({ method: "POST", body: JSON.stringify({ snippet_id: createdSnippet.id }) })
      )
    );
  });

  it("manages party entities, fields, roster, and publishes party projection", async () => {
    const updatedParty: PartyTrackerConfig = {
      ...partyTracker,
      members: [{ id: "member-id", entity_id: partyEntity.id, sort_order: 0, entity: partyEntity }],
      fields: [
        { id: "party-level", field_definition_id: levelField.id, sort_order: 0, public_visible: true, field: levelField },
        { id: "party-hp", field_definition_id: hpField.id, sort_order: 1, public_visible: true, field: hpField }
      ]
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/campaigns/c1/entities")) {
        if (init?.method === "POST") return jsonResponse({ ...partyEntity, id: "new-entity", name: "New PC" }, true, 201);
        return jsonResponse({ entities: [partyEntity], updated_at: partyEntity.updated_at });
      }
      if (url.endsWith(`/api/entities/${partyEntity.id}`)) {
        if (url.endsWith("/field-values")) return jsonResponse({ ...partyEntity, field_values: { ...partyEntity.field_values, hp: { current: 19, max: 31 } } });
        return jsonResponse({ ...partyEntity, notes: "Edited private note" });
      }
      if (url.endsWith(`/api/entities/${partyEntity.id}/field-values`)) {
        return jsonResponse({ ...partyEntity, field_values: { ...partyEntity.field_values, hp: { current: 19, max: 31 } } });
      }
      if (url.endsWith("/api/campaigns/c1/custom-fields")) {
        if (init?.method === "POST") return jsonResponse({ ...hpField, id: "new-field", key: "morale", label: "Morale", field_type: "select" }, true, 201);
        return jsonResponse({ fields: [levelField, hpField], updated_at: hpField.updated_at });
      }
      if (url.endsWith(`/api/custom-fields/${levelField.id}`)) {
        return jsonResponse({ ...levelField, label: "Character Level" });
      }
      if (url.endsWith("/api/campaigns/c1/party-tracker")) {
        if (init?.method === "PATCH") return jsonResponse(updatedParty);
        return jsonResponse(partyTracker);
      }
      if (url.endsWith("/api/campaigns/c1/assets")) return jsonResponse([asset]);
      if (url.endsWith("/api/player-display/show-party")) {
        return jsonResponse({
          ...playerDisplayState,
          mode: "party",
          title: "Party",
          payload: {
            type: "party",
            campaign_id: "c1",
            layout: "standard",
            cards: [
              {
                entity_id: partyEntity.id,
                display_name: "Aria",
                kind: "pc",
                portrait_asset_id: asset.id,
                portrait_url: `/api/player-display/assets/${asset.id}/blob`,
                fields: [
                  { key: "level", label: "Level", type: "number", value: 5 },
                  { key: "hp", label: "HP", type: "resource", value: { current: 22, max: 31 } }
                ]
              }
            ]
          },
          revision: 14
        });
      }
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderWithClient(
      <PartyTrackerWidget
        campaigns={[]}
        sessions={[]}
        scenes={[]}
        selectedCampaign={null}
        selectedCampaignId="c1"
        selectedSessionId={null}
        selectedSceneId={null}
        setSelectedCampaignId={() => undefined}
        setSelectedSessionId={() => undefined}
        setSelectedSceneId={() => undefined}
      />
    );

    expect(await screen.findByText("Aria Vell · pc")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save entity" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        `/api/entities/${partyEntity.id}`,
        expect.objectContaining({ method: "PATCH" })
      )
    );

    await user.clear(screen.getByPlaceholderText("current/max"));
    await user.type(screen.getByPlaceholderText("current/max"), "19/31");
    await user.click(screen.getByRole("button", { name: "Save values" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        `/api/entities/${partyEntity.id}/field-values`,
        expect.objectContaining({ method: "PATCH", body: expect.stringContaining("\"hp\":{\"current\":19,\"max\":31}") })
      )
    );

    await user.click(screen.getByRole("button", { name: "Clear field form" }));
    await waitFor(() => expect(screen.getByLabelText("Custom field key")).not.toBeDisabled());
    await user.type(screen.getByLabelText("Custom field key"), "morale");
    await user.type(screen.getByLabelText("Custom field label"), "Morale");
    await user.selectOptions(screen.getByLabelText("Custom field type"), "select");
    await user.type(screen.getByLabelText("Custom field options"), "steady, shaken");
    await user.click(screen.getByRole("button", { name: /New field/ }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/campaigns/c1/custom-fields",
        expect.objectContaining({ method: "POST", body: expect.stringContaining("\"key\":\"morale\"") })
      )
    );

    await user.click(screen.getByRole("button", { name: "Add selected PC" }));
    const hpPublicToggle = screen.getAllByText("Public")[1].closest("label")!.querySelector("input")!;
    await user.click(hpPublicToggle);
    await user.click(screen.getByRole("button", { name: "Save party" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/campaigns/c1/party-tracker",
        expect.objectContaining({ method: "PATCH", body: expect.stringContaining(`"member_ids":["${partyEntity.id}"]`) })
      )
    );
    await user.click(screen.getByRole("button", { name: /Publish party/ }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/player-display/show-party",
        expect.objectContaining({ method: "POST", body: JSON.stringify({ campaign_id: "c1" }) })
      )
    );
  });

  it("manages combat encounters, combatants, turns, and publishes initiative", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/campaigns/c1/combat-encounters")) {
        if (init?.method === "POST") return jsonResponse({ ...combatEncounter, id: "new-encounter", title: "New Fight" }, true, 201);
        return jsonResponse({ encounters: [combatEncounter], updated_at: combatEncounter.updated_at });
      }
      if (url.endsWith(`/api/combat-encounters/${combatEncounter.id}`)) {
        return jsonResponse({ ...combatEncounter, status: "paused" });
      }
      if (url.endsWith(`/api/combat-encounters/${combatEncounter.id}/combatants`)) {
        return jsonResponse(
          {
            ...combatEncounter,
            combatants: [...combatEncounter.combatants, { ...combatEncounter.combatants[0], id: "new-combatant", name: "New Enemy" }]
          },
          true,
          201
        );
      }
      if (url.endsWith(`/api/combatants/${combatEncounter.combatants[0].id}`)) {
        return jsonResponse({ ...combatEncounter, combatants: [{ ...combatEncounter.combatants[0], hp_current: 9 }] });
      }
      if (url.endsWith(`/api/combatants/${combatEncounter.combatants[1].id}`)) {
        return jsonResponse({ deleted_combatant_id: combatEncounter.combatants[1].id, encounter: combatEncounter });
      }
      if (url.endsWith(`/api/combat-encounters/${combatEncounter.id}/reorder`)) {
        return jsonResponse({ ...combatEncounter, combatants: [...combatEncounter.combatants].reverse() });
      }
      if (url.endsWith(`/api/combat-encounters/${combatEncounter.id}/next-turn`)) {
        return jsonResponse({ ...combatEncounter, active_combatant_id: combatEncounter.combatants[1].id, round: 2 });
      }
      if (url.endsWith(`/api/combat-encounters/${combatEncounter.id}/previous-turn`)) {
        return jsonResponse(combatEncounter);
      }
      if (url.endsWith("/api/campaigns/c1/entities")) return jsonResponse({ entities: [partyEntity], updated_at: partyEntity.updated_at });
      if (url.endsWith("/api/campaigns/c1/scenes/sc1/maps")) return jsonResponse([sceneMap]);
      if (url.endsWith(`/api/scene-maps/${sceneMap.id}/tokens`)) return jsonResponse({ tokens: [mapToken], updated_at: mapToken.updated_at });
      if (url.endsWith("/api/player-display/show-initiative")) {
        return jsonResponse({
          ...playerDisplayState,
          mode: "initiative",
          title: "Initiative",
          subtitle: combatEncounter.title,
          payload: {
            type: "initiative",
            encounter_id: combatEncounter.id,
            round: 1,
            active_combatant_id: combatEncounter.combatants[0].id,
            combatants: [
              {
                id: combatEncounter.combatants[0].id,
                name: "Aria",
                disposition: "pc",
                initiative: 18,
                is_active: true,
                portrait_asset_id: asset.id,
                portrait_url: `/api/player-display/assets/${asset.id}/blob`,
                public_status: ["Blessed"]
              }
            ]
          },
          revision: 18
        });
      }
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderWithClient(
      <CombatTrackerWidget
        campaigns={[]}
        sessions={[{ id: "s1", campaign_id: "c1", title: "Session", starts_at: null, ended_at: null, created_at: note.created_at, updated_at: note.updated_at }]}
        scenes={[{ id: "sc1", campaign_id: "c1", session_id: "s1", title: "Scene", summary: null, created_at: note.created_at, updated_at: note.updated_at }]}
        selectedCampaign={null}
        selectedCampaignId="c1"
        selectedSessionId="s1"
        selectedSceneId="sc1"
        setSelectedCampaignId={() => undefined}
        setSelectedSessionId={() => undefined}
        setSelectedSceneId={() => undefined}
      />
    );

    expect(await screen.findByText("Deck Fight · round 1")).toBeInTheDocument();
    await user.clear(screen.getByLabelText("Combatant HP current"));
    await user.type(screen.getByLabelText("Combatant HP current"), "9");
    await user.click(screen.getByRole("button", { name: "Save combatant" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        `/api/combatants/${combatEncounter.combatants[0].id}`,
        expect.objectContaining({ method: "PATCH", body: expect.stringContaining("\"hp_current\":9") })
      )
    );
    await user.click(screen.getByRole("button", { name: "Next turn" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(`/api/combat-encounters/${combatEncounter.id}/next-turn`, expect.objectContaining({ method: "POST" })));
    await user.click(screen.getByRole("button", { name: /Publish initiative/ }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/player-display/show-initiative",
        expect.objectContaining({ method: "POST", body: JSON.stringify({ encounter_id: combatEncounter.id }) })
      )
    );
  });

  it("uses map endpoints from the map display widget", async () => {
    const bundledMapRecord: MapRecord = {
      ...mapRecord,
      id: "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
      asset_id: "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff",
      asset_name: "Crystal Cave",
      name: "Crystal Cave",
      grid_size_px: 32,
      grid_offset_x: 3,
      grid_offset_y: 4
    };
    const bundledAsset: Asset = {
      ...mapAsset,
      id: bundledMapRecord.asset_id,
      name: "Crystal Cave"
    };
    let bundledAdded = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/bundled-asset-packs")) {
        return jsonResponse([
          {
            id: "fixture-pack",
            title: "Fixture Battle Maps",
            asset_count: 1,
            category_count: 1,
            collections: ["Caves"]
          }
        ]);
      }
      if (url.endsWith("/api/bundled-asset-packs/fixture-pack/maps")) {
        return jsonResponse([
          {
            id: "crystal-cave",
            pack_id: "fixture-pack",
            title: "Crystal Cave",
            collection: "Caves",
            group: "ruins",
            category_key: "ruins_entry",
            category_label: "Ruins Entry",
            width: 320,
            height: 180,
            tags: ["cave", "crystal"],
            grid: { cols: 10, rows: 6, feet_per_cell: 5, px_per_cell: 32, offset_x: 3, offset_y: 4 }
          }
        ]);
      }
      if (url.endsWith("/api/campaigns/c1/bundled-maps")) {
        bundledAdded = true;
        return jsonResponse({ asset: bundledAsset, map: bundledMapRecord, created_asset: true, created_map: true }, true, 201);
      }
      if (url.endsWith("/api/campaigns/c1/assets")) return jsonResponse([mapAsset, asset]);
      if (url.endsWith("/api/campaigns/c1/maps")) {
        if (init?.method === "POST") return jsonResponse(mapRecord, true, 201);
        return jsonResponse(bundledAdded ? [bundledMapRecord, mapRecord] : [mapRecord]);
      }
      if (url.endsWith("/api/campaigns/c1/scenes/sc1/maps")) {
        if (init?.method === "POST") return jsonResponse({ ...sceneMap, is_active: true }, true, 201);
        return jsonResponse([sceneMap]);
      }
      if (url.endsWith(`/api/scene-maps/${sceneMap.id}/activate`)) {
        return jsonResponse({ ...sceneMap, is_active: true });
      }
      if (url.endsWith(`/api/scene-maps/${sceneMap.id}/fog`)) {
        return jsonResponse(fogMask);
      }
      if (url.endsWith(`/api/scene-maps/${sceneMap.id}/fog/enable`)) {
        return jsonResponse(fogMask);
      }
      if (url.endsWith(`/api/scene-maps/${sceneMap.id}/fog/operations`)) {
        return jsonResponse({ fog: { ...fogMask, revision: 2 }, player_display: null });
      }
      if (url.endsWith(`/api/scene-maps/${sceneMap.id}/tokens`)) {
        if (init?.method === "POST") return jsonResponse({ token: mapToken, player_display: null }, true, 201);
        return jsonResponse({ tokens: [mapToken], updated_at: "2026-04-27T00:00:00Z" });
      }
      if (url.endsWith(`/api/tokens/${mapToken.id}`)) {
        if (init?.method === "DELETE") return jsonResponse({ deleted_token_id: mapToken.id, player_display: null });
        return jsonResponse({ token: { ...mapToken, rotation: 45 }, player_display: null });
      }
      if (url.endsWith(`/api/maps/${mapRecord.id}/grid`)) {
        return jsonResponse({ ...mapRecord, grid_color: "#AABBCC" });
      }
      if (url.endsWith(`/api/maps/${bundledMapRecord.id}/grid`)) {
        return jsonResponse({ ...bundledMapRecord, grid_size_px: 37, grid_offset_x: 13, grid_offset_y: 5, grid_color: "#AABBCC" });
      }
      if (url.endsWith(`/api/scene-maps/${sceneMap.id}`)) {
        return jsonResponse({ ...sceneMap, player_fit_mode: "fill", player_grid_visible: false });
      }
      if (url.endsWith("/api/player-display/show-map")) {
        return jsonResponse({
          ...playerDisplayState,
          mode: "map",
          title: mapRecord.name,
          payload: {
            type: "map",
            scene_map_id: sceneMap.id,
            map_id: mapRecord.id,
            asset_id: mapAsset.id,
            asset_url: `/api/player-display/assets/${mapAsset.id}/blob`,
            width: 320,
            height: 180,
            title: "Harbor Map",
            fit_mode: "fit",
            grid: { type: "square", visible: true, size_px: 40, offset_x: 0, offset_y: 0, color: "#FFFFFF", opacity: 0.35 }
          },
          revision: 9
        });
      }
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(
      <MapDisplayWidget
        campaigns={[]}
        sessions={[]}
        scenes={[
          {
            id: "sc1",
            campaign_id: "c1",
            session_id: null,
            title: "Harbor Scene",
            summary: null,
            created_at: "2026-04-27T00:00:00Z",
            updated_at: "2026-04-27T00:00:00Z"
          }
        ]}
        selectedCampaign={null}
        selectedCampaignId="c1"
        selectedSessionId={null}
        selectedSceneId="sc1"
        setSelectedCampaignId={() => undefined}
        setSelectedSessionId={() => undefined}
        setSelectedSceneId={() => undefined}
      />
    );

    expect(await screen.findAllByText("Harbor Map")).not.toHaveLength(0);
    expect(await screen.findByText("Fixture Battle Maps")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Bundled map search"), { target: { value: "crystal" } });
    fireEvent.click(screen.getByRole("button", { name: /Add to campaign/ }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/campaigns/c1/bundled-maps",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ pack_id: "fixture-pack", asset_id: "crystal-cave" })
        })
      )
    );
    await waitFor(() => expect((screen.getByLabelText("Grid size") as HTMLInputElement).value).toBe("32"));
    fireEvent.click(screen.getByRole("button", { name: "Increase grid size by 5" }));
    fireEvent.click(screen.getByRole("button", { name: "Nudge grid right 10px" }));
    fireEvent.click(screen.getByRole("button", { name: "Nudge grid down 1px" }));
    expect((screen.getByLabelText("Grid size") as HTMLInputElement).value).toBe("37");
    expect((screen.getByLabelText("Grid offset X") as HTMLInputElement).value).toBe("13");
    expect((screen.getByLabelText("Grid offset Y") as HTMLInputElement).value).toBe("5");
    fireEvent.change(screen.getByLabelText("Grid color"), { target: { value: "#abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Save grid" }));
    fireEvent.click(screen.getByRole("button", { name: "Create map" }));
    fireEvent.click(screen.getByRole("button", { name: "Assign active" }));
    fireEvent.click(screen.getByRole("button", { name: "Activate scene map" }));
    fireEvent.change(screen.getByLabelText("Map fit mode"), { target: { value: "fill" } });
    fireEvent.click(screen.getByRole("button", { name: "Save player" }));
    fireEvent.click(screen.getByRole("button", { name: /Enable hidden fog/ }));
    fireEvent.click(screen.getByRole("button", { name: /Reveal all/ }));
    fireEvent.click(screen.getByRole("button", { name: /Create center/ }));
    fireEvent.change(screen.getByLabelText("Token rotation"), { target: { value: "45" } });
    fireEvent.click(screen.getByRole("button", { name: "Save token" }));
    fireEvent.click(screen.getByRole("button", { name: /Send map/ }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/player-display/show-map",
        expect.objectContaining({ method: "POST", body: JSON.stringify({ scene_map_id: sceneMap.id }) })
      )
    );
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/maps/${bundledMapRecord.id}/grid`,
      expect.objectContaining({
        method: "PATCH",
        body: expect.stringContaining("\"grid_size_px\":37")
      })
    );
    const gridBody = fetchMock.mock.calls.find(([url]) => String(url).endsWith(`/api/maps/${bundledMapRecord.id}/grid`))?.[1]?.body as string;
    expect(gridBody).toContain("\"grid_offset_x\":13");
    expect(gridBody).toContain("\"grid_offset_y\":5");
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/scene-maps/${sceneMap.id}/fog/operations`,
      expect.objectContaining({ method: "POST", body: JSON.stringify({ operations: [{ type: "reveal_all" }] }) })
    );
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/scene-maps/${sceneMap.id}/tokens`,
      expect.objectContaining({ method: "POST" })
    );
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/tokens/${mapToken.id}`,
      expect.objectContaining({ method: "PATCH", body: expect.stringContaining("\"rotation\":45") })
    );
  });

  it("renders shared map renderer grid and unavailable state", () => {
    const payload: MapRenderPayload = {
      type: "map",
      scene_map_id: sceneMap.id,
      map_id: mapRecord.id,
      asset_id: mapAsset.id,
      asset_url: `/api/player-display/assets/${mapAsset.id}/blob`,
      width: 120,
      height: 80,
      title: "Harbor Map",
      fit_mode: "fit",
      grid: { type: "square", visible: true, size_px: 40, offset_x: 0, offset_y: 0, color: "#FFFFFF", opacity: 0.35 }
    };
    const { container } = render(<MapRenderer payload={payload} />);

    const image = screen.getByAltText("Harbor Map");
    expect(image).toHaveAttribute("src", `/api/player-display/assets/${mapAsset.id}/blob`);
    expect(container.querySelectorAll("line").length).toBeGreaterThan(0);
    fireEvent.error(image);
    expect(screen.getByText("Map unavailable")).toBeInTheDocument();
  });

  it("renders shared map renderer token layer and portrait fallback", () => {
    const payload: MapRenderPayload = {
      type: "map",
      scene_map_id: sceneMap.id,
      map_id: mapRecord.id,
      asset_id: mapAsset.id,
      asset_url: `/api/player-display/assets/${mapAsset.id}/blob`,
      width: 120,
      height: 80,
      title: "Harbor Map",
      fit_mode: "fit",
      grid: { type: "square", visible: false, size_px: 40, offset_x: 0, offset_y: 0, color: "#FFFFFF", opacity: 0.35 },
      tokens: [
        {
          id: "token-public",
          entity_id: null,
          asset_id: null,
          asset_url: null,
          name: null,
          x: 30,
          y: 20,
          width: 20,
          height: 20,
          rotation: 0,
          style: { shape: "circle", color: "#D94841", border_color: "#FFFFFF", opacity: 1 },
          status: []
        },
        {
          id: "token-portrait",
          entity_id: null,
          asset_id: asset.id,
          asset_url: `/api/player-display/assets/${asset.id}/blob`,
          name: "Captain",
          x: 80,
          y: 40,
          width: 26,
          height: 26,
          rotation: 0,
          style: { shape: "portrait", color: "#335577", border_color: "#FFFFFF", opacity: 1 },
          status: []
        }
      ]
    };
    const { container } = render(<MapRenderer payload={payload} />);

    expect(screen.getByText("Captain")).toBeInTheDocument();
    const portrait = screen.getByAltText("Captain");
    expect(container.querySelector(".shape-portrait .map-token-portrait-frame")).toBeInTheDocument();
    fireEvent.error(portrait);
    expect(screen.queryByAltText("Captain")).not.toBeInTheDocument();
    expect(screen.getByText("Captain")).toBeInTheDocument();
  });

  it("renders shared map renderer with fog canvas in GM and player modes", () => {
    const payload: MapRenderPayload = {
      type: "map",
      scene_map_id: sceneMap.id,
      map_id: mapRecord.id,
      asset_id: mapAsset.id,
      asset_url: `/api/player-display/assets/${mapAsset.id}/blob`,
      width: 120,
      height: 80,
      title: "Harbor Map",
      fit_mode: "fit",
      grid: { type: "square", visible: true, size_px: 40, offset_x: 0, offset_y: 0, color: "#FFFFFF", opacity: 0.35 },
      fog: {
        enabled: true,
        mask_id: fogMask.id,
        mask_url: `/api/player-display/fog/${fogMask.id}/mask?revision=1`,
        revision: 1,
        width: 120,
        height: 80
      }
    };
    const { container, rerender } = render(<MapRenderer payload={payload} renderMode="gm" />);

    expect(container.querySelector(".render-gm canvas")).toBeInTheDocument();
    expect(container.querySelector(".render-gm")?.getAttribute("style")).toContain("aspect-ratio: 120 / 80");
    expect(container.querySelectorAll("line").length).toBeGreaterThan(0);

    rerender(<MapRenderer payload={payload} renderMode="player" />);
    expect(container.querySelector(".render-player canvas")).toBeInTheDocument();
    expect(container.querySelector(".render-player")?.getAttribute("style") ?? "").not.toContain("aspect-ratio");
  });

  it("renders player display scene title and reconnecting overlay from last known state", () => {
    render(<PlayerDisplaySurface state={playerDisplayState} now={Date.parse("2026-04-27T00:00:00Z")} reconnecting />);

    expect(screen.getByText("Lantern Bridge")).toBeInTheDocument();
    expect(screen.getByText("Opening Night")).toBeInTheDocument();
    expect(screen.getByText("Reconnecting")).toBeInTheDocument();
  });

  it("suppresses reconnecting overlay during blackout", () => {
    render(<PlayerDisplaySurface state={{ ...playerDisplayState, mode: "blackout" }} now={Date.now()} reconnecting />);

    expect(screen.queryByText("Reconnecting")).not.toBeInTheDocument();
    expect(screen.queryByText("Lantern Bridge")).not.toBeInTheDocument();
  });

  it("renders player display image mode and image unavailable state", () => {
    const state: PlayerDisplayState = {
      ...playerDisplayState,
      mode: "image",
      title: "Storm Gate",
      payload: {
        type: "image",
        asset_id: asset.id,
        asset_url: `/api/player-display/assets/${asset.id}/blob`,
        title: "Storm Gate",
        caption: "Visible clue",
        fit_mode: "fit",
        width: 640,
        height: 360
      },
      revision: 8
    };

    render(<PlayerDisplaySurface state={state} now={Date.now()} reconnecting />);

    const image = screen.getByAltText("Storm Gate");
    expect(image).toHaveAttribute("src", `/api/player-display/assets/${asset.id}/blob`);
    expect(screen.getByText("Visible clue")).toBeInTheDocument();
    fireEvent.error(image);
    expect(screen.getByText("Image unavailable")).toBeInTheDocument();
  });

  it("renders player display map mode and map unavailable state", () => {
    const state: PlayerDisplayState = {
      ...playerDisplayState,
      mode: "map",
      title: "Harbor Map",
      payload: {
        type: "map",
        scene_map_id: sceneMap.id,
        map_id: mapRecord.id,
        asset_id: mapAsset.id,
        asset_url: `/api/player-display/assets/${mapAsset.id}/blob`,
        width: 320,
        height: 180,
        title: "Harbor Map",
        fit_mode: "fit",
        grid: { type: "square", visible: true, size_px: 40, offset_x: 0, offset_y: 0, color: "#FFFFFF", opacity: 0.35 }
      },
      revision: 10
    };

    render(<PlayerDisplaySurface state={state} now={Date.now()} reconnecting />);

    const image = screen.getByAltText("Harbor Map");
    expect(image).toHaveAttribute("src", `/api/player-display/assets/${mapAsset.id}/blob`);
    expect(screen.getByText("Reconnecting")).toBeInTheDocument();
    fireEvent.error(image);
    expect(screen.getByText("Map unavailable")).toBeInTheDocument();
  });

  it("renders player display map fog mode through public fog payload", () => {
    const state: PlayerDisplayState = {
      ...playerDisplayState,
      mode: "map",
      title: "Harbor Map",
      payload: {
        type: "map",
        scene_map_id: sceneMap.id,
        map_id: mapRecord.id,
        asset_id: mapAsset.id,
        asset_url: `/api/player-display/assets/${mapAsset.id}/blob`,
        width: 320,
        height: 180,
        title: "Harbor Map",
        fit_mode: "fit",
        grid: { type: "square", visible: true, size_px: 40, offset_x: 0, offset_y: 0, color: "#FFFFFF", opacity: 0.35 },
        fog: {
          enabled: true,
          mask_id: fogMask.id,
          mask_url: `/api/player-display/fog/${fogMask.id}/mask?revision=1`,
          revision: 1,
          width: 320,
          height: 180
        }
      },
      revision: 11
    };
    const { container } = render(<PlayerDisplaySurface state={state} now={Date.now()} reconnecting={false} />);

    expect(container.querySelector(".player-map .render-player canvas")).toBeInTheDocument();
  });

  it("renders player display text mode with safe markdown", () => {
    const state: PlayerDisplayState = {
      ...playerDisplayState,
      mode: "text",
      title: "Safe clue",
      payload: {
        type: "public_snippet",
        snippet_id: publicSnippet.id,
        title: "Safe clue",
        body: "**Safe clue text.** [Do not navigate](https://example.com)",
        format: "markdown"
      },
      revision: 13
    };
    const { container } = render(<PlayerDisplaySurface state={state} now={Date.now()} reconnecting />);

    expect(screen.getByText("Safe clue")).toBeInTheDocument();
    expect(screen.getByText("Safe clue text.")).toBeInTheDocument();
    expect(container.querySelector("a")).toBeNull();
    expect(screen.getByText("Reconnecting")).toBeInTheDocument();
  });

  it("renders player display party mode from sanitized cards", () => {
    const state: PlayerDisplayState = {
      ...playerDisplayState,
      mode: "party",
      title: "Party",
      payload: {
        type: "party",
        campaign_id: "c1",
        layout: "standard",
        cards: [
          {
            entity_id: partyEntity.id,
            display_name: "Aria",
            kind: "pc",
            portrait_asset_id: asset.id,
            portrait_url: `/api/player-display/assets/${asset.id}/blob`,
            fields: [
              { key: "level", label: "Level", type: "number", value: 5 },
              { key: "hp", label: "HP", type: "resource", value: { current: 22, max: 31 } }
            ]
          }
        ]
      },
      revision: 15
    };
    render(<PlayerDisplaySurface state={state} now={Date.now()} reconnecting />);

    expect(screen.getByText("Aria")).toBeInTheDocument();
    expect(screen.getByText("Level")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("HP")).toBeInTheDocument();
    expect(screen.getByText("22/31")).toBeInTheDocument();
    expect(screen.queryByText("PRIVATE ENTITY NOTE")).not.toBeInTheDocument();
    expect(screen.queryByText("PRIVATE FIELD")).not.toBeInTheDocument();
    const portrait = screen.getByAltText("Aria");
    fireEvent.error(portrait);
    expect(screen.queryByAltText("Aria")).not.toBeInTheDocument();
    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText("Reconnecting")).toBeInTheDocument();
  });

  it("renders player display initiative mode from sanitized order", () => {
    const state: PlayerDisplayState = {
      ...playerDisplayState,
      mode: "initiative",
      title: "Initiative",
      subtitle: "Deck Fight",
      payload: {
        type: "initiative",
        encounter_id: combatEncounter.id,
        round: 2,
        active_combatant_id: combatEncounter.combatants[0].id,
        combatants: [
          {
            id: combatEncounter.combatants[0].id,
            name: "Aria",
            disposition: "pc",
            initiative: 18,
            is_active: true,
            portrait_asset_id: asset.id,
            portrait_url: `/api/player-display/assets/${asset.id}/blob`,
            public_status: ["Blessed"]
          }
        ]
      },
      revision: 19
    };
    render(<PlayerDisplaySurface state={state} now={Date.now()} reconnecting />);

    expect(screen.getByText("Deck Fight")).toBeInTheDocument();
    expect(screen.getByText("Round 2")).toBeInTheDocument();
    expect(screen.getByText("Aria")).toBeInTheDocument();
    expect(screen.getByText("Initiative 18 · pc")).toBeInTheDocument();
    expect(screen.getByText("Blessed")).toBeInTheDocument();
    expect(screen.queryByText("PRIVATE COMBAT NOTE")).not.toBeInTheDocument();
    expect(screen.queryByText("SECRET CONDITION")).not.toBeInTheDocument();
    expect(screen.getByText("Reconnecting")).toBeInTheDocument();
  });

  it("renders safe markdown links as inert text", () => {
    const { container } = render(<SafeMarkdownRenderer body={"Read [this clue](https://example.com)."} />);

    expect(screen.getByText("this clue")).toBeInTheDocument();
    expect(container.querySelector("a")).toBeNull();
  });

  it("renders player display initial degraded state and only calls public display API", async () => {
    const fetchMock = vi.fn((_input: RequestInfo | URL) => Promise.reject(new Error("offline")));
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(<PlayerDisplayApp />);

    expect(await screen.findByText("Player display unavailable")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalled();
    expect(fetchMock.mock.calls.every(([url]) => String(url).includes("/api/player-display"))).toBe(true);
  });
});
