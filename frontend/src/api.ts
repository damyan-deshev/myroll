import type {
  ApiErrorEnvelope,
  Asset,
  AssetBatchUploadResponse,
  AssetKind,
  AssetVisibility,
  BundledAssetPack,
  BundledMap,
  BundledMapCreateResult,
  Campaign,
  CampaignMemoryEntry,
  CampaignMemoryEntriesResponse,
  CombatantDeleteResult,
  CombatantDisposition,
  CombatantRecord,
  CombatEncounter,
  CombatEncounterStatus,
  CombatEncountersResponse,
  CustomFieldDefinition,
  CustomFieldsResponse,
  DisplayFitMode,
  EntitiesResponse,
  EntityRecord,
  EntityAlias,
  FogMask,
  FogOperation,
  FogOperationResult,
  Health,
  MapRecord,
  Meta,
  BuildBranchResult,
  PlayerSafeRecapResult,
  BuildRecapResult,
  LlmContextPackage,
  LlmProviderProfile,
  LlmProviderProfilesResponse,
  LlmRun,
  MemoryCandidate,
  MemoryCandidatesResponse,
  Note,
  NotesResponse,
  PlayerDisplayState,
  PublicSnippet,
  PublicSnippetsResponse,
  PublicSafetyWarningScanResult,
  PartyTrackerConfig,
  PlanningMarker,
  PlanningMarkersResponse,
  ProposalOption,
  ProposalSetDetail,
  ProposalSetsResponse,
  SceneMapToken,
  RuntimeState,
  Scene,
  SceneContext,
  SceneEntityRole,
  SceneStagedDisplayMode,
  SceneMap,
  Session,
  SessionRecap,
  SessionRecapsResponse,
  SessionTranscriptEvent,
  StorageArtifact,
  StorageStatus,
  TranscriptEventsResponse,
  RecallResult,
  TokenDeleteResult,
  TokenMutationResult,
  TokensResponse,
  WidgetPatch,
  WorkspaceWidget,
  WorkspaceWidgetsResponse
} from "./types";

const rawBase = import.meta.env.VITE_API_BASE_URL ?? "";
const API_BASE = rawBase.endsWith("/") ? rawBase.slice(0, -1) : rawBase;

export class ApiError extends Error {
  code: string;
  status: number;
  details?: Array<Record<string, unknown>>;

  constructor(status: number, code: string, message: string, details?: Array<Record<string, unknown>>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: isFormData
        ? init?.headers
        : {
            "Content-Type": "application/json",
            ...(init?.headers ?? {})
          }
    });
  } catch (error) {
    throw new ApiError(0, "backend_unavailable", "Backend unavailable");
  }

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const envelope = data as ApiErrorEnvelope | null;
    if (envelope?.error) {
      throw new ApiError(response.status, envelope.error.code, envelope.error.message, envelope.error.details);
    }
    throw new ApiError(response.status, "http_error", response.statusText || "Request failed");
  }
  return data as T;
}

export const api = {
  health: () => request<Health>("/health"),
  meta: () => request<Meta>("/api/meta"),
  storageStatus: () => request<StorageStatus>("/api/storage/status"),
  createStorageBackup: () => request<StorageArtifact>("/api/storage/backup", { method: "POST" }),
  createStorageExport: (payload?: { include_llm_history?: boolean }) =>
    request<StorageArtifact>(`/api/storage/export${payload?.include_llm_history ? "?include_llm_history=true" : ""}`, { method: "POST" }),
  runtime: () => request<RuntimeState>("/api/runtime"),
  campaigns: () => request<Campaign[]>("/api/campaigns"),
  createCampaign: (payload: { name: string; description?: string }) =>
    request<Campaign>("/api/campaigns", { method: "POST", body: JSON.stringify(payload) }),
  assets: (campaignId: string) => request<Asset[]>(`/api/campaigns/${campaignId}/assets`),
  notes: (campaignId: string) => request<NotesResponse>(`/api/campaigns/${campaignId}/notes`),
  createNote: (
    campaignId: string,
    payload: { title: string; private_body?: string; tags?: string[]; session_id?: string | null; scene_id?: string | null; asset_id?: string | null }
  ) =>
    request<Note>(`/api/campaigns/${campaignId}/notes`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  note: (noteId: string) => request<Note>(`/api/notes/${noteId}`),
  patchNote: (
    noteId: string,
    payload: Partial<Pick<Note, "title" | "private_body" | "tags" | "session_id" | "scene_id" | "asset_id">>
  ) =>
    request<Note>(`/api/notes/${noteId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  importNoteUpload: (
    campaignId: string,
    payload: {
      file: File;
      title?: string;
      tags?: string;
      session_id?: string | null;
      scene_id?: string | null;
      asset_id?: string | null;
    }
  ) => {
    const body = new FormData();
    body.append("file", payload.file);
    if (payload.title) body.append("title", payload.title);
    if (payload.tags) body.append("tags", payload.tags);
    if (payload.session_id) body.append("session_id", payload.session_id);
    if (payload.scene_id) body.append("scene_id", payload.scene_id);
    if (payload.asset_id) body.append("asset_id", payload.asset_id);
    return request<Note>(`/api/campaigns/${campaignId}/notes/import-upload`, { method: "POST", body });
  },
  publicSnippets: (campaignId: string) => request<PublicSnippetsResponse>(`/api/campaigns/${campaignId}/public-snippets`),
  createPublicSnippet: (
    campaignId: string,
    payload: {
      note_id?: string | null;
      title?: string | null;
      body: string;
      format?: "markdown";
      creation_source?: "manual" | "llm_scribe";
      source_llm_run_id?: string | null;
      source_draft_hash?: string | null;
      warning_content_hash?: string | null;
      warning_ack_content_hash?: string | null;
    }
  ) =>
    request<PublicSnippet>(`/api/campaigns/${campaignId}/public-snippets`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  patchPublicSnippet: (snippetId: string, payload: Partial<Pick<PublicSnippet, "title" | "body" | "format">>) =>
    request<PublicSnippet>(`/api/public-snippets/${snippetId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  transcriptEvents: (campaignId: string, sessionId?: string | null) =>
    request<TranscriptEventsResponse>(`/api/campaigns/${campaignId}/scribe/transcript-events${sessionId ? `?session_id=${sessionId}` : ""}`),
  createTranscriptEvent: (
    campaignId: string,
    payload: { session_id: string; scene_id?: string | null; body: string; source?: string }
  ) =>
    request<SessionTranscriptEvent>(`/api/campaigns/${campaignId}/scribe/transcript-events`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  correctTranscriptEvent: (eventId: string, payload: { body: string }) =>
    request<SessionTranscriptEvent>(`/api/scribe/transcript-events/${eventId}/correct`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  llmProviderProfiles: () => request<LlmProviderProfilesResponse>("/api/llm/provider-profiles"),
  createLlmProviderProfile: (payload: {
    label: string;
    vendor: LlmProviderProfile["vendor"];
    base_url: string;
    model_id: string;
    key_source: { type: "none" | "env"; ref?: string | null };
  }) =>
    request<LlmProviderProfile>("/api/llm/provider-profiles", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  patchLlmProviderProfile: (
    profileId: string,
    payload: Partial<Pick<LlmProviderProfile, "label" | "vendor" | "base_url" | "model_id">> & {
      key_source?: { type: "none" | "env"; ref?: string | null };
    }
  ) =>
    request<LlmProviderProfile>(`/api/llm/provider-profiles/${profileId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  testLlmProviderProfile: (profileId: string) =>
    request<{ profile: LlmProviderProfile; ok: boolean; conformance_level: string; message: string; metadata: Record<string, unknown> }>(
      `/api/llm/provider-profiles/${profileId}/test`,
      { method: "POST" }
    ),
  createContextPreview: (
    campaignId: string,
    payload: {
      session_id?: string | null;
      scene_id?: string | null;
      task_kind?: string;
      scope_kind?: "campaign" | "session" | "scene";
      visibility_mode?: "gm_private" | "public_safe";
      gm_instruction?: string;
      include_unshown_public_snippets?: boolean;
      excluded_source_refs?: string[];
    }
  ) =>
    request<LlmContextPackage>(`/api/campaigns/${campaignId}/llm/context-preview`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  reviewContextPackage: (packageId: string) =>
    request<LlmContextPackage>(`/api/llm/context-packages/${packageId}/review`, { method: "POST" }),
  buildSessionRecap: (
    campaignId: string,
    payload: { session_id: string; provider_profile_id: string; context_package_id: string; verify?: boolean }
  ) =>
    request<BuildRecapResult>(`/api/campaigns/${campaignId}/llm/session-recap/build`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  buildBranchDirections: (campaignId: string, payload: { provider_profile_id: string; context_package_id: string }) =>
    request<BuildBranchResult>(`/api/campaigns/${campaignId}/llm/branch-directions/build`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  buildPlayerSafeRecap: (
    campaignId: string,
    payload: { session_id: string; provider_profile_id: string; context_package_id: string }
  ) =>
    request<PlayerSafeRecapResult>(`/api/campaigns/${campaignId}/llm/player-safe-recap/build`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  scanPublicSafetyWarnings: (campaignId: string, payload: { title?: string | null; body_markdown: string }) =>
    request<PublicSafetyWarningScanResult>(`/api/campaigns/${campaignId}/scribe/public-safety-warnings`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  proposalSets: (campaignId: string) => request<ProposalSetsResponse>(`/api/campaigns/${campaignId}/proposal-sets`),
  proposalSet: (proposalSetId: string) => request<ProposalSetDetail>(`/api/proposal-sets/${proposalSetId}`),
  selectProposalOption: (optionId: string) =>
    request<ProposalOption>(`/api/proposal-options/${optionId}/select`, { method: "POST" }),
  rejectProposalOption: (optionId: string) =>
    request<ProposalOption>(`/api/proposal-options/${optionId}/reject`, { method: "POST" }),
  saveProposalOptionForLater: (optionId: string) =>
    request<ProposalOption>(`/api/proposal-options/${optionId}/save-for-later`, { method: "POST" }),
  createPlanningMarkerFromOption: (
    optionId: string,
    payload: {
      title: string;
      marker_text: string;
      scope_kind?: "campaign" | "session" | "scene" | null;
      session_id?: string | null;
      scene_id?: string | null;
      expires_at?: string | null;
      confirm_warnings?: boolean;
    }
  ) =>
    request<PlanningMarker>(`/api/proposal-options/${optionId}/create-planning-marker`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  planningMarkers: (campaignId: string) => request<PlanningMarkersResponse>(`/api/campaigns/${campaignId}/planning-markers`),
  patchPlanningMarker: (
    markerId: string,
    payload: Partial<Pick<PlanningMarker, "title" | "marker_text" | "expires_at">> & { confirm_warnings?: boolean }
  ) =>
    request<PlanningMarker>(`/api/planning-markers/${markerId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  expirePlanningMarker: (markerId: string) =>
    request<PlanningMarker>(`/api/planning-markers/${markerId}/expire`, { method: "POST" }),
  discardPlanningMarker: (markerId: string) =>
    request<PlanningMarker>(`/api/planning-markers/${markerId}/discard`, { method: "POST" }),
  saveSessionRecap: (
    campaignId: string,
    payload: { session_id: string; title: string; body_markdown: string; source_llm_run_id?: string | null; evidence_refs?: Array<Record<string, unknown>> }
  ) =>
    request<SessionRecap>(`/api/campaigns/${campaignId}/scribe/session-recaps`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  sessionRecaps: (campaignId: string, sessionId?: string | null) =>
    request<SessionRecapsResponse>(`/api/campaigns/${campaignId}/scribe/session-recaps${sessionId ? `?session_id=${sessionId}` : ""}`),
  patchSessionRecapPublicSafety: (
    recapId: string,
    payload: {
      campaign_id?: string | null;
      public_safe: boolean;
      sensitivity_reason?: string | null;
      warning_content_hash?: string | null;
      warning_ack_content_hash?: string | null;
    }
  ) =>
    request<SessionRecap>(`/api/scribe/session-recaps/${recapId}/public-safety`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  memoryEntries: (campaignId: string, sessionId?: string | null) =>
    request<CampaignMemoryEntriesResponse>(`/api/campaigns/${campaignId}/scribe/memory-entries${sessionId ? `?session_id=${sessionId}` : ""}`),
  patchMemoryEntryPublicSafety: (
    entryId: string,
    payload: {
      campaign_id?: string | null;
      public_safe: boolean;
      sensitivity_reason?: string | null;
      warning_content_hash?: string | null;
      warning_ack_content_hash?: string | null;
    }
  ) =>
    request<CampaignMemoryEntry>(`/api/scribe/memory-entries/${entryId}/public-safety`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  memoryCandidates: (campaignId: string) => request<MemoryCandidatesResponse>(`/api/campaigns/${campaignId}/scribe/memory-candidates`),
  editMemoryCandidate: (candidateId: string, payload: Partial<Pick<MemoryCandidate, "title" | "body">>) =>
    request<MemoryCandidate>(`/api/scribe/memory-candidates/${candidateId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  acceptMemoryCandidate: (candidateId: string, payload?: { confirm_linked_marker_canonization?: boolean }) =>
    request<CampaignMemoryEntry>(`/api/scribe/memory-candidates/${candidateId}/accept`, {
      method: "POST",
      body: payload ? JSON.stringify(payload) : undefined
    }),
  rejectMemoryCandidate: (candidateId: string) =>
    request<MemoryCandidate>(`/api/scribe/memory-candidates/${candidateId}/reject`, { method: "POST" }),
  entityAliases: (campaignId: string) => request<EntityAlias[]>(`/api/campaigns/${campaignId}/scribe/aliases`),
  createEntityAlias: (campaignId: string, payload: { alias_text: string; entity_id?: string | null; language?: string | null }) =>
    request<EntityAlias>(`/api/campaigns/${campaignId}/scribe/aliases`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  recall: (campaignId: string, payload: { query: string; include_draft?: boolean }) =>
    request<RecallResult>(`/api/campaigns/${campaignId}/scribe/recall`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  entities: (campaignId: string) => request<EntitiesResponse>(`/api/campaigns/${campaignId}/entities`),
  createEntity: (
    campaignId: string,
    payload: Partial<Pick<EntityRecord, "kind" | "name" | "display_name" | "visibility" | "portrait_asset_id" | "tags" | "notes">>
  ) =>
    request<EntityRecord>(`/api/campaigns/${campaignId}/entities`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  entity: (entityId: string) => request<EntityRecord>(`/api/entities/${entityId}`),
  patchEntity: (
    entityId: string,
    payload: Partial<Pick<EntityRecord, "kind" | "name" | "display_name" | "visibility" | "portrait_asset_id" | "tags" | "notes">>
  ) =>
    request<EntityRecord>(`/api/entities/${entityId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  customFields: (campaignId: string) => request<CustomFieldsResponse>(`/api/campaigns/${campaignId}/custom-fields`),
  createCustomField: (
    campaignId: string,
    payload: Pick<
      CustomFieldDefinition,
      "key" | "label" | "field_type" | "applies_to" | "required" | "default_value" | "options" | "public_by_default" | "sort_order"
    >
  ) =>
    request<CustomFieldDefinition>(`/api/campaigns/${campaignId}/custom-fields`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  patchCustomField: (
    fieldId: string,
    payload: Partial<Pick<CustomFieldDefinition, "label" | "applies_to" | "required" | "default_value" | "options" | "public_by_default" | "sort_order">>
  ) =>
    request<CustomFieldDefinition>(`/api/custom-fields/${fieldId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  patchEntityFieldValues: (entityId: string, values: Record<string, unknown | null>) =>
    request<EntityRecord>(`/api/entities/${entityId}/field-values`, {
      method: "PATCH",
      body: JSON.stringify({ values })
    }),
  partyTracker: (campaignId: string) => request<PartyTrackerConfig>(`/api/campaigns/${campaignId}/party-tracker`),
  patchPartyTracker: (
    campaignId: string,
    payload: { layout?: string; member_ids?: string[]; fields?: Array<{ field_definition_id: string; public_visible: boolean }> }
  ) =>
    request<PartyTrackerConfig>(`/api/campaigns/${campaignId}/party-tracker`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  combatEncounters: (campaignId: string) => request<CombatEncountersResponse>(`/api/campaigns/${campaignId}/combat-encounters`),
  createCombatEncounter: (
    campaignId: string,
    payload: { title: string; session_id?: string | null; scene_id?: string | null; status?: CombatEncounterStatus }
  ) =>
    request<CombatEncounter>(`/api/campaigns/${campaignId}/combat-encounters`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  combatEncounter: (encounterId: string) => request<CombatEncounter>(`/api/combat-encounters/${encounterId}`),
  patchCombatEncounter: (
    encounterId: string,
    payload: Partial<Pick<CombatEncounter, "title" | "session_id" | "scene_id" | "status" | "round" | "active_combatant_id">>
  ) =>
    request<CombatEncounter>(`/api/combat-encounters/${encounterId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  createCombatant: (
    encounterId: string,
    payload: {
      entity_id?: string | null;
      token_id?: string | null;
      name?: string | null;
      disposition?: CombatantDisposition | null;
      initiative?: number | null;
      armor_class?: number | null;
      hp_current?: number | null;
      hp_max?: number | null;
      hp_temp?: number;
      conditions?: Array<Record<string, unknown>>;
      public_status?: Array<string | { label: string }>;
      notes?: string;
      public_visible?: boolean | null;
      is_defeated?: boolean;
    }
  ) =>
    request<CombatEncounter>(`/api/combat-encounters/${encounterId}/combatants`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  patchCombatant: (combatantId: string, payload: Partial<CombatantRecord>) =>
    request<CombatEncounter>(`/api/combatants/${combatantId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  deleteCombatant: (combatantId: string) => request<CombatantDeleteResult>(`/api/combatants/${combatantId}`, { method: "DELETE" }),
  reorderCombatants: (encounterId: string, combatantIds: string[]) =>
    request<CombatEncounter>(`/api/combat-encounters/${encounterId}/reorder`, {
      method: "POST",
      body: JSON.stringify({ combatant_ids: combatantIds })
    }),
  nextCombatTurn: (encounterId: string) =>
    request<CombatEncounter>(`/api/combat-encounters/${encounterId}/next-turn`, { method: "POST" }),
  previousCombatTurn: (encounterId: string) =>
    request<CombatEncounter>(`/api/combat-encounters/${encounterId}/previous-turn`, { method: "POST" }),
  uploadAsset: (
    campaignId: string,
    payload: {
      file: File;
      kind: AssetKind;
      visibility: AssetVisibility;
      name?: string;
      tags?: string;
    }
  ) => {
    const body = new FormData();
    body.append("file", payload.file);
    body.append("kind", payload.kind);
    body.append("visibility", payload.visibility);
    if (payload.name) body.append("name", payload.name);
    if (payload.tags) body.append("tags", payload.tags);
    return request<Asset>(`/api/campaigns/${campaignId}/assets/upload`, { method: "POST", body });
  },
  uploadAssetsBatch: (
    campaignId: string,
    payload: {
      files: File[];
      kind: AssetKind;
      visibility: AssetVisibility;
      tags?: string;
      auto_create_maps?: boolean;
    }
  ) => {
    const body = new FormData();
    payload.files.forEach((file) => body.append("files", file));
    body.append("kind", payload.kind);
    body.append("visibility", payload.visibility);
    if (payload.tags) body.append("tags", payload.tags);
    body.append("auto_create_maps", payload.auto_create_maps ? "true" : "false");
    return request<AssetBatchUploadResponse>(`/api/campaigns/${campaignId}/assets/upload-batch`, { method: "POST", body });
  },
  bundledAssetPacks: () => request<BundledAssetPack[]>("/api/bundled-asset-packs"),
  bundledAssetPackMaps: (packId: string) => request<BundledMap[]>(`/api/bundled-asset-packs/${encodeURIComponent(packId)}/maps`),
  addBundledMapToCampaign: (campaignId: string, payload: { pack_id: string; asset_id: string; name?: string | null }) =>
    request<BundledMapCreateResult>(`/api/campaigns/${campaignId}/bundled-maps`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  maps: (campaignId: string) => request<MapRecord[]>(`/api/campaigns/${campaignId}/maps`),
  createMap: (campaignId: string, payload: { asset_id: string; name?: string | null }) =>
    request<MapRecord>(`/api/campaigns/${campaignId}/maps`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  sceneMaps: (campaignId: string, sceneId: string) =>
    request<SceneMap[]>(`/api/campaigns/${campaignId}/scenes/${sceneId}/maps`),
  assignSceneMap: (
    campaignId: string,
    sceneId: string,
    payload: { map_id: string; is_active?: boolean; player_fit_mode?: DisplayFitMode; player_grid_visible?: boolean }
  ) =>
    request<SceneMap>(`/api/campaigns/${campaignId}/scenes/${sceneId}/maps`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  patchMapGrid: (
    mapId: string,
    payload: {
      grid_enabled?: boolean;
      grid_size_px?: number;
      grid_offset_x?: number;
      grid_offset_y?: number;
      grid_color?: string;
      grid_opacity?: number;
    }
  ) =>
    request<MapRecord>(`/api/maps/${mapId}/grid`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  patchSceneMap: (sceneMapId: string, payload: { player_fit_mode?: DisplayFitMode; player_grid_visible?: boolean }) =>
    request<SceneMap>(`/api/scene-maps/${sceneMapId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  activateSceneMap: (sceneMapId: string) =>
    request<SceneMap>(`/api/scene-maps/${sceneMapId}/activate`, { method: "POST" }),
  sceneMapFog: (sceneMapId: string) => request<FogMask | null>(`/api/scene-maps/${sceneMapId}/fog`),
  enableSceneMapFog: (sceneMapId: string) =>
    request<FogMask>(`/api/scene-maps/${sceneMapId}/fog/enable`, { method: "POST" }),
  applySceneMapFogOperations: (sceneMapId: string, operations: FogOperation[]) =>
    request<FogOperationResult>(`/api/scene-maps/${sceneMapId}/fog/operations`, {
      method: "POST",
      body: JSON.stringify({ operations })
    }),
  sceneMapTokens: (sceneMapId: string) => request<TokensResponse>(`/api/scene-maps/${sceneMapId}/tokens`),
  createSceneMapToken: (
    sceneMapId: string,
    payload: Partial<
      Pick<
        SceneMapToken,
        | "name"
        | "x"
        | "y"
        | "width"
        | "height"
        | "rotation"
        | "z_index"
        | "visibility"
        | "label_visibility"
        | "shape"
        | "color"
        | "border_color"
        | "opacity"
        | "asset_id"
        | "entity_id"
        | "status"
      >
    >
  ) =>
    request<TokenMutationResult>(`/api/scene-maps/${sceneMapId}/tokens`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  patchToken: (
    tokenId: string,
    payload: Partial<
      Pick<
        SceneMapToken,
        | "name"
        | "x"
        | "y"
        | "width"
        | "height"
        | "rotation"
        | "z_index"
        | "visibility"
        | "label_visibility"
        | "shape"
        | "color"
        | "border_color"
        | "opacity"
        | "asset_id"
        | "entity_id"
        | "status"
      >
    >
  ) =>
    request<TokenMutationResult>(`/api/tokens/${tokenId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  deleteToken: (tokenId: string) => request<TokenDeleteResult>(`/api/tokens/${tokenId}`, { method: "DELETE" }),
  sessions: (campaignId: string) => request<Session[]>(`/api/campaigns/${campaignId}/sessions`),
  createSession: (campaignId: string, payload: { title: string }) =>
    request<Session>(`/api/campaigns/${campaignId}/sessions`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  scenes: (campaignId: string) => request<Scene[]>(`/api/campaigns/${campaignId}/scenes`),
  createScene: (campaignId: string, payload: { title: string; summary?: string; session_id?: string | null }) =>
    request<Scene>(`/api/campaigns/${campaignId}/scenes`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  sceneContext: (sceneId: string) => request<SceneContext>(`/api/scenes/${sceneId}/context`),
  patchSceneContext: (
    sceneId: string,
    payload: {
      active_encounter_id?: string | null;
      staged_display_mode?: SceneStagedDisplayMode | null;
      staged_public_snippet_id?: string | null;
    }
  ) =>
    request<SceneContext>(`/api/scenes/${sceneId}/context`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  linkSceneEntity: (
    sceneId: string,
    payload: { entity_id: string; role?: SceneEntityRole; sort_order?: number; notes?: string }
  ) =>
    request<SceneContext>(`/api/scenes/${sceneId}/entity-links`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  unlinkSceneEntity: (linkId: string) =>
    request<SceneContext>(`/api/scene-entity-links/${linkId}`, { method: "DELETE" }),
  linkScenePublicSnippet: (sceneId: string, payload: { public_snippet_id: string; sort_order?: number }) =>
    request<SceneContext>(`/api/scenes/${sceneId}/public-snippet-links`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  unlinkScenePublicSnippet: (linkId: string) =>
    request<SceneContext>(`/api/scene-public-snippet-links/${linkId}`, { method: "DELETE" }),
  publishSceneStagedDisplay: (sceneId: string) =>
    request<PlayerDisplayState>(`/api/scenes/${sceneId}/publish-staged-display`, { method: "POST" }),
  activateCampaign: (campaignId: string) =>
    request<RuntimeState>("/api/runtime/activate-campaign", {
      method: "POST",
      body: JSON.stringify({ campaign_id: campaignId })
    }),
  activateSession: (sessionId: string) =>
    request<RuntimeState>("/api/runtime/activate-session", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId })
    }),
  activateScene: (sceneId: string) =>
    request<RuntimeState>("/api/runtime/activate-scene", {
      method: "POST",
      body: JSON.stringify({ scene_id: sceneId })
    }),
  clearRuntime: () => request<RuntimeState>("/api/runtime/clear", { method: "POST" }),
  playerDisplay: () => request<PlayerDisplayState>("/api/player-display"),
  playerDisplayBlackout: () => request<PlayerDisplayState>("/api/player-display/blackout", { method: "POST" }),
  playerDisplayIntermission: () => request<PlayerDisplayState>("/api/player-display/intermission", { method: "POST" }),
  playerDisplayShowSceneTitle: (sceneId?: string | null) =>
    request<PlayerDisplayState>("/api/player-display/show-scene-title", {
      method: "POST",
      body: sceneId ? JSON.stringify({ scene_id: sceneId }) : undefined
    }),
  playerDisplayShowImage: (payload: {
    asset_id: string;
    title?: string | null;
    caption?: string | null;
    fit_mode?: DisplayFitMode;
  }) =>
    request<PlayerDisplayState>("/api/player-display/show-image", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  playerDisplayShowMap: (sceneMapId?: string | null) =>
    request<PlayerDisplayState>("/api/player-display/show-map", {
      method: "POST",
      body: sceneMapId ? JSON.stringify({ scene_map_id: sceneMapId }) : undefined
    }),
  playerDisplayShowSnippet: (snippetId: string) =>
    request<PlayerDisplayState>("/api/player-display/show-snippet", {
      method: "POST",
      body: JSON.stringify({ snippet_id: snippetId })
    }),
  playerDisplayShowParty: (campaignId: string) =>
    request<PlayerDisplayState>("/api/player-display/show-party", {
      method: "POST",
      body: JSON.stringify({ campaign_id: campaignId })
    }),
  playerDisplayShowInitiative: (encounterId: string) =>
    request<PlayerDisplayState>("/api/player-display/show-initiative", {
      method: "POST",
      body: JSON.stringify({ encounter_id: encounterId })
    }),
  playerDisplayIdentify: () => request<PlayerDisplayState>("/api/player-display/identify", { method: "POST" }),
  workspaceWidgets: () => request<WorkspaceWidgetsResponse>("/api/workspace/widgets"),
  patchWorkspaceWidget: (widgetId: string, payload: WidgetPatch) =>
    request<WorkspaceWidget>(`/api/workspace/widgets/${widgetId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  resetWorkspaceWidgets: () => request<WorkspaceWidgetsResponse>("/api/workspace/widgets/reset", { method: "POST" })
};
