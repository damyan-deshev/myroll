export type ApiErrorEnvelope = {
  error: {
    code: string;
    message: string;
    details?: Array<Record<string, unknown>>;
  };
};

export type Health = {
  status: string;
  db: string;
  schema_version: string | null;
  db_path: string;
  time: string;
};

export type Meta = {
  app: string;
  version: string;
  db_path: string;
  schema_version: string | null;
  seed_version: string | null;
  expected_seed_version: string;
};

export type Campaign = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type Session = {
  id: string;
  campaign_id: string;
  title: string;
  starts_at: string | null;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
};

export type Scene = {
  id: string;
  campaign_id: string;
  session_id: string | null;
  title: string;
  summary: string | null;
  created_at: string;
  updated_at: string;
};

export type RuntimeState = {
  active_campaign_id: string | null;
  active_campaign_name: string | null;
  active_session_id: string | null;
  active_session_title: string | null;
  active_scene_id: string | null;
  active_scene_title: string | null;
  updated_at: string;
};

export type AssetKind = "map_image" | "handout_image" | "npc_portrait" | "item_image" | "scene_image" | "token_image";
export type AssetVisibility = "private" | "public_displayable";
export type DisplayFitMode = "fit" | "fill" | "stretch" | "actual_size";

export type GridSettings = {
  type: "square";
  visible: boolean;
  size_px: number;
  offset_x: number;
  offset_y: number;
  color: string;
  opacity: number;
};

export type FogMask = {
  id: string;
  campaign_id: string;
  scene_id: string;
  scene_map_id: string;
  enabled: boolean;
  revision: number;
  width: number;
  height: number;
  mask_url: string;
  updated_at: string;
};

export type FogPayload = {
  enabled: boolean;
  mask_id: string;
  mask_url: string;
  revision: number;
  width: number;
  height: number;
};

export type FogRectOperation = {
  type: "reveal_rect" | "hide_rect";
  rect: { x: number; y: number; width: number; height: number };
};

export type FogBrushOperation = {
  type: "reveal_brush" | "hide_brush";
  radius: number;
  points: Array<{ x: number; y: number }>;
};

export type FogAllOperation = {
  type: "reveal_all" | "hide_all";
};

export type FogOperation = FogRectOperation | FogBrushOperation | FogAllOperation;

export type FogOperationResult = {
  fog: FogMask;
  player_display: PlayerDisplayState | null;
};

export type TokenVisibility = "gm_only" | "player_visible" | "hidden_until_revealed";
export type LabelVisibility = "gm_only" | "player_visible" | "hidden";
export type TokenShape = "circle" | "square" | "portrait" | "marker";

export type TokenStyle = {
  shape: TokenShape;
  color: string;
  border_color: string;
  opacity: number;
};

export type SceneMapToken = {
  id: string;
  campaign_id: string;
  scene_id: string;
  scene_map_id: string;
  entity_id: string | null;
  asset_id: string | null;
  asset_name: string | null;
  asset_visibility: AssetVisibility | null;
  asset_url: string | null;
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  z_index: number;
  visibility: TokenVisibility;
  label_visibility: LabelVisibility;
  shape: TokenShape;
  color: string;
  border_color: string;
  opacity: number;
  status: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
};

export type TokensResponse = {
  tokens: SceneMapToken[];
  updated_at: string;
};

export type PublicMapToken = {
  id: string;
  entity_id: string | null;
  asset_id: string | null;
  asset_url: string | null;
  mime_type?: string;
  asset_width?: number;
  asset_height?: number;
  name: string | null;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  style: TokenStyle;
  status: Array<Record<string, unknown>>;
};

export type TokenMutationResult = {
  token: SceneMapToken;
  player_display: PlayerDisplayState | null;
};

export type TokenDeleteResult = {
  deleted_token_id: string;
  player_display: PlayerDisplayState | null;
};

export type NoteSummary = {
  id: string;
  campaign_id: string;
  source_id: string | null;
  session_id: string | null;
  scene_id: string | null;
  asset_id: string | null;
  title: string;
  tags: string[];
  source_label: string | null;
  recall_status: "private_prep" | "scoped_recall_eligible" | "archived";
  created_at: string;
  updated_at: string;
};

export type Note = NoteSummary & {
  private_body: string;
};

export type NotesResponse = {
  notes: NoteSummary[];
  updated_at: string;
};

export type PublicSnippet = {
  id: string;
  campaign_id: string;
  note_id: string | null;
  title: string | null;
  body: string;
  format: "markdown";
  creation_source: "manual" | "llm_scribe";
  source_llm_run_id: string | null;
  source_draft_hash: string | null;
  safety_warnings: Array<Record<string, unknown>>;
  last_published_at: string | null;
  publication_count: number;
  created_at: string;
  updated_at: string;
};

export type PublicSnippetsResponse = {
  snippets: PublicSnippet[];
  updated_at: string;
};

export type EntityKind = "pc" | "npc" | "creature" | "location" | "item" | "handout" | "faction" | "vehicle" | "generic";
export type EntityVisibility = "private" | "public_known";
export type CustomFieldType = "short_text" | "long_text" | "number" | "boolean" | "select" | "multi_select" | "radio" | "resource" | "image";
export type PartyLayout = "compact" | "standard" | "wide";

export type EntityRecord = {
  id: string;
  campaign_id: string;
  kind: EntityKind;
  name: string;
  display_name: string | null;
  visibility: EntityVisibility;
  portrait_asset_id: string | null;
  portrait_asset_name: string | null;
  portrait_asset_visibility: AssetVisibility | null;
  tags: string[];
  notes: string;
  field_values: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type EntitiesResponse = {
  entities: EntityRecord[];
  updated_at: string;
};

export type CustomFieldDefinition = {
  id: string;
  campaign_id: string;
  key: string;
  label: string;
  field_type: CustomFieldType;
  applies_to: EntityKind[];
  required: boolean;
  default_value: unknown | null;
  options: string[];
  public_by_default: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
};

export type CustomFieldsResponse = {
  fields: CustomFieldDefinition[];
  updated_at: string;
};

export type PartyMember = {
  id: string;
  entity_id: string;
  sort_order: number;
  entity: EntityRecord;
};

export type PartyField = {
  id: string;
  field_definition_id: string;
  sort_order: number;
  public_visible: boolean;
  field: CustomFieldDefinition;
};

export type PartyTrackerConfig = {
  id: string;
  campaign_id: string;
  layout: PartyLayout;
  members: PartyMember[];
  fields: PartyField[];
  updated_at: string;
};

export type PublicPartyField = {
  key: string;
  label: string;
  type: CustomFieldType;
  value: unknown;
};

export type PublicPartyCard = {
  entity_id: string;
  display_name: string;
  kind: EntityKind;
  portrait_asset_id: string | null;
  portrait_url: string | null;
  fields: PublicPartyField[];
};

export type CombatEncounterStatus = "active" | "paused" | "ended";
export type CombatantDisposition = "pc" | "ally" | "neutral" | "enemy" | "hazard" | "other";

export type CombatantRecord = {
  id: string;
  campaign_id: string;
  encounter_id: string;
  entity_id: string | null;
  token_id: string | null;
  name: string;
  disposition: CombatantDisposition;
  initiative: number | null;
  order_index: number;
  armor_class: number | null;
  hp_current: number | null;
  hp_max: number | null;
  hp_temp: number;
  conditions: Array<Record<string, unknown>>;
  public_status: Array<string | { label: string }>;
  notes: string;
  public_visible: boolean;
  is_defeated: boolean;
  portrait_asset_id: string | null;
  portrait_asset_name: string | null;
  created_at: string;
  updated_at: string;
};

export type CombatEncounter = {
  id: string;
  campaign_id: string;
  session_id: string | null;
  scene_id: string | null;
  title: string;
  status: CombatEncounterStatus;
  round: number;
  active_combatant_id: string | null;
  combatants: CombatantRecord[];
  created_at: string;
  updated_at: string;
};

export type CombatEncountersResponse = {
  encounters: CombatEncounter[];
  updated_at: string;
};

export type CombatantDeleteResult = {
  deleted_combatant_id: string;
  encounter: CombatEncounter;
};

export type SceneStagedDisplayMode =
  | "none"
  | "blackout"
  | "intermission"
  | "scene_title"
  | "active_map"
  | "initiative"
  | "public_snippet";

export type SceneEntityRole = "featured" | "supporting" | "location" | "clue" | "threat" | "other";

export type SceneContextConfig = {
  id: string;
  campaign_id: string;
  scene_id: string;
  active_encounter_id: string | null;
  staged_display_mode: SceneStagedDisplayMode;
  staged_public_snippet_id: string | null;
  created_at: string;
  updated_at: string;
};

export type SceneEntityLink = {
  id: string;
  campaign_id: string;
  scene_id: string;
  entity_id: string;
  role: SceneEntityRole;
  sort_order: number;
  notes: string;
  entity: EntityRecord;
  created_at: string;
  updated_at: string;
};

export type ScenePublicSnippetLink = {
  id: string;
  campaign_id: string;
  scene_id: string;
  public_snippet_id: string;
  sort_order: number;
  snippet: PublicSnippet;
  created_at: string;
  updated_at: string;
};

export type SceneContext = {
  scene: Scene;
  context: SceneContextConfig;
  active_map: SceneMap | null;
  notes: NoteSummary[];
  public_snippets: ScenePublicSnippetLink[];
  entities: SceneEntityLink[];
  active_encounter: CombatEncounter | null;
  updated_at: string;
};

export type PublicInitiativeCombatant = {
  id: string;
  name: string;
  disposition: CombatantDisposition;
  initiative: number | null;
  is_active: boolean;
  portrait_asset_id: string | null;
  portrait_url: string | null;
  public_status: Array<string | { label: string }>;
};

export type Asset = {
  id: string;
  campaign_id: string;
  kind: AssetKind;
  visibility: AssetVisibility;
  name: string;
  mime_type: string;
  byte_size: number;
  checksum: string;
  relative_path: string;
  original_filename: string | null;
  width: number | null;
  height: number | null;
  duration_ms: number | null;
  tags: string[];
  created_at: string;
  updated_at: string;
};

export type MapRecord = {
  id: string;
  campaign_id: string;
  asset_id: string;
  asset_name: string | null;
  asset_visibility: AssetVisibility | null;
  asset_url: string;
  name: string;
  width: number;
  height: number;
  grid_enabled: boolean;
  grid_size_px: number;
  grid_offset_x: number;
  grid_offset_y: number;
  grid_color: string;
  grid_opacity: number;
  created_at: string;
  updated_at: string;
};

export type AssetBatchUploadResult = {
  filename: string;
  asset: Asset | null;
  map: MapRecord | null;
  error: { code: string; message: string } | null;
};

export type AssetBatchUploadResponse = {
  results: AssetBatchUploadResult[];
};

export type BundledGrid = {
  cols: number;
  rows: number;
  feet_per_cell: number;
  px_per_cell: number;
  offset_x: number;
  offset_y: number;
};

export type BundledAssetPack = {
  id: string;
  title: string;
  asset_count: number;
  category_count: number;
  collections: string[];
};

export type BundledMap = {
  id: string;
  pack_id: string;
  title: string;
  collection: string;
  group: string;
  category_key: string;
  category_label: string;
  width: number;
  height: number;
  tags: string[];
  grid: BundledGrid;
};

export type BundledMapCreateResult = {
  asset: Asset;
  map: MapRecord;
  created_asset: boolean;
  created_map: boolean;
};

export type SceneMap = {
  id: string;
  campaign_id: string;
  scene_id: string;
  map_id: string;
  is_active: boolean;
  player_fit_mode: DisplayFitMode;
  player_grid_visible: boolean;
  map: MapRecord;
  created_at: string;
  updated_at: string;
};

export type MapRenderPayload = {
  type: "map";
  scene_map_id: string;
  map_id: string;
  asset_id: string;
  asset_url: string;
  mime_type?: string;
  width: number;
  height: number;
  title: string;
  fit_mode: DisplayFitMode;
  grid: GridSettings;
  fog?: FogPayload;
  tokens?: PublicMapToken[];
};

export type PlayerDisplayMode = "blackout" | "intermission" | "scene_title" | "image" | "map" | "text" | "party" | "initiative";

export type PlayerDisplayState = {
  mode: PlayerDisplayMode;
  title: string | null;
  subtitle: string | null;
  active_campaign_id: string | null;
  active_campaign_name: string | null;
  active_session_id: string | null;
  active_session_title: string | null;
  active_scene_id: string | null;
  active_scene_title: string | null;
  payload: Record<string, unknown>;
  revision: number;
  identify_revision: number;
  identify_until: string | null;
  updated_at: string;
};

export type WorkspaceWidget = {
  id: string;
  scope_type: string;
  scope_id: string | null;
  kind: string;
  title: string;
  x: number;
  y: number;
  width: number;
  height: number;
  z_index: number;
  locked: boolean;
  minimized: boolean;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type WorkspaceWidgetsResponse = {
  widgets: WorkspaceWidget[];
  updated_at: string;
};

export type WidgetPatch = Partial<
  Pick<WorkspaceWidget, "x" | "y" | "width" | "height" | "z_index" | "locked" | "minimized">
>;

export type StorageArtifact = {
  archive_name: string;
  byte_size: number;
  created_at: string;
  download_url: string | null;
};

export type StorageStatus = {
  profile: string;
  db_path: string;
  asset_dir: string;
  backup_dir: string;
  export_dir: string;
  db_size_bytes: number;
  asset_size_bytes: number;
  latest_backup: StorageArtifact | null;
  latest_export: StorageArtifact | null;
  schema_version: string | null;
  seed_version: string | null;
  expected_seed_version: string;
  private_demo_name_map_active: boolean;
};

export type SessionTranscriptEvent = {
  id: string;
  campaign_id: string;
  session_id: string;
  scene_id: string | null;
  corrects_event_id: string | null;
  event_type: "live_dm_note" | "correction";
  body: string;
  source: string;
  public_safe: boolean;
  order_index: number;
  created_at: string;
  updated_at: string;
  corrected_by_event_id: string | null;
};

export type TranscriptEventsResponse = {
  events: SessionTranscriptEvent[];
  projection: SessionTranscriptEvent[];
  updated_at: string;
};

export type LlmProviderProfile = {
  id: string;
  label: string;
  vendor: "openai" | "ollama" | "lmstudio" | "kobold" | "openrouter" | "custom";
  base_url: string;
  model_id: string;
  key_source: { type: "none" | "env"; ref: string | null };
  conformance_level: string;
  capabilities: Record<string, unknown>;
  last_probe_result: Record<string, unknown> | null;
  probed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type LlmProviderProfilesResponse = {
  profiles: LlmProviderProfile[];
  updated_at: string;
};

export type LlmContextPackage = {
  id: string;
  campaign_id: string;
  session_id: string | null;
  scene_id: string | null;
  task_kind: string;
  scope_kind: "campaign" | "session" | "scene";
  visibility_mode: "gm_private" | "public_safe";
  gm_instruction: string;
  source_refs: Array<Record<string, unknown>>;
  rendered_prompt: string;
  source_ref_hash: string;
  source_classes: string[];
  context_options: Record<string, unknown>;
  warnings: Array<Record<string, unknown>>;
  review_status: "unreviewed" | "reviewed";
  reviewed_at: string | null;
  reviewed_by: string | null;
  token_estimate: number;
  created_at: string;
  updated_at: string;
};

export type LlmRun = {
  id: string;
  campaign_id: string;
  session_id: string | null;
  provider_profile_id: string | null;
  context_package_id: string | null;
  parent_run_id: string | null;
  task_kind: string;
  status: "running" | "succeeded" | "failed" | "canceled";
  error_code: string | null;
  error_message: string | null;
  parse_failure_reason: string | null;
  repair_attempted: boolean;
  request_metadata: Record<string, unknown>;
  response_text: string | null;
  normalized_output: Record<string, unknown> | null;
  prompt_tokens_estimate: number | null;
  duration_ms: number | null;
  cancel_requested_at: string | null;
  created_at: string;
  updated_at: string;
};

export type SessionRecap = {
  id: string;
  campaign_id: string;
  session_id: string;
  source_llm_run_id: string | null;
  title: string;
  body_markdown: string;
  evidence_refs: Array<Record<string, unknown>>;
  public_safe: boolean;
  sensitivity_reason: string | null;
  created_at: string;
  updated_at: string;
};

export type SessionRecapsResponse = {
  recaps: SessionRecap[];
  updated_at: string;
};

export type MemoryCandidate = {
  id: string;
  campaign_id: string;
  session_id: string | null;
  source_llm_run_id: string | null;
  source_recap_id: string | null;
  source_planning_marker_id: string | null;
  source_proposal_option_id: string | null;
  status: "draft" | "edited" | "accepted" | "rejected";
  title: string;
  body: string;
  claim_strength: "directly_evidenced" | "strong_inference" | "weak_inference" | "gm_review_required";
  evidence_refs: Array<Record<string, unknown>>;
  validation_errors: string[];
  normalization_warnings: string[];
  normalization_warning_details: Array<Record<string, unknown>>;
  edited_from_candidate_id: string | null;
  applied_memory_entry_id: string | null;
  created_at: string;
  updated_at: string;
};

export type MemoryCandidatesResponse = {
  candidates: MemoryCandidate[];
  updated_at: string;
};

export type CampaignMemoryEntry = {
  id: string;
  campaign_id: string;
  session_id: string | null;
  source_candidate_id: string | null;
  source_planning_marker_id: string | null;
  source_proposal_option_id: string | null;
  title: string;
  body: string;
  evidence_refs: Array<Record<string, unknown>>;
  tags: string[];
  public_safe: boolean;
  sensitivity_reason: string | null;
  created_at: string;
  updated_at: string;
};

export type CampaignMemoryEntriesResponse = {
  entries: CampaignMemoryEntry[];
  updated_at: string;
};

export type BuildRecapResult = {
  run: LlmRun;
  bundle: {
    privateRecap?: { title?: string; bodyMarkdown?: string; keyMoments?: Array<Record<string, unknown>> };
    memoryCandidateDrafts?: Array<Record<string, unknown>>;
    continuityWarnings?: Array<Record<string, unknown>>;
    unresolvedThreads?: string[];
  };
  candidates: MemoryCandidate[];
  rejected_drafts: Array<Record<string, unknown>>;
  verification?: Record<string, unknown> | null;
  verification_run?: LlmRun | null;
};

export type ProposalOption = {
  id: string;
  proposal_set_id: string;
  option_index: number;
  stable_option_key: string;
  title: string;
  summary: string;
  body: string;
  consequences: string;
  reveals: string;
  stays_hidden: string;
  proposed_delta: Record<string, unknown>;
  planning_marker_text: string;
  status: "proposed" | "selected" | "rejected" | "saved_for_later" | "superseded" | "canonized";
  selected_at: string | null;
  canonized_at: string | null;
  active_planning_marker_id: string | null;
  created_at: string;
  updated_at: string;
};

export type PlanningMarker = {
  id: string;
  campaign_id: string;
  session_id: string | null;
  scene_id: string | null;
  source_proposal_option_id: string | null;
  scope_kind: "campaign" | "session" | "scene";
  status: "active" | "expired" | "superseded" | "canonized" | "discarded";
  title: string;
  marker_text: string;
  original_marker_text: string | null;
  lint_warnings: string[];
  provenance: Record<string, unknown>;
  edited_at: string | null;
  edited_from_source: boolean;
  expires_at: string | null;
  canonized_at: string | null;
  canon_memory_entry_id: string | null;
  created_at: string;
  updated_at: string;
};

export type ProposalSetSummary = {
  id: string;
  campaign_id: string;
  session_id: string | null;
  scene_id: string | null;
  llm_run_id: string | null;
  context_package_id: string | null;
  task_kind: string;
  scope_kind: "campaign" | "session" | "scene";
  title: string;
  status: string;
  option_count: number;
  selected_count: number;
  active_marker_count: number;
  rejected_count: number;
  saved_count: number;
  has_warnings: boolean;
  warning_count: number;
  degraded: boolean;
  repair_attempted: boolean;
  created_at: string;
  updated_at: string;
};

export type ProposalSetsResponse = {
  proposal_sets: ProposalSetSummary[];
  updated_at: string;
};

export type ProposalSetDetail = {
  proposal_set: ProposalSetSummary;
  options: ProposalOption[];
  planning_markers: PlanningMarker[];
  run: LlmRun | null;
  context_package: LlmContextPackage | null;
  normalization_warnings: Array<Record<string, unknown>>;
};

export type BuildBranchResult = {
  run: LlmRun;
  proposal_set: ProposalSetDetail | null;
  rejected_options: Array<Record<string, unknown>>;
  warnings: Array<Record<string, unknown>>;
};

export type PlayerSafeRecapResult = {
  run: LlmRun;
  public_snippet_draft: { title: string; bodyMarkdown: string };
  source_draft_hash: string;
  warnings: Array<Record<string, unknown>>;
};

export type PublicSafetyWarning = {
  code: string;
  severity: "low" | "medium" | "high" | string;
  message: string;
  matched_text?: string;
};

export type PublicSafetyWarningScanResult = {
  warnings: PublicSafetyWarning[];
  content_hash: string;
  ack_required: boolean;
};

export type PlanningMarkersResponse = {
  planning_markers: PlanningMarker[];
  updated_at: string;
};

export type EntityAlias = {
  id: string;
  campaign_id: string;
  entity_id: string | null;
  alias_text: string;
  normalized_alias: string;
  language: string | null;
  source: string;
  source_ref: Record<string, unknown> | null;
  confidence: string;
  created_at: string;
  updated_at: string;
};

export type RecallResult = {
  query: string;
  expanded_terms: string[];
  hits: Array<{
    card_id?: string | null;
    source_kind: string;
    source_id: string;
    source_revision: string;
    source_hash?: string | null;
    card_variant?: string | null;
    title: string;
    excerpt: string;
    lane: string;
    visibility: string;
    review_status?: string | null;
    source_status?: string | null;
    claim_role?: string | null;
    score: number;
    match?: { strategy?: string; matched_terms?: string[] } | Record<string, unknown> | null;
    admissibility?: string | null;
  }>;
  policy?: Record<string, unknown>;
  summary?: Record<string, unknown>;
  evidenceCoverage?: "none" | "weak" | "partial" | "sufficient" | string;
  trace?: Record<string, unknown> | null;
  assembly?: Array<Record<string, unknown>>;
};
