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
