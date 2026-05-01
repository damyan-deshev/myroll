import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

function mockResponse(body: unknown, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    statusText: ok ? "OK" : "Bad Request",
    text: () => Promise.resolve(JSON.stringify(body))
  } as Response);
}

describe("api client", () => {
  it("parses success responses", async () => {
    const fetchMock = vi.fn(() => mockResponse({ status: "ok", db: "ok" }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.health();

    expect(result.status).toBe("ok");
    expect(fetchMock).toHaveBeenCalledWith(
      "/health",
      expect.objectContaining({ headers: expect.objectContaining({ "Content-Type": "application/json" }) })
    );
  });

  it("parses error envelopes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        mockResponse(
          {
            error: {
              code: "validation_error",
              message: "Request validation failed",
              details: [{ loc: ["body", "name"], message: "required" }]
            }
          },
          false,
          422
        )
      )
    );

    await expect(api.createCampaign({ name: "" })).rejects.toMatchObject({
      status: 422,
      code: "validation_error",
      message: "Request validation failed"
    } satisfies Partial<ApiError>);
  });

  it("reports backend unavailable when fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("offline")))
    );

    await expect(api.health()).rejects.toMatchObject({
      status: 0,
      code: "backend_unavailable"
    } satisfies Partial<ApiError>);
  });

  it("calls storage status, backup, and export endpoints", async () => {
    const fetchMock = vi.fn(() =>
      mockResponse({
        archive_name: "myroll.20260428T010203Z.export.tar.gz",
        byte_size: 1234,
        created_at: "2026-04-28T01:02:03Z",
        download_url: "/api/storage/exports/myroll.20260428T010203Z.export.tar.gz"
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.storageStatus();
    await api.createStorageBackup();
    await api.createStorageExport();

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/storage/status",
      expect.objectContaining({ headers: expect.objectContaining({ "Content-Type": "application/json" }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/storage/backup",
      expect.objectContaining({ method: "POST" })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/storage/export",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("calls player display endpoints", async () => {
    const fetchMock = vi.fn(() =>
      mockResponse({
        mode: "intermission",
        title: "Intermission",
        subtitle: null,
        active_campaign_id: null,
        active_campaign_name: null,
        active_session_id: null,
        active_session_title: null,
        active_scene_id: null,
        active_scene_title: null,
        payload: {},
        revision: 2,
        identify_revision: 0,
        identify_until: null,
        updated_at: "2026-04-27T00:00:00Z"
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.playerDisplayIntermission();
    await api.playerDisplayShowSceneTitle("scene-id");
    await api.playerDisplayShowImage({ asset_id: "asset-id", fit_mode: "fit" });
    await api.playerDisplayShowMap("scene-map-id");
    await api.playerDisplayShowSnippet("snippet-id");
    await api.playerDisplayShowParty("campaign-id");
    await api.playerDisplayShowInitiative("encounter-id");

    expect(result.mode).toBe("intermission");
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/player-display/intermission",
      expect.objectContaining({ method: "POST" })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/player-display/show-scene-title",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ scene_id: "scene-id" }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/player-display/show-image",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ asset_id: "asset-id", fit_mode: "fit" }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/player-display/show-map",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ scene_map_id: "scene-map-id" }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "/api/player-display/show-snippet",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ snippet_id: "snippet-id" }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "/api/player-display/show-party",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ campaign_id: "campaign-id" }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      7,
      "/api/player-display/show-initiative",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ encounter_id: "encounter-id" }) })
    );
  });

  it("calls entity, custom field, and party tracker endpoints", async () => {
    const fetchMock = vi.fn(() =>
      mockResponse({
        id: "entity-id",
        campaign_id: "campaign-id",
        kind: "pc",
        name: "Aria Vell",
        display_name: "Aria",
        visibility: "public_known",
        portrait_asset_id: null,
        portrait_asset_name: null,
        portrait_asset_visibility: null,
        tags: [],
        notes: "",
        field_values: {},
        created_at: "2026-04-27T00:00:00Z",
        updated_at: "2026-04-27T00:00:00Z"
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.entities("campaign-id");
    await api.createEntity("campaign-id", { kind: "pc", name: "Aria Vell", visibility: "public_known" });
    await api.entity("entity-id");
    await api.patchEntity("entity-id", { display_name: "Aria" });
    await api.customFields("campaign-id");
    await api.createCustomField("campaign-id", {
      key: "hp",
      label: "HP",
      field_type: "resource",
      applies_to: ["pc"],
      required: false,
      default_value: null,
      options: [],
      public_by_default: true,
      sort_order: 10
    });
    await api.patchCustomField("field-id", { label: "Hit Points" });
    await api.patchEntityFieldValues("entity-id", { hp: { current: 22, max: 31 } });
    await api.partyTracker("campaign-id");
    await api.patchPartyTracker("campaign-id", {
      layout: "standard",
      member_ids: ["entity-id"],
      fields: [{ field_definition_id: "field-id", public_visible: true }]
    });

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/campaigns/campaign-id/entities", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/campaigns/campaign-id/entities",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ kind: "pc", name: "Aria Vell", visibility: "public_known" }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/entities/entity-id", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/entities/entity-id",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ display_name: "Aria" }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(5, "/api/campaigns/campaign-id/custom-fields", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "/api/campaigns/campaign-id/custom-fields",
      expect.objectContaining({ method: "POST", body: expect.stringContaining("\"key\":\"hp\"") })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      7,
      "/api/custom-fields/field-id",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ label: "Hit Points" }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      8,
      "/api/entities/entity-id/field-values",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ values: { hp: { current: 22, max: 31 } } }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(9, "/api/campaigns/campaign-id/party-tracker", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(
      10,
      "/api/campaigns/campaign-id/party-tracker",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          layout: "standard",
          member_ids: ["entity-id"],
          fields: [{ field_definition_id: "field-id", public_visible: true }]
        })
      })
    );
  });

  it("calls combat tracker endpoints", async () => {
    const fetchMock = vi.fn(() =>
      mockResponse({
        id: "encounter-id",
        campaign_id: "campaign-id",
        session_id: null,
        scene_id: null,
        title: "Deck Fight",
        status: "active",
        round: 1,
        active_combatant_id: null,
        combatants: [],
        created_at: "2026-04-27T00:00:00Z",
        updated_at: "2026-04-27T00:00:00Z"
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.combatEncounters("campaign-id");
    await api.createCombatEncounter("campaign-id", { title: "Deck Fight", session_id: "session-id", scene_id: "scene-id" });
    await api.combatEncounter("encounter-id");
    await api.patchCombatEncounter("encounter-id", { status: "paused", round: 2 });
    await api.createCombatant("encounter-id", { name: "Aria", initiative: 18, public_visible: true });
    await api.patchCombatant("combatant-id", { hp_current: 12, public_visible: false });
    await api.reorderCombatants("encounter-id", ["b", "a"]);
    await api.nextCombatTurn("encounter-id");
    await api.previousCombatTurn("encounter-id");
    await api.deleteCombatant("combatant-id");

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/campaigns/campaign-id/combat-encounters", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/campaigns/campaign-id/combat-encounters",
      expect.objectContaining({ method: "POST", body: expect.stringContaining("\"title\":\"Deck Fight\"") })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/combat-encounters/encounter-id", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/combat-encounters/encounter-id",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ status: "paused", round: 2 }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "/api/combat-encounters/encounter-id/combatants",
      expect.objectContaining({ method: "POST", body: expect.stringContaining("\"public_visible\":true") })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "/api/combatants/combatant-id",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ hp_current: 12, public_visible: false }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      7,
      "/api/combat-encounters/encounter-id/reorder",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ combatant_ids: ["b", "a"] }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(8, "/api/combat-encounters/encounter-id/next-turn", expect.objectContaining({ method: "POST" }));
    expect(fetchMock).toHaveBeenNthCalledWith(9, "/api/combat-encounters/encounter-id/previous-turn", expect.objectContaining({ method: "POST" }));
    expect(fetchMock).toHaveBeenNthCalledWith(10, "/api/combatants/combatant-id", expect.objectContaining({ method: "DELETE" }));
  });

  it("calls notes and public snippet endpoints", async () => {
    const fetchMock = vi.fn(() =>
      mockResponse({
        id: "note-id",
        campaign_id: "campaign-id",
        source_id: null,
        session_id: null,
        scene_id: null,
        asset_id: null,
        title: "Private note",
        private_body: "Secret body",
        tags: [],
        source_label: "Internal Notes",
        created_at: "2026-04-27T00:00:00Z",
        updated_at: "2026-04-27T00:00:00Z"
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.notes("campaign-id");
    await api.createNote("campaign-id", { title: "Private note", private_body: "Secret body" });
    await api.note("note-id");
    await api.patchNote("note-id", { private_body: "Changed body" });
    await api.importNoteUpload("campaign-id", { file: new File(["# Note"], "note.md", { type: "text/markdown" }) });
    await api.publicSnippets("campaign-id");
    await api.createPublicSnippet("campaign-id", { note_id: "note-id", title: "Public", body: "Safe text" });
    await api.patchPublicSnippet("snippet-id", { body: "Changed public text" });

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/campaigns/campaign-id/notes", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/campaigns/campaign-id/notes",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ title: "Private note", private_body: "Secret body" }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/notes/note-id", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/notes/note-id",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ private_body: "Changed body" }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "/api/campaigns/campaign-id/notes/import-upload",
      expect.objectContaining({ method: "POST", body: expect.any(FormData), headers: undefined })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(6, "/api/campaigns/campaign-id/public-snippets", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(
      7,
      "/api/campaigns/campaign-id/public-snippets",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ note_id: "note-id", title: "Public", body: "Safe text" }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      8,
      "/api/public-snippets/snippet-id",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ body: "Changed public text" }) })
    );
  });

  it("calls scene context endpoints", async () => {
    const fetchMock = vi.fn(() =>
      mockResponse({
        scene: {
          id: "scene-id",
          campaign_id: "campaign-id",
          session_id: null,
          title: "Deck",
          summary: null,
          created_at: "2026-04-27T00:00:00Z",
          updated_at: "2026-04-27T00:00:00Z"
        },
        context: {
          id: "context-id",
          campaign_id: "campaign-id",
          scene_id: "scene-id",
          active_encounter_id: null,
          staged_display_mode: "none",
          staged_public_snippet_id: null,
          created_at: "2026-04-27T00:00:00Z",
          updated_at: "2026-04-27T00:00:00Z"
        },
        active_map: null,
        notes: [],
        public_snippets: [],
        entities: [],
        active_encounter: null,
        updated_at: "2026-04-27T00:00:00Z"
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.sceneContext("scene-id");
    await api.patchSceneContext("scene-id", {
      active_encounter_id: "encounter-id",
      staged_display_mode: "public_snippet",
      staged_public_snippet_id: "snippet-id"
    });
    await api.linkSceneEntity("scene-id", { entity_id: "entity-id", role: "threat", sort_order: 2, notes: "GM-only" });
    await api.unlinkSceneEntity("entity-link-id");
    await api.linkScenePublicSnippet("scene-id", { public_snippet_id: "snippet-id", sort_order: 1 });
    await api.unlinkScenePublicSnippet("snippet-link-id");
    await api.publishSceneStagedDisplay("scene-id");

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/scenes/scene-id/context", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/scenes/scene-id/context",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          active_encounter_id: "encounter-id",
          staged_display_mode: "public_snippet",
          staged_public_snippet_id: "snippet-id"
        })
      })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/scenes/scene-id/entity-links",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ entity_id: "entity-id", role: "threat", sort_order: 2, notes: "GM-only" })
      })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(4, "/api/scene-entity-links/entity-link-id", expect.objectContaining({ method: "DELETE" }));
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "/api/scenes/scene-id/public-snippet-links",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ public_snippet_id: "snippet-id", sort_order: 1 }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(6, "/api/scene-public-snippet-links/snippet-link-id", expect.objectContaining({ method: "DELETE" }));
    expect(fetchMock).toHaveBeenNthCalledWith(7, "/api/scenes/scene-id/publish-staged-display", expect.objectContaining({ method: "POST" }));
  });

  it("calls map endpoints", async () => {
    const fetchMock = vi.fn(() =>
      mockResponse({
        id: "map-id",
        campaign_id: "campaign-id",
        asset_id: "asset-id",
        asset_name: "Harbor Map",
        asset_visibility: "public_displayable",
        asset_url: "/api/assets/asset-id/blob",
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
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.createMap("campaign-id", { asset_id: "asset-id", name: "Harbor Map" });
    await api.assignSceneMap("campaign-id", "scene-id", { map_id: "map-id", is_active: true });
    await api.patchMapGrid("map-id", { grid_enabled: true, grid_size_px: 40 });
    await api.patchSceneMap("scene-map-id", { player_fit_mode: "fill", player_grid_visible: false });
    await api.activateSceneMap("scene-map-id");
    await api.sceneMapFog("scene-map-id");
    await api.enableSceneMapFog("scene-map-id");
    await api.applySceneMapFogOperations("scene-map-id", [{ type: "reveal_all" }]);
    await api.sceneMapTokens("scene-map-id");
    await api.createSceneMapToken("scene-map-id", { name: "Guard", visibility: "player_visible" });
    await api.patchToken("token-id", { x: 10, y: 12, rotation: 45 });
    await api.deleteToken("token-id");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/campaigns/campaign-id/maps",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ asset_id: "asset-id", name: "Harbor Map" }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/campaigns/campaign-id/scenes/scene-id/maps",
      expect.objectContaining({ method: "POST" })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/maps/map-id/grid",
      expect.objectContaining({ method: "PATCH" })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/scene-maps/scene-map-id",
      expect.objectContaining({ method: "PATCH" })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "/api/scene-maps/scene-map-id/activate",
      expect.objectContaining({ method: "POST" })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "/api/scene-maps/scene-map-id/fog",
      expect.objectContaining({ headers: expect.objectContaining({ "Content-Type": "application/json" }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      7,
      "/api/scene-maps/scene-map-id/fog/enable",
      expect.objectContaining({ method: "POST" })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      8,
      "/api/scene-maps/scene-map-id/fog/operations",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ operations: [{ type: "reveal_all" }] }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      9,
      "/api/scene-maps/scene-map-id/tokens",
      expect.objectContaining({ headers: expect.objectContaining({ "Content-Type": "application/json" }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      10,
      "/api/scene-maps/scene-map-id/tokens",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ name: "Guard", visibility: "player_visible" }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      11,
      "/api/tokens/token-id",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ x: 10, y: 12, rotation: 45 }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      12,
      "/api/tokens/token-id",
      expect.objectContaining({ method: "DELETE" })
    );
  });

  it("uploads assets with FormData without JSON content type", async () => {
    const fetchMock = vi.fn(() =>
      mockResponse({
        id: "asset-id",
        campaign_id: "campaign-id",
        kind: "handout_image",
        visibility: "public_displayable",
        name: "Handout",
        mime_type: "image/png",
        byte_size: 12,
        checksum: "abc",
        relative_path: "ab/abc.png",
        original_filename: "handout.png",
        width: 10,
        height: 10,
        duration_ms: null,
        tags: [],
        created_at: "2026-04-27T00:00:00Z",
        updated_at: "2026-04-27T00:00:00Z"
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.uploadAsset("campaign-id", {
      file: new File(["fake"], "handout.png", { type: "image/png" }),
      kind: "handout_image",
      visibility: "public_displayable"
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/campaigns/campaign-id/assets/upload",
      expect.objectContaining({ method: "POST", body: expect.any(FormData), headers: undefined })
    );
  });
});
