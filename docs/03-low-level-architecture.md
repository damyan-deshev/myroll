# Myroll Low-Level Architecture

Date: 2026-05-02
Status: Draft 1

This document defines concrete data shapes, modules, events, operations, and implementation rules for the MVP architecture.

The examples use TypeScript-style types. They are implementation guidance, not final generated code.

## 0. Current Backend Foundation

The current implementation starts with a local backend foundation:

```text
SQLite = durable source of truth
FastAPI = local control plane
Filesystem = asset blob storage
Browser = UI/runtime/cache
```

Backend foundation requirements:
- FastAPI app.
- SQLite database at `data/myroll.dev.sqlite3` by default.
- Alembic migrations from day one.
- Pre-migration backup for existing non-empty DB files.
- Idempotent transactional demo seed.
- Local-only bind to `127.0.0.1` by default.
- Campaign/session/scene creation APIs.
- Singleton active runtime context.
- Runtime activation action endpoints.
- Standard API error envelope.

SQLite connections must apply these PRAGMAs through a SQLAlchemy connection event:

```text
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
```

All API timestamps must be timezone-aware UTC ISO-8601 strings with trailing `Z`. Naive datetimes are forbidden at API boundaries.

### 0.1 Runtime Context

The backend owns the active local runtime context.

```ts
type AppRuntime = {
  id: "runtime";
  activeCampaignId?: CampaignId;
  activeSessionId?: SessionId;
  activeSceneId?: SceneId;
  updatedAt: IsoDateTime;
};
```

The database must enforce `id = "runtime"` with a primary key and check constraint.

Activation is command-based:

```text
POST /api/runtime/activate-campaign
POST /api/runtime/activate-session
POST /api/runtime/activate-scene
POST /api/runtime/clear
```

Each activation returns the current runtime response, including IDs and labels for UI bootstrap.

Scene activation is private:
- `POST /api/runtime/activate-scene` updates `app_runtime` only;
- it does not mutate `player_display_runtime`;
- public display changes from scene orchestration happen only through `POST /api/scenes/{sceneId}/publish-staged-display`.

### 0.1a Scene Context Staging

Slice 12 adds a private scene orchestration layer.

```ts
type SceneStagedDisplayMode =
  | "none"
  | "blackout"
  | "intermission"
  | "scene_title"
  | "active_map"
  | "initiative"
  | "public_snippet";

type SceneContext = {
  id: string;
  campaignId: CampaignId;
  sceneId: SceneId;
  activeEncounterId?: string;
  stagedDisplayMode: SceneStagedDisplayMode;
  stagedPublicSnippetId?: string;
  createdAt: IsoDateTime;
  updatedAt: IsoDateTime;
};

type SceneEntityLink = {
  id: string;
  campaignId: CampaignId;
  sceneId: SceneId;
  entityId: EntityId;
  role: "featured" | "supporting" | "location" | "clue" | "threat" | "other";
  sortOrder: number;
  notes?: string;
  createdAt: IsoDateTime;
  updatedAt: IsoDateTime;
};

type ScenePublicSnippetLink = {
  id: string;
  campaignId: CampaignId;
  sceneId: SceneId;
  publicSnippetId: string;
  sortOrder: number;
  createdAt: IsoDateTime;
  updatedAt: IsoDateTime;
};
```

Schema rules:
- `scene_contexts.scene_id` is unique;
- `scene_entity_links` is unique on `(scene_id, entity_id)`;
- `scene_public_snippet_links` is unique on `(scene_id, public_snippet_id)`;
- staged display mode is constrained to the listed string values.

Private GM APIs:

```text
GET    /api/scenes/{scene_id}/context
PATCH  /api/scenes/{scene_id}/context
POST   /api/scenes/{scene_id}/entity-links
DELETE /api/scene-entity-links/{link_id}
POST   /api/scenes/{scene_id}/public-snippet-links
DELETE /api/scene-public-snippet-links/{link_id}
POST   /api/scenes/{scene_id}/publish-staged-display
```

Validation:
- `PATCH /context` may save partial staging;
- `active_encounter_id` must belong to the same campaign and scene;
- `staged_public_snippet_id` must belong to the same campaign and be explicitly linked to the scene;
- `publish-staged-display` rejects `none`;
- `public_snippet` publish requires a linked staged snippet;
- `initiative` publish requires an active encounter;
- `active_map` publish requires the scene's active scene map.

Publish behavior:
- `publish-staged-display` mutates only `player_display_runtime`;
- it reuses the existing map, initiative, snippet, scene-title, intermission, and blackout display paths;
- scene context responses are GM-private and are never consumed by `/player`.

### 0.2 API Error Envelope

Public API errors use:

```json
{
  "error": {
    "code": "campaign_not_found",
    "message": "Campaign not found"
  }
}
```

Validation errors use the same envelope with `code = "validation_error"` and a `details` array.

### 0.3 Workspace Widgets

The GM cockpit layout is persisted by the backend.

Current frontend routing:

```text
/gm           docked overview
/gm/map       map/fog/token workbench
/gm/library   assets, notes, snippets
/gm/actors    party/entities
/gm/combat    encounters/initiative
/gm/scene     scene context/staging
/gm/floating  persistent floating widget canvas
```

```ts
type WorkspaceWidget = {
  id: string;
  scopeType: "global" | "campaign" | "scene";
  scopeId?: string;
  kind: string;
  title: string;
  x: number;
  y: number;
  width: number;
  height: number;
  zIndex: number;
  locked: boolean;
  minimized: boolean;
  config: Record<string, unknown>;
  createdAt: IsoDateTime;
  updatedAt: IsoDateTime;
};
```

Slice 3 uses `scopeType = "global"` and no `scopeId`. The same shape is reserved for future campaign and scene layouts.

Rules:
- `config_json` in SQLite must always decode to a JSON object.
- API responses expose parsed `config`, not raw JSON text.
- Default widgets are deterministic and seeded once.
- Moving or resizing a widget must not overwrite unrelated layout fields.
- Frontend drag/resize updates local UI immediately and persists only on stop.
- Failed layout PATCH keeps the local position and marks the widget unsaved.
- Browser storage must not become the source of truth for workspace layout.
- Default laptop workflows should use focused surfaces; `/gm/floating` preserves the draggable canvas for advanced custom layouts.

### 0.4 Player Display Runtime

The backend owns the active public display state.

```ts
type PlayerDisplayRuntime = {
  id: "player_display";
  mode: "blackout" | "intermission" | "scene_title" | "image" | "map" | "text" | "party" | "initiative";
  activeCampaignId?: CampaignId;
  activeSessionId?: SessionId;
  activeSceneId?: SceneId;
  title?: string;
  subtitle?: string;
  payload: Record<string, unknown>;
  revision: number;
  identifyRevision: number;
  identifyUntil?: IsoDateTime;
  updatedAt: IsoDateTime;
};
```

Rules:
- the database constrains `id = "player_display"`;
- the database constrains valid `mode` values;
- `revision` increments only on public content state changes;
- `identifyRevision` increments only on identify;
- identify does not change mode/title/subtitle;
- `show-scene-title` may read `app_runtime.activeSceneId`, but never mutates `app_runtime`;
- `show-image` may publish only `public_displayable` image assets;
- image payloads store public-safe metadata and a relative `/api/player-display/assets/{assetId}/blob` URL;
- `show-map` may read the active runtime scene when no scene map is provided, but never mutates `app_runtime`;
- `show-map` never activates or deactivates scene maps;
- map payloads store public-safe metadata, square grid render settings, and a relative `/api/player-display/assets/{assetId}/blob` URL;
- `show-snippet` builds text payloads only from `public_snippets`, never from private note bodies;
- `show-party` builds party payloads only through the party sanitizer, never from raw entity records;
- `show-initiative` builds initiative payloads only through the combat sanitizer, never from raw combat/entity/token records;
- public initiative visibility is controlled only by `combatants.public_visible`;
- `/player` fetches only `GET /api/player-display` and optional health diagnostics;
- `/player` image/map/token/party/initiative bytes come only from the active public display blob endpoint;
- transport messages contain heartbeat/revision notification only, never display payload content;
- after a refetch failure, `/player` keeps the last successful public state unless no state has ever loaded.

## 1. Core Type Rules

### 1.1 IDs

Use branded string IDs for domain safety.

```ts
type Brand<T, Name extends string> = T & { readonly __brand: Name };

type CampaignId = Brand<string, "CampaignId">;
type SessionId = Brand<string, "SessionId">;
type SceneId = Brand<string, "SceneId">;
type EntityId = Brand<string, "EntityId">;
type AssetId = Brand<string, "AssetId">;
type MapId = Brand<string, "MapId">;
type TokenId = Brand<string, "TokenId">;
type FogMaskId = Brand<string, "FogMaskId">;
type NoteId = Brand<string, "NoteId">;
type PublicSnippetId = Brand<string, "PublicSnippetId">;
type LayoutId = Brand<string, "LayoutId">;
type DisplayStateId = Brand<string, "DisplayStateId">;
```

IDs should be generated locally with `crypto.randomUUID()` unless a future sync model requires a different ID scheme.

### 1.2 Timestamps

Use ISO strings at the persistence boundary.

```ts
type IsoDateTime = string;
```

Inside logic, parse to `Date` only when necessary.

### 1.3 Versioning

Durable records should include `schemaVersion`.

```ts
type VersionedRecord = {
  schemaVersion: number;
  createdAt: IsoDateTime;
  updatedAt: IsoDateTime;
};
```

This matters because local-first data migrations become unavoidable quickly.

## 2. Campaign Domain

### 2.1 Campaign

```ts
type Campaign = VersionedRecord & {
  id: CampaignId;
  name: string;
  description?: string;
  activeSessionId?: SessionId;
  activeSceneId?: SceneId;
  settings: CampaignSettings;
};

type CampaignSettings = {
  defaultDisplayMode: PlayerDisplayMode;
  defaultMapFitMode: DisplayFitMode;
  defaultPrivateByDefault: true;
  systemLabel?: string;
};
```

### 2.2 Session

```ts
type Session = VersionedRecord & {
  id: SessionId;
  campaignId: CampaignId;
  title: string;
  startsAt?: IsoDateTime;
  endedAt?: IsoDateTime;
  sceneIds: SceneId[];
  notes?: string;
};
```

### 2.3 Scene

```ts
type Scene = VersionedRecord & {
  id: SceneId;
  campaignId: CampaignId;
  sessionId?: SessionId;
  title: string;
  summary?: string;
  linkedMapId?: MapId;
  linkedNoteIds: NoteId[];
  linkedEntityIds: EntityId[];
  linkedAssetIds: AssetId[];
  displayPreset?: SceneDisplayPreset;
  defaultLayoutId?: LayoutId;
  runtime: SceneRuntimeState;
};

type SceneRuntimeState = {
  activeCombatId?: string;
  activeClockIds: string[];
  revealedFactIds: string[];
  hiddenFactIds: string[];
  lastActivatedAt?: IsoDateTime;
};

type SceneDisplayPreset = {
  mode: PlayerDisplayMode;
  sourceId?: string;
  blackoutOnActivation?: boolean;
  mapView?: Partial<PlayerMapViewState>;
  overlay?: PublicDisplayOverlay;
};
```

MVP can store `SceneDisplayPreset` as a light object and expand later.

Current implementation stores live orchestration state in `SceneContext` rather than embedding it in `Scene`. This keeps private GM focus, linked entities/snippets, active encounter, and staged display metadata separate from player display state.

## 3. Asset Domain

### 3.1 Asset

```ts
type AssetKind =
  | "map_image"
  | "handout_image"
  | "npc_portrait"
  | "item_image"
  | "scene_image"
  | "token_image"
  | "audio"
  | "markdown"
  | "pdf"
  | "other";

type AssetVisibility = "private" | "public_displayable";

type Asset = VersionedRecord & {
  id: AssetId;
  campaignId: CampaignId;
  kind: AssetKind;
  visibility: AssetVisibility;
  name: string;
  mimeType: string;
  byteSize: number;
  storageKey: string;
  originalFileName?: string;
  width?: number;
  height?: number;
  durationMs?: number;
  checksum?: string;
  tags: string[];
};
```

Current implementation includes `token_image` for reusable monster/NPC token art. Scene-map portrait tokens can reference `token_image` and other validated image assets, but public serving still requires the asset to be referenced by the active public display payload.

### 3.2 Asset Storage

Current implementation:
- SQLite stores asset metadata.
- Filesystem storage under `data/assets/` stores imported blobs.
- `relativePath` is a managed storage key under `asset_dir`, never an external absolute path.
- Browser upload copies bytes into managed storage.
- Server-path import was removed after security review; uploads are the supported user-consent boundary.
- Supported Slice 5 formats are PNG, JPEG, and WebP.
- Import limits are 25 MB and 50 decoded megapixels.
- Pillow validation derives real MIME type, extension, width, and height.
- Decompression bomb warnings/errors are rejected.
- Blob writes use a temp file before the final content-addressed path.

Implementation abstraction:

```ts
interface AssetStore {
  putFile(file: File, meta: CreateAssetInput): Promise<Asset>;
  getBlob(assetId: AssetId): Promise<Blob>;
  getObjectUrl(assetId: AssetId): Promise<string>;
  revokeObjectUrl(url: string): void;
  delete(assetId: AssetId): Promise<void>;
}
```

Public display image payloads reference asset IDs and relative public blob URLs. They must not store object URLs, absolute filesystem paths, or private asset metadata.

### 3.3 Generated Battle Map Pack Contract

Generated battle-map packs are external input artifacts, not runtime storage. The production-facing pack is the curated export, not the raw ComfyUI generation tree:

```text
manifest.json
taxonomy.json
README.md
HANDOFF.md
assets/battle-maps/fantasy/<collection>/<group>/<category>/
  category.json
  images/*.webp
curation/
  curation_decisions.json
  rejections.json
  source_inventory.json
  contact_sheets/
```

`manifest.json` lists accepted app-facing assets. Each accepted asset carries its own grid contract, and each category directory also has a `category.json` summary for tactical scale and browsing:

```ts
type GeneratedBattleMapPackManifest = {
  schemaVersion: 1;
  packId: "myroll_battle_maps_production_v1";
  title: string;
  sourcePacks: string[];
  sourceAssetCount: number;
  assetCount: number;
  rejectedCount: number;
  categories: GeneratedMapCategorySummary[];
  assets: GeneratedMapAssetManifestEntry[];
};

type GeneratedMapCategorySummary = {
  categoryKey: string;
  label: string;
  collection: "core" | "diverse" | "weird";
  group: string;
  slug: string;
  categoryPath: string;
  sourceCount: number;
  acceptedCount: number;
  rejectedCount: number;
};

type GeneratedMapCategoryManifest = {
  schemaVersion: 1;
  categoryKey: string;
  label: string;
  theme: "fantasy";
  collection: "core" | "diverse" | "weird";
  group: string;
  slug: string;
  grid: GeneratedMapGrid;
  assets: GeneratedMapCategoryAssetEntry[];
  sourcePacks: string[];
  assetCount: number;
};

type GeneratedMapCategoryAssetEntry = {
  id: string;
  title: string;
  file: string; // relative to the category directory, usually images/*.webp
  sourceDecisionKey: string;
};

type GeneratedMapAssetManifestEntry = {
  id: string;
  title: string;
  file: string;
  role: "battle_map";
  format: "webp";
  theme: "fantasy";
  collection: "core" | "diverse" | "weird";
  categoryKey: string;
  categoryLabel: string;
  categoryPath: string;
  grid: GeneratedMapGrid;
  image: {
    width: number;
    height: number;
    gridless: true;
  };
  checksum: {
    sha256: string;
  };
  tags: string[];
  curation: {
    status: "accepted";
    decisionKey: string;
    reviewedBy: string;
    reviewedAt: string;
  };
  provenance: {
    sourcePackId: string;
    sourceAssetKey: string;
    sourceSlot: number;
    sourceName: string;
    sourceWebp?: string;
    sourcePng?: string;
    seed?: number;
    prompt?: string;
  };
};

type GeneratedMapGrid = {
  type: "square";
  cols: number;
  rows: number;
  feetPerCell: number;
  pxPerCell: number;
  offsetX: number;
  offsetY: number;
};

type GeneratedMapTaxonomy = {
  schemaVersion: 1;
  theme: "fantasy";
  collections: Record<
    "core" | "diverse" | "weird",
    {
      groups: Record<
        string,
        {
          categories: Array<{
            categoryKey: string;
            label: string;
            slug: string;
            assetCount: number;
            path: string;
          }>;
        }
      >;
    }
  >;
};
```

Current bundled-pack import rules:
- import only curated production `manifest.json`, not raw source `pack.json` files;
- bundled static packs should be auto-registered from a configured app resource directory at startup, not manually imported by installed users;
- the first production pack may be committed as an immutable bundled asset version to avoid separate artifact-storage infrastructure;
- if pack size or update frequency becomes painful, move bundled packs to Git LFS, GitHub release assets, or another artifact store without changing the manifest/catalog contract;
- resolve every `asset.file` relative to the production pack root and reject absolute paths or path traversal;
- resolve category-local `category.json` asset files relative to their category directory;
- use `taxonomy.json` or derived manifest data for browsing, not as the validation source of truth;
- import generated maps through the existing asset validation and managed-storage pipeline;
- reject unsupported MIME types and files whose decoded dimensions do not match `grid.cols * grid.pxPerCell` by `grid.rows * grid.pxPerCell`;
- create `map_image` assets first, then create campaign map records with square grid calibration from the category contract;
- preserve `categoryKey`, `collection`, generated asset ID, prompt/provenance metadata, and curation status in map/asset metadata for filtering and later regeneration;
- do not trust the diffusion prompt, filename, or contact sheet for scale;
- keep generated images gridless and render the tactical grid live from `GridSettings`.

### 3.4 User-Facing Asset Import Contract

The bundled catalog, curated battle-map pack importer, and the user's general asset import flow must stay separate.

Bundled catalog:
- read-only static asset packs shipped with the app or supplied to development through a configured bundle directory;
- auto-registered on startup so installed users do not perform a manual import step;
- validates manifest/category/checksum/dimension metadata before exposing entries in the GM browser;
- does not treat external pack files as generic public assets.

Pack importer:
- local development/admin workflow;
- reads an explicitly configured manifest path;
- validates checksums, relative paths, category metadata, and decoded image dimensions;
- creates or refreshes bundled catalog entries after validation;
- never serves files directly from the external pack directory.

User-facing import:
- browser upload remains the current supported consent boundary;
- multi-file upload can batch maps, handouts, portraits, and token art;
- a future directory picker is acceptable only if the user explicitly selects it and every discovered file still goes through backend validation;
- arbitrary `source_path` strings must not be accepted by public HTTP APIs;
- batch defaults may set `kind`, `visibility`, and tags, but backend validation remains authoritative for MIME type, extension, dimensions, checksum, and storage path.

Campaign use of bundled entries:
- when a GM adds a bundled map to a campaign, Myroll creates a campaign-scoped map record using the bundled entry's title, tags, provenance, and grid contract;
- the current implementation copies the referenced WebP into managed content-addressed storage on add;
- deterministic IDs from `campaign_id + pack_id + bundled_asset_id` make repeated adds idempotent for the same campaign;
- `/api/player-display/assets/{asset_id}/blob` remains active-display scoped and does not become a generic bundled asset server;
- export behavior remains simple for v1 because copied managed blobs are ordinary campaign assets.

## 4. Player Display Domain

### 4.1 Modes

```ts
type PlayerDisplayMode =
  | "blackout"
  | "map"
  | "image"
  | "handout"
  | "text"
  | "npc_portrait"
  | "initiative"
  | "timer"
  | "scene_title"
  | "mood_board"
  | "intermission"
  | "custom_scene";

type DisplayFitMode = "fit" | "fill" | "stretch" | "actual_size";
```

### 4.2 PlayerDisplayState

```ts
type PlayerDisplayState = VersionedRecord & {
  id: DisplayStateId;
  campaignId: CampaignId;
  sceneId?: SceneId;
  mode: PlayerDisplayMode;
  sourceId?: string;
  title?: string;
  blackout: boolean;
  payload: PublicDisplayPayload;
  layout: PlayerDisplayLayout;
  safety: DisplaySafety;
};

type PlayerDisplayLayout = {
  fitMode: DisplayFitMode;
  background: "black" | "blurred" | "solid" | "transparent";
  showSceneTitle?: boolean;
  overlays: PublicDisplayOverlay[];
};

type PublicDisplayOverlay =
  | { type: "initiative"; position: "top" | "bottom" | "side" }
  | { type: "current_combatant"; position: "top-left" | "top-right" | "bottom-left" | "bottom-right" }
  | { type: "timer"; position: "top" | "center" | "bottom" }
  | { type: "caption"; text: string; position: "top" | "center" | "bottom" };

type DisplaySafety = {
  requiresPreview: boolean;
  staged: boolean;
  createdByCommand: string;
  previousStateId?: DisplayStateId;
};
```

### 4.3 PublicDisplayPayload

```ts
type PublicDisplayPayload =
  | { type: "blackout"; message?: string }
  | { type: "intermission"; title?: string; subtitle?: string }
  | { type: "map"; map: PlayerMapPayload }
  | { type: "image"; assetId: AssetId; alt?: string; caption?: string }
  | { type: "handout"; assetId?: AssetId; title?: string; body?: string }
  | { type: "text"; title?: string; body: string }
  | { type: "npc_portrait"; entityId: EntityId; assetId?: AssetId; name?: string; caption?: string }
  | { type: "initiative"; initiative: PublicInitiativePayload }
  | { type: "timer"; timer: PublicTimerPayload }
  | { type: "scene_title"; title: string; subtitle?: string }
  | { type: "mood_board"; assets: AssetId[]; title?: string };
```

### 4.4 Display Connection State

```ts
type DisplayConnectionStatus =
  | "not_open"
  | "opening"
  | "connected"
  | "stale"
  | "disconnected";

type PlayerDisplayConnection = {
  id: string;
  campaignId: CampaignId;
  windowName: string;
  status: DisplayConnectionStatus;
  transportKind?: DisplayTransportKind;
  lastHeartbeatAt?: IsoDateTime;
  lastAckStateId?: DisplayStateId;
  userAgent?: string;
};

type DisplayTransportKind = "postMessage" | "broadcastChannel" | "storageSync";

type DisplayTransportCapabilities = {
  kind: DisplayTransportKind;
  supportsTransferables: boolean;
  requiresWindowReference: boolean;
  crossesStoragePartition: boolean;
};
```

### 4.5 Display Operations

```ts
interface DisplayManager {
  openPlayerWindow(): Promise<void>;
  reconnect(): Promise<void>;
  identifyDisplay(): Promise<void>;
  publish(state: PlayerDisplayState): Promise<void>;
  stage(state: PlayerDisplayState): Promise<void>;
  publishStaged(): Promise<void>;
  blackout(reason?: string): Promise<void>;
  undo(): Promise<void>;
  getActiveState(): Promise<PlayerDisplayState>;
  getStatus(): PlayerDisplayStatusViewModel;
}
```

`blackout()` must be immediate and should not delete display history.

### 4.6 Display Status View Model

```ts
type PlayerDisplayStatusViewModel = {
  connectionStatus: DisplayConnectionStatus;
  mode: PlayerDisplayMode;
  sourceLabel?: string;
  sceneTitle?: string;
  fogEnabled?: boolean;
  publicTokenCount?: number;
  hiddenTokenCount?: number;
  fullscreenKnown?: boolean;
  lastChangedAt?: IsoDateTime;
  canUndo: boolean;
  stagedState?: {
    mode: PlayerDisplayMode;
    sourceLabel?: string;
  };
};
```

This is what the always-visible GM status panel renders.

## 5. Display Messaging

### 5.1 Transport Selection

Display communication uses a layered transport.

Preferred order:
1. `postMessage` when `/gm` opened `/player` and has a live `WindowProxy`.
2. `BroadcastChannel` when both windows are same-origin and same storage partition.
3. `storageSync` as a slow reconnect fallback via persisted active display state.

`BroadcastChannel` is not enough by itself because private/incognito windows, separate browser profiles, and storage partition boundaries can prevent delivery. `postMessage` supports transferables such as `ArrayBuffer` and `ImageBitmap`, but every message must validate `origin`, `source`, app instance ID, and campaign ID.

Manual `/player` windows opened in a separate incognito/private profile are not guaranteed to work in MVP because they may have neither shared storage nor an opener `WindowProxy`. Supporting that reliably requires a different pairing transport, such as a local host process or server-mediated channel.

### 5.2 BroadcastChannel

Channel:

```ts
const channelName = `myroll:${campaignId}:display`;
```

### 5.3 Message Types

```ts
type DisplayMessage =
  | DisplayHelloMessage
  | DisplayHeartbeatMessage
  | DisplayStatePublishedMessage
  | DisplayBlackoutMessage
  | DisplayIdentifyMessage
  | DisplayRequestSyncMessage
  | DisplayFogOperationMessage
  | DisplayFogSnapshotMessage
  | DisplayAckMessage;

type DisplayHelloMessage = {
  type: "DISPLAY_HELLO";
  displayWindowId: string;
  sentAt: IsoDateTime;
};

type DisplayHeartbeatMessage = {
  type: "DISPLAY_HEARTBEAT";
  displayWindowId: string;
  activeStateId?: DisplayStateId;
  sentAt: IsoDateTime;
};

type DisplayStatePublishedMessage = {
  type: "DISPLAY_STATE_PUBLISHED";
  state: PlayerDisplayState;
  sentAt: IsoDateTime;
};

type DisplayBlackoutMessage = {
  type: "DISPLAY_BLACKOUT";
  state: PlayerDisplayState;
  sentAt: IsoDateTime;
};

type DisplayIdentifyMessage = {
  type: "DISPLAY_IDENTIFY";
  label: string;
  durationMs: number;
  sentAt: IsoDateTime;
};

type DisplayRequestSyncMessage = {
  type: "DISPLAY_REQUEST_SYNC";
  displayWindowId: string;
  sentAt: IsoDateTime;
};

type DisplayAckMessage = {
  type: "DISPLAY_ACK";
  displayWindowId: string;
  stateId: DisplayStateId;
  sentAt: IsoDateTime;
};

type DisplayFogOperationMessage = {
  type: "DISPLAY_FOG_OPERATION";
  campaignId: CampaignId;
  sceneId: SceneId;
  mapId: MapId;
  operation: FogOperation;
  sequence: number;
  sentAt: IsoDateTime;
};

type DisplayFogSnapshotMessage = {
  type: "DISPLAY_FOG_SNAPSHOT";
  campaignId: CampaignId;
  sceneId: SceneId;
  mapId: MapId;
  fogMaskId: FogMaskId;
  snapshot: FogSnapshotTransport;
  sequence: number;
  sentAt: IsoDateTime;
};

type FogSnapshotTransport =
  | { kind: "asset_ref"; assetId: AssetId }
  | { kind: "array_buffer"; mimeType: "image/png" | "image/webp"; bytes: ArrayBuffer }
  | { kind: "image_bitmap"; bitmap: ImageBitmap };
```

### 5.4 postMessage Rules

When using `window.postMessage()`:
- always set exact `targetOrigin`;
- validate `event.origin`;
- validate `event.source` against the known player window or opener;
- validate message shape;
- validate `campaignId`;
- reject unknown `appInstanceId` if implemented;
- use transferables for large binary snapshots;
- never use `*` as target origin in production.

Example conceptual send:

```ts
playerWindow.postMessage(message, window.location.origin, transferables);
```

### 5.5 Reconnect Logic

On `/player` load:

```text
1. Create displayWindowId.
2. Detect opener/postMessage availability.
3. Open BroadcastChannel if available.
4. Send DISPLAY_HELLO through all available transports.
5. Read active PlayerDisplayState from IndexedDB if available.
6. Render active state if present, otherwise blackout.
7. Send DISPLAY_REQUEST_SYNC.
8. Start heartbeat every 1000-2000ms.
```

On `/gm`:

```text
1. Listen for DISPLAY_HELLO.
2. Mark connection connected.
3. Broadcast active state.
4. Track heartbeats.
5. Mark stale if heartbeat older than threshold.
```

Suggested stale threshold: 5000ms.

## 6. Map Domain

### 6.1 MapAsset

```ts
type MapAsset = VersionedRecord & {
  id: MapId;
  campaignId: CampaignId;
  assetId: AssetId;
  name: string;
  width: number;
  height: number;
  defaultGrid?: GridSettings;
  metadata: Record<string, unknown>;
};

type GridSettings = {
  enabled: boolean;
  type: "square" | "hex";
  sizePx: number;
  offsetX: number;
  offsetY: number;
  color: string;
  opacity: number;
};
```

For generated gridless maps, calibration should be expressed by `sizePx`, `offsetX`, and `offsetY`. The GM UI may describe this as resizing and nudging the map/grid, but persistence should not move or rewrite the underlying image. Fog masks and tokens continue to use the original intrinsic map pixel coordinate space.

Current Slice 6 persistence shape:

```ts
type CampaignMapRecord = {
  id: MapId;
  campaignId: CampaignId;
  assetId: AssetId;
  name: string;
  width: number;
  height: number;
  gridEnabled: boolean;
  gridSizePx: number;      // 4..500
  gridOffsetX: number;     // finite
  gridOffsetY: number;     // finite
  gridColor: string;       // normalized #RRGGBB
  gridOpacity: number;     // 0..1
  createdAt: IsoDateTime;
  updatedAt: IsoDateTime;
};

type SceneMapRecord = {
  id: string;
  campaignId: CampaignId;
  sceneId: SceneId;
  mapId: MapId;
  isActive: boolean;
  playerFitMode: DisplayFitMode;
  playerGridVisible: boolean;
  createdAt: IsoDateTime;
  updatedAt: IsoDateTime;
};
```

Database invariant:

```sql
CREATE UNIQUE INDEX uq_scene_maps_one_active_per_scene
ON scene_maps(scene_id)
WHERE is_active = 1;
```

Activation must clear the old active row and set the selected active row inside one transaction.

### 6.1a Grid Calibration Controls

The current numeric grid fields are sufficient for storage, but the GM map workbench needs faster controls for live use:

```ts
type GridNudgeMode = "fine" | "cell_fraction" | "cell";

type GridCalibrationCommand =
  | { type: "resize_grid"; deltaPx: number; mode: GridNudgeMode }
  | { type: "set_grid_size"; sizePx: number }
  | { type: "nudge_grid"; dx: number; dy: number; mode: GridNudgeMode }
  | { type: "set_grid_offset"; offsetX: number; offsetY: number }
  | { type: "reset_grid_size" }
  | { type: "reset_grid_offset" };
```

Rules:
- grid-size controls update `gridSizePx` within the existing valid bounds;
- four-direction nudge buttons and keyboard shortcuts update `gridOffsetX` and `gridOffsetY`;
- fine nudges should be small pixel deltas, while coarse nudges may use fractions of `gridSizePx`;
- grid size and offset changes must be previewed immediately and persisted through the existing map grid update path;
- player grid visibility remains a scene-map setting and does not imply that the GM calibration grid is public;
- if a later feature adds image framing/pan, keep it separate from tactical grid calibration and from fog/token coordinates.

### 6.2 Map Scene State

```ts
type MapSceneState = VersionedRecord & {
  id: string;
  campaignId: CampaignId;
  sceneId: SceneId;
  mapId: MapId;
  fogMaskId?: FogMaskId;
  tokenIds: TokenId[];
  layerIds: string[];
  gmView: GMMapViewState;
  playerView: PlayerMapViewState;
};

type GMMapViewState = {
  zoom: number;
  panX: number;
  panY: number;
  selectedLayerId?: string;
  selectedTokenIds: TokenId[];
  showPrivateAnnotations: boolean;
  showHiddenTokens: boolean;
  showFogOverlay: boolean;
  mode: "gm_full" | "fog_edit" | "player_preview";
};

type PlayerMapViewState = {
  zoom: number;
  panX: number;
  panY: number;
  fitMode: DisplayFitMode;
  fogEnabled: boolean;
  gridVisible: boolean;
  labelsVisible: boolean;
};
```

### 6.3 Fog Mask

MVP should use a raster mask aligned to map pixel coordinates.

Recommended semantics:
- `0` = hidden from players;
- `255` = visible to players;
- intermediate alpha optional later for soft reveal.

```ts
type FogMask = VersionedRecord & {
  id: FogMaskId;
  campaignId: CampaignId;
  mapId: MapId;
  sceneId?: SceneId;
  width: number;
  height: number;
  storageKey: string;
  brushSettings: FogBrushSettings;
};

type FogBrushSettings = {
  size: number;
  hardness: number;
  opacity: number;
  mode: "reveal" | "hide";
};
```

Persist fog mask as a PNG/WebP blob or raw compressed bytes through `AssetStore`/OPFS. For MVP, PNG is easiest to inspect/debug.

### 6.4 Fog Operations

```ts
type FogOperation =
  | { type: "reveal_brush"; points: Point[]; size: number; hardness: number }
  | { type: "hide_brush"; points: Point[]; size: number; hardness: number }
  | { type: "reveal_rect"; rect: Rect }
  | { type: "hide_rect"; rect: Rect }
  | { type: "reveal_polygon"; points: Point[] }
  | { type: "hide_polygon"; points: Point[] }
  | { type: "reveal_all" }
  | { type: "hide_all" }
  | { type: "reset" };

type Point = { x: number; y: number };
type Rect = { x: number; y: number; width: number; height: number };
```

MVP order:
1. `reveal_rect`
2. `hide_rect`
3. `reveal_brush`
4. `hide_brush`
5. polygon later

Live transport rule:
- during pointer drag, send `FogOperation` messages only;
- do not send full raster fog masks during drag;
- do not call `canvas.toDataURL()` in a live fog path;
- do not send base64 Data URLs over `BroadcastChannel`;
- on pointer-up/debounce, send or persist an authoritative `FogSnapshotTransport`.

### 6.5 Token

```ts
type TokenVisibility = "gm_only" | "player_visible" | "hidden_until_revealed";
type LabelVisibility = "gm_only" | "player_visible" | "hidden";

type Token = VersionedRecord & {
  id: TokenId;
  campaignId: CampaignId;
  mapId: MapId;
  sceneId?: SceneId;
  entityId?: EntityId;
  assetId?: AssetId;
  name: string;
  position: Point; // token center in intrinsic map pixels
  size: { width: number; height: number };
  rotation: number; // degrees around token center
  layerId?: string;
  visibility: TokenVisibility;
  labelVisibility: LabelVisibility;
  status: TokenStatus[];
  style: TokenStyle;
};

type TokenStatus = {
  id: string;
  label: string;
  icon?: string;
  color?: string;
};

type TokenStyle = {
  shape: "circle" | "square" | "portrait" | "marker";
  color?: string;
  borderColor?: string;
  opacity?: number;
};
```

Current coordinate convention:
- `position.x/y` are the token center point in intrinsic map pixel coordinates.
- `size.width/height` are rendered token size in intrinsic map pixels.
- `rotation` is around the token center.
- CSS pixels, device pixel ratio, and top-left DOM positioning do not enter persistence.

### 6.6 Token Visibility Rules

```ts
function isTokenPublic(token: Token, fogMask: FogMask | undefined): boolean {
  if (token.visibility === "gm_only") return false;
  if (token.visibility === "player_visible") return true;
  if (token.visibility === "hidden_until_revealed") {
    return isPointVisibleInFogMask(token.position, fogMask);
  }
  return false;
}

function getPublicTokenLabel(token: Token): string | undefined {
  if (token.labelVisibility !== "player_visible") return undefined;
  return token.name;
}
```

For MVP, `hidden_until_revealed` can be implemented by checking token center point against fog mask. Later, use token bounds.

### 6.7 Player Map Payload

```ts
type PlayerMapPayload = {
  sceneMapId: string;
  mapId: MapId;
  assetId: AssetId;
  assetUrl: string;
  mimeType?: string;
  width: number;
  height: number;
  title: string;
  fitMode: DisplayFitMode;
  grid: {
    type: "square";
    visible: boolean;
    sizePx: number;
    offsetX: number;
    offsetY: number;
    color: string;
    opacity: number;
  };
  fog?: PlayerFogPayload;
  tokens?: PublicTokenPayload[];
  annotations?: PublicAnnotationPayload[];
};

type PlayerFogPayload = {
  enabled: boolean;
  maskId: FogMaskId;
  maskUrl: string;
  revision: number;
  width: number;
  height: number;
};

type PublicTokenPayload = {
  id: TokenId;
  entityId?: EntityId;
  assetId?: AssetId;
  assetUrl?: string;
  name?: string;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  style: TokenStyle;
  status: TokenStatus[];
};

type PublicAnnotationPayload = {
  id: string;
  type: "label" | "shape" | "ping";
  payload: unknown;
};
```

Current Slice 8 payload includes map metadata, square grid settings, optional fog, and sanitized public tokens. Annotations remain deferred.

### 6.8 Map Sanitizer

```ts
function createPlayerMapPayload(input: {
  map: MapAsset;
  mapState: MapSceneState;
  fogMask?: FogMask;
  tokens: Token[];
  layers: MapLayer[];
}): PlayerMapPayload {
  const publicTokens = input.tokens
    .filter((token) => isTokenPublic(token, input.fogMask))
    .map(toPublicTokenPayload);

  return {
    mapId: input.map.id,
    mapAssetId: input.map.assetId,
    width: input.map.width,
    height: input.map.height,
    fog: createPlayerFogPayload(input.fogMask, input.mapState.playerView),
    grid: input.mapState.playerView.gridVisible ? input.map.defaultGrid : undefined,
    tokens: publicTokens,
    annotations: createPublicAnnotations(input.layers),
    view: input.mapState.playerView,
  };
}
```

Rules:
- Public map payload must be generated only through the centralized sanitizer.
- No endpoint may hand-roll token filtering.
- `player_visible` tokens are public even under fog.
- `hidden_until_revealed` tokens are public only when the token center point is visible in the fog mask.
- Token portrait `assetUrl` is included only for safe public-displayable assets referenced by the active public payload.

This function is a critical safety boundary and should have tests.

Current Slice 6 sanitizer rule:
- the shared map renderer accepts a sanitized render payload, not raw `SceneMapRecord` or backend ORM data;
- GM preview may derive render props from private scene-map API data;
- `/player` derives render props only from `GET /api/player-display`;
- browser transport never carries the map payload.

## 7. Entity Domain

### 7.1 Entity

```ts
type EntityKind =
  | "pc"
  | "npc"
  | "creature"
  | "location"
  | "item"
  | "handout"
  | "faction"
  | "vehicle"
  | "generic";

type Entity = VersionedRecord & {
  id: EntityId;
  campaignId: CampaignId;
  kind: EntityKind;
  name: string;
  displayName?: string;
  visibility: "private" | "public_known";
  portraitAssetId?: AssetId;
  tags: string[];
  fields: Record<string, CustomFieldValue>;
  notes?: string;
};
```

### 7.2 Custom Fields

```ts
type CustomFieldType =
  | "number"
  | "boolean"
  | "short_text"
  | "long_text"
  | "select"
  | "multi_select"
  | "radio"
  | "resource"
  | "image";

type CustomFieldDefinition = VersionedRecord & {
  id: string;
  campaignId: CampaignId;
  appliesTo: EntityKind[];
  key: string;
  label: string;
  type: CustomFieldType;
  required: boolean;
  defaultValue?: CustomFieldValue;
  options?: string[];
  publicByDefault: boolean;
  sortOrder: number;
};

type CustomFieldValue =
  | { type: "number"; value: number }
  | { type: "boolean"; value: boolean }
  | { type: "short_text"; value: string }
  | { type: "long_text"; value: string }
  | { type: "select"; value: string }
  | { type: "multi_select"; value: string[] }
  | { type: "radio"; value: string }
  | { type: "resource"; current: number; max?: number }
  | { type: "image"; assetId: AssetId };
```

Field definitions should support flexible party card configuration, but be global enough for NPCs, creatures, locations, and other entities.

Implementation rules:
- `entities.visibility` defaults to `private`;
- `portraitAssetId` must reference a same-campaign image asset;
- `custom_field_definitions.key` is unique per campaign, lowercase slug, and immutable after creation;
- `custom_field_definitions.field_type` is immutable after creation;
- values are unique per `(entityId, fieldDefinitionId)`;
- values may only be set when the field applies to the entity kind;
- `image` values must reference same-campaign image assets.

### 7.3 Party Tracker

Party tracker uses an explicit campaign roster and ordered field config.

```ts
type PartyTrackerConfig = VersionedRecord & {
  id: string;
  campaignId: CampaignId;
  layout: "compact" | "standard" | "wide";
};

type PartyTrackerMember = VersionedRecord & {
  id: string;
  configId: string;
  campaignId: CampaignId;
  entityId: EntityId;
  sortOrder: number;
};

type PartyTrackerField = VersionedRecord & {
  id: string;
  configId: string;
  campaignId: CampaignId;
  fieldDefinitionId: string;
  sortOrder: number;
  publicVisible: boolean;
};
```

Slice 10 roster accepts `pc` entities only.

### 7.4 Public Party Payload

```ts
type PublicPartyPayload = {
  type: "party";
  campaignId: CampaignId;
  layout: "compact" | "standard" | "wide";
  cards: PublicPartyCard[];
};

type PublicPartyCard = {
  entityId: EntityId;
  displayName: string;
  kind: "pc";
  portraitAssetId?: AssetId;
  portraitUrl?: string;
  fields: Array<{
    key: string;
    label: string;
    type: CustomFieldType;
    value: unknown;
  }>;
};
```

Sanitization rules:
- include only party roster entities with `visibility = "public_known"`;
- include only `party_tracker_fields.public_visible = true`;
- exclude entity notes, tags, private entities, non-roster entities, and private fields;
- include portrait/image URLs only when the referenced asset is `public_displayable`;
- public blob serving for party assets is active-payload scoped.

### 7.5 Quick NPC Seed Catalog

Quick NPC is a run-mode GM primitive backed by shipped static content. It is not an image dataset and it is not an LLM workflow.

Current v1 bundled catalog:

```text
bundled/quick_npc_seeds/quick_npc_seeds.json
```

The current file is a top-level JSON array. Do not change it to an envelope without adding a backwards-compatible loader and updating the schema test.

```ts
type QuickNpcSeedType =
  | "guard_soldier"
  | "commoner_villager"
  | "merchant_trader"
  | "artisan_craftsperson"
  | "noble_official_bureaucrat"
  | "criminal_spy_smuggler"
  | "scholar_scribe_priest"
  | "traveler_refugee_pilgrim"
  | "wilderness_local_guide_hunter"
  | "sailor_porter_caravan_worker"
  | "cultist_zealot_secret_believer"
  | "weird_magical_stranger";

type QuickNpcSeed = {
  id: string;
  type: QuickNpcSeedType;
  race: string;
  gender: "female" | "male";
  name: string;
  role: string;
  origin: string;
  appearance: string;
  voice: string;
  mannerism: string;
  attitude: string;
  tinyBackstory: string;
  hookOrSecret: string;
  portraitTags: string[];
  useTags: string[];
};
```

Backend loader rules:
- load the bundled JSON once at startup or lazily through a cached service;
- validate schema before serving any catalog response;
- reject duplicate seed IDs and duplicate names;
- require exactly 300 seeds in v1;
- require exactly 25 seeds for each `QuickNpcSeedType`;
- require non-empty strings for scalar fields;
- require non-empty string arrays for `portrait_tags` and `use_tags`;
- preserve stable IDs exactly as written in the bundled file;
- expose camelCase API fields while accepting the snake_case bundled file internally;
- do not mutate the bundled catalog during campaign play.

Selection query:

```ts
type QuickNpcSeedQuery = {
  type?: QuickNpcSeedType;
  race?: string;
  gender?: "female" | "male";
  role?: string;
  useTags?: string[];
  q?: string;
  limit?: number;
  offset?: number;
  randomSeed?: string;
  excludeSeedIds?: string[];
};

type QuickNpcDrawRequest = QuickNpcSeedQuery & {
  count?: number;
};

type QuickNpcDrawResponse = {
  seeds: QuickNpcSeed[];
  totalMatching: number;
  randomSeed?: string;
};
```

Selection service rules:
- filtering is exact for `type`, `race`, and `gender`;
- `role` is case-insensitive substring matching against `role`;
- `useTags` uses AND semantics by default;
- `q` searches `name`, `role`, `race`, `origin`, `appearance`, `attitude`, `tiny_backstory`, `hook_or_secret`, `portrait_tags`, and `use_tags`;
- default browse ordering is stable by file order;
- random draw shuffles only the already-filtered candidate set;
- if `randomSeed` is supplied, repeated requests with the same filters and seed must return the same order;
- `excludeSeedIds` supports rerolling without immediately repeating already shown seeds;
- the service must return quickly enough for live table use and must not call an LLM provider.

Initial GM API surface:

```text
GET  /api/bundled/quick-npcs
GET  /api/bundled/quick-npcs/{seed_id}
POST /api/bundled/quick-npcs/draw
POST /api/campaigns/{campaign_id}/quick-npcs/promote
```

`GET /api/bundled/quick-npcs` accepts query parameters matching `QuickNpcSeedQuery` except `randomSeed`.

Promotion request:

```ts
type QuickNpcPromotionRequest = {
  seedId: string;
  sceneId?: SceneId;
  name?: string;
  displayName?: string;
  portraitAssetId?: AssetId;
  tags?: string[];
  note?: string;
};

type QuickNpcPromotionResponse = {
  entity: Entity;
  sourceSeedId: string;
};
```

Promotion behavior:
- promotion is an explicit GM action;
- promotion creates a new `Entity` with `kind = "npc"` and `visibility = "private"`;
- the generated entity name defaults to `QuickNpcSeed.name`;
- `portraitAssetId`, when present, must reference a same-campaign validated image asset;
- the seed's `type`, `race`, `gender`, `role`, and `useTags` become searchable tags and/or custom fields;
- the seed's origin, appearance, voice, mannerism, attitude, tiny backstory, and hook/secret are copied into editable campaign state;
- the campaign entity must not hold a live reference that would change when the bundled catalog changes later;
- the original `sourceSeedId` should be preserved for traceability and optional portrait matching;
- promoted NPCs can be linked to the active scene after creation when `sceneId` is supplied.

Recommended field mapping for the first promotion implementation:

```text
Entity.name                <- seed.name
Entity.kind                <- npc
Entity.visibility          <- private
Entity.tags                <- seed.type, seed.race, seed.gender, seed.role, seed.use_tags
Entity.notes               <- compact GM-readable seed summary plus optional promotion note
custom.quick_npc_seed_id   <- seed.id
custom.quick_npc_type      <- seed.type
custom.race                <- seed.race
custom.gender              <- seed.gender
custom.role                <- seed.role
custom.origin              <- seed.origin
custom.appearance          <- seed.appearance
custom.voice               <- seed.voice
custom.mannerism           <- seed.mannerism
custom.attitude            <- seed.attitude
custom.tiny_backstory      <- seed.tiny_backstory
custom.hook_or_secret      <- seed.hook_or_secret
```

If these custom field definitions do not exist for the campaign, the promotion service may create private-by-default definitions lazily. It must not make `hook_or_secret`, notes, or backstory public by default.

GM UI requirements:
- expose a Quick NPC picker/card from the GM overview and focused session/scene tools;
- support filter by type, race, gender, role, and use tags;
- support search by name, role, tags, and seed text;
- support reroll/refresh without repeating the immediately visible seed when possible;
- show a compact card with name, race, role, appearance, voice, mannerism, attitude, and hook/secret;
- provide copy/use-in-note actions that do not create campaign canon;
- provide pin/save-for-session behavior for temporarily useful seeds;
- provide "Promote to campaign NPC" as the action that creates durable editable campaign state;
- after promotion, link to the created NPC card and allow optional scene linking.

Command registry additions for the Quick NPC slice:

```text
npc.quickPicker
npc.quickDraw
npc.promoteQuickSeed
```

Asset binding is optional and source-seed based:

```ts
type QuickNpcPortraitCandidate = {
  id: string;
  sourceSeedId: string;
  assetPackId: string;
  variant: number;
  assetId?: AssetId;
  status: "generated" | "pending_review" | "accepted" | "rejected" | "artifact" | "metadata_mismatch";
  notes?: string;
  metadata: {
    sourceSeed: QuickNpcSeed;
    filename?: string;
    prompt?: string;
    model?: string;
  };
};
```

Rules:
- portrait candidates are not source of truth for NPC identity;
- the app must remain fully usable when no portrait pack is installed;
- raw generated portraits are offline/bootstrap output, not campaign assets;
- a portrait becomes usable in Myroll only after it passes through the existing asset validation/import pipeline;
- imported portrait assets should keep searchable provenance linking them to `sourceSeed.id`;
- if multiple variants exist, the UI should prefer a curated `accepted` variant and hide rejected/artifact variants by default;
- curation may be manual first and VLM-assisted later;
- curation should track race/gender mismatches, artifacts, malformed anatomy, and species-specific failures such as problematic dragonborn outputs;
- no Quick NPC portrait is published to `/player` unless the GM explicitly links it to a public-displayable asset and publishes a player-safe display mode.

## 8. Combat Domain

Combat is manual and rules-light in Slice 11. It stores enough D&D-ish state for live table operation without rules automation.

```ts
type CombatEncounter = VersionedRecord & {
  id: string;
  campaignId: CampaignId;
  sessionId?: SessionId;
  sceneId?: SceneId;
  title: string;
  status: "active" | "paused" | "ended";
  round: number;
  activeCombatantId?: CombatantId;
};

type Combatant = VersionedRecord & {
  id: CombatantId;
  campaignId: CampaignId;
  encounterId: CombatEncounterId;
  entityId?: EntityId;
  tokenId?: TokenId;
  name: string;
  disposition: "pc" | "ally" | "neutral" | "enemy" | "hazard" | "other";
  initiative?: number;
  orderIndex: number;
  armorClass?: number;
  hpCurrent?: number;
  hpMax?: number;
  hpTemp: number;
  conditions: Array<Record<string, unknown>>; // GM/private
  publicStatus: Array<string | { label: string }>;
  notes: string; // GM/private
  publicVisible: boolean;
  isDefeated: boolean;
};
```

Turn rules:
- combatants are ordered by `orderIndex`;
- next/previous skip defeated combatants;
- wrapping forward increments round;
- wrapping backward decrements round but never below 1;
- if every combatant is defeated, active combatant becomes `null` and round does not churn.

### 8.1 Public Initiative Payload

```ts
type PublicInitiativePayload = {
  type: "initiative";
  encounterId: CombatEncounterId;
  round: number;
  activeCombatantId?: CombatantId;
  combatants: Array<{
    id: CombatantId;
    name: string;
    disposition: Combatant["disposition"];
    initiative?: number;
    isActive: boolean;
    portraitAssetId?: AssetId;
    portraitUrl?: string;
    publicStatus: Array<string | { label: string }>;
  }>;
};
```

Sanitization rules:
- include only `combatants.publicVisible = true`;
- do not infer public visibility from linked token/entity state after creation;
- exclude HP, temp HP, AC, private conditions, combat notes, entity tags, private fields, and hidden combatants;
- `conditions` is GM/private state;
- `publicStatus` is curated player-facing state and accepts only bounded strings or `{ label }` objects;
- portrait URLs appear only when the referenced asset is `public_displayable`;
- public blob serving for initiative portraits is active-payload scoped.

## 9. Notes Domain

### 9.1 Note Source

```ts
type NoteSourceKind = "internal" | "imported_markdown";

type NoteSource = VersionedRecord & {
  id: string;
  campaignId: CampaignId;
  kind: NoteSourceKind;
  name: string;
  readonly: boolean;
};
```

Imported notes copy content into SQLite. The original absolute source path is not stored as an asset location or runtime dependency.

### 9.2 Note

```ts
type Note = VersionedRecord & {
  id: NoteId;
  campaignId: CampaignId;
  sourceId?: string;
  title: string;
  privateBody: string;
  tags: string[];
  sourceLabel?: string;
  sessionId?: SessionId;
  sceneId?: SceneId;
  assetId?: AssetId;
};
```

### 9.3 Public Snippet

```ts
type PublicSnippet = VersionedRecord & {
  id: PublicSnippetId;
  campaignId: CampaignId;
  noteId?: NoteId;
  title?: string;
  body: string;
  format: "markdown";
};
```

Public snippets are explicit snapshot records. If the GM creates one from a note selection, the selected text is copied into `PublicSnippet.body` at that moment. `noteId` is traceability only and never authoritative for display text.

Only `PublicSnippet.title`, `PublicSnippet.body`, and `PublicSnippet.format` are used for player text payloads. `Note.privateBody` and `noteId` are not sent to `/player`.

### 9.4 API Surface

```text
GET   /api/campaigns/{campaign_id}/notes
POST  /api/campaigns/{campaign_id}/notes
GET   /api/notes/{note_id}
PATCH /api/notes/{note_id}
POST  /api/campaigns/{campaign_id}/notes/import-upload

GET   /api/campaigns/{campaign_id}/public-snippets
POST  /api/campaigns/{campaign_id}/public-snippets
PATCH /api/public-snippets/{snippet_id}

POST  /api/player-display/show-snippet
```

Validation:
- note title: max 160 chars and non-empty after trim;
- private note body: max 200,000 chars;
- snippet body: max 8,000 chars;
- markdown import: `.md`, `.markdown`, `.txt`, max 2 MB, decoded as UTF-8 or UTF-8-sig;
- linked session, scene, asset, and note IDs must belong to the same campaign.

### 9.5 Text Display Payload

```json
{
  "mode": "text",
  "payload": {
    "type": "public_snippet",
    "snippet_id": "...",
    "title": "Optional public title",
    "body": "Public text only",
    "format": "markdown"
  }
}
```

`show-snippet` mutates only `player_display_runtime`, increments display `revision`, and returns the current player display response. GM broadcasts display transport notifications only after this backend mutation succeeds.

GM preview and `/player` text mode use the same safe markdown renderer. Raw HTML is disabled and links render as inert text in the Slice 9 UI.

## 10. Canvas Domain

### 10.1 Widget Instance

```ts
type WidgetKind =
  | "map"
  | "notes"
  | "party_tracker"
  | "combat_tracker"
  | "entity_library"
  | "npc_generator"
  | "quick_npc_picker"
  | "dice_roller"
  | "display_status"
  | "timer"
  | "soundboard"
  | "weather"
  | "custom";

type CanvasWidgetInstance = VersionedRecord & {
  id: string;
  campaignId: CampaignId;
  sceneId?: SceneId;
  kind: WidgetKind;
  title?: string;
  position: {
    x: number;
    y: number;
    width: number;
    height: number;
    zIndex: number;
  };
  locked: boolean;
  minimized: boolean;
  config: Record<string, unknown>;
};
```

### 10.2 Layout

```ts
type Layout = VersionedRecord & {
  id: LayoutId;
  campaignId: CampaignId;
  sceneId?: SceneId;
  name: string;
  canvas: {
    zoom: number;
    panX: number;
    panY: number;
  };
  widgets: CanvasWidgetInstance[];
};
```

### 10.3 Run Mode

```ts
type WorkspaceMode = "prep" | "run" | "layout_edit";
```

Rules:
- `run`: prevent accidental widget moves unless modifier/explicit unlock.
- `layout_edit`: enable drag/resize.
- `prep`: allow content editing and layout changes with fewer restrictions.

The Player Display status widget should be pinned or otherwise always visible in Run Mode.

## 11. Tool Domains

### 11.1 Party Tracker

Party tracker renders explicitly rostered `pc` entities using custom field definitions.

```ts
type PartyTrackerConfig = {
  memberIds: EntityId[];
  fields: Array<{ fieldDefinitionId: string; publicVisible: boolean }>;
  layout: "compact" | "standard" | "wide";
};
```

The party card editor maps to `CustomFieldDefinition`, `CustomFieldValue`, and the explicit party tracker roster. Public projection is cards-only and passes through the party sanitizer before writing `player_display_runtime(mode="party")`.

### 11.2 Combat Tracker

```ts
type CombatState = VersionedRecord & {
  id: string;
  campaignId: CampaignId;
  sceneId?: SceneId;
  round: number;
  activeTurnIndex: number;
  combatants: Combatant[];
  startedAt?: IsoDateTime;
};

type Combatant = {
  id: string;
  entityId?: EntityId;
  tokenId?: TokenId;
  name: string;
  initiative: number;
  hp?: { current: number; max?: number };
  ac?: number;
  status: TokenStatus[];
  publicVisible: boolean;
};
```

Public initiative projection:

```ts
type PublicInitiativePayload = {
  round: number;
  activeCombatantId?: string;
  combatants: {
    id: string;
    name: string;
    portraitAssetId?: AssetId;
    status: TokenStatus[];
    isActive: boolean;
  }[];
};
```

Filter by `publicVisible`.

### 11.3 Dice Roller

MVP dice roller can be local-only.

```ts
type DiceRoll = {
  id: string;
  expression: string;
  result: number;
  detail: string;
  rolledAt: IsoDateTime;
};
```

Player projection of dice rolls is optional and should be explicit.

## 12. Command Registry

### 12.1 Command

```ts
type CommandContext = {
  campaignId: CampaignId;
  activeSceneId?: SceneId;
  selection: SelectionState;
};

type Command = {
  id: string;
  title: string;
  description?: string;
  category: string;
  hotkey?: string;
  canRun(ctx: CommandContext): boolean;
  run(ctx: CommandContext): Promise<void>;
  safety?: CommandSafety;
};

type CommandSafety = {
  affectsPlayerDisplay: boolean;
  requiresConfirmation: boolean;
  supportsUndo: boolean;
};
```

### 12.2 Critical Commands

Required MVP commands:

```text
display.open
display.reconnect
display.identify
display.preview
display.blackout
display.undo
display.sendCurrentMap
display.sendSelectedHandout
display.publishStaged
map.enterFogEdit
map.revealRect
map.hideRect
scene.activate
scene.create
asset.import
token.add
token.togglePlayerVisible
note.createPublicSnippet
note.publishSnippetToDisplay
```

Every command affecting player display should be visible in display history.

## 13. Storage Schema

Durable MVP storage lives in SQLite through Alembic migrations. Browser storage is UI cache/runtime convenience only and must not become the campaign source of truth.

The logical records below describe durable domain tables, not an IndexedDB contract:

```ts
type MyrollDurableStore = {
  campaigns: Campaign;
  sessions: Session;
  scenes: Scene;
  assets: Asset;
  assetFiles: { relativePath: string; checksum: string };
  maps: MapAsset;
  mapSceneStates: MapSceneState;
  fogMasks: FogMask;
  tokens: Token;
  entities: Entity;
  customFieldDefinitions: CustomFieldDefinition;
  notes: Note;
  publicSnippets: PublicSnippet;
  layouts: Layout;
  displayStates: PlayerDisplayState;
  displayHistory: DisplayHistoryEntry;
  combatStates: CombatState;
  storageHealth: StorageHealthRecord;
};
```

The bundled Quick NPC seed catalog is app content loaded from the repository/package, not durable campaign state. Promoted quick NPCs become normal `entities` records.

Suggested indexes:

```text
campaigns: id
sessions: id, campaignId
scenes: id, campaignId, sessionId
assets: id, campaignId, kind
maps: id, campaignId, assetId
mapSceneStates: id, campaignId, sceneId, mapId
fogMasks: id, campaignId, sceneId, mapId
tokens: id, campaignId, sceneId, mapId, entityId
entities: id, campaignId, kind, name
customFieldDefinitions: id, campaignId, key
notes: id, campaignId, sourceId
publicSnippets: id, campaignId, noteId
layouts: id, campaignId, sceneId
displayStates: id, campaignId, sceneId, mode
displayHistory: id, campaignId, timestamp
combatStates: id, campaignId, sceneId
```

### 13.1 Backup, Export, And Restore Contract

Slice 13 adds explicit portable storage operations:

```text
GET  /api/storage/status
POST /api/storage/backup
POST /api/storage/export
GET  /api/storage/exports/{archive_name}
```

`storage/status` returns shortened paths only:

```ts
type StorageStatus = {
  profile: "dev" | "demo" | string;
  dbPath: string;
  assetDir: string;
  backupDir: string;
  exportDir: string;
  dbSizeBytes: number;
  assetSizeBytes: number;
  latestBackup: StorageArtifact | null;
  latestExport: StorageArtifact | null;
  schemaVersion: string | null;
  seedVersion: string | null;
  expectedSeedVersion: string;
  privateDemoNameMapActive: boolean;
};
```

Export archives are gzip tar archives with this layout:

```text
myroll-export.json
db/myroll.sqlite3
assets/<managed asset tree>
```

The manifest includes format version, archive name, created timestamp, database archive path, asset root, byte sizes, and SHA-256 checksums. `.tmp` paths are excluded from export.

Restore is offline:

```bash
scripts/restore_export.sh <archive> <target-data-dir> [--force]
```

Restore rejects absolute paths, `..` traversal, unexpected archive entries, and non-empty targets unless forced. Restored DB is written as `myroll.dev.sqlite3`; restored blobs go under `assets/`.

### 13.2 Demo Profile Contract

The deterministic public demo profile is keyed as `lantern_vale_chronicle`.

Default public-safe names:

```text
Chronicle of the Lantern Vale
Lake of the Last Horn
The Blue Forest Road
The Crooked Loom House
Workshop of Stolen Time
```

Local display-name overrides are read from ignored `demo/local/name-map.private.json` when present. The override file maps stable demo keys to local display names:

```json
{
  "campaign.lantern_vale_chronicle": "Private local campaign title",
  "scene.crooked_loom_house": "Private local scene title"
}
```

Committed fixtures and generated asset manifests must stay public-safe and English. Public demo exports should be generated without the local override map active.

Generated demo images live under:

```text
demo/assets/generated/lantern_vale_chronicle/
```

Demo reset imports those files through the normal image validation path into the current demo data dir. The source files are fixture inputs, not runtime blobs.

### 13.3 Active App State

Some state can live in a singleton settings table:

```ts
type AppRuntimeSettings = {
  id: "runtime";
  activeCampaignId?: CampaignId;
  activeSessionId?: SessionId;
  activeSceneId?: SceneId;
  activeDisplayStateId?: DisplayStateId;
  stagedDisplayStateId?: DisplayStateId;
};
```

Persist this so refresh/reconnect works.

### 13.2 Storage Health

```ts
type StoragePersistenceStatus =
  | "persistent"
  | "best_effort"
  | "unsupported"
  | "unknown";

type StorageHealthRecord = {
  id: "storage-health";
  schemaVersion: number;
  persistence: StoragePersistenceStatus;
  estimate?: {
    usage?: number;
    quota?: number;
    usageRatio?: number;
  };
  lastCheckedAt?: IsoDateTime;
  lastPersistRequestAt?: IsoDateTime;
  lastPersistRequestGranted?: boolean;
  lastBackupExportAt?: IsoDateTime;
  lastWriteError?: {
    name: string;
    message: string;
    occurredAt: IsoDateTime;
  };
};
```

Storage persistence gate:

```ts
async function ensurePersistentStorage(): Promise<StorageHealthRecord> {
  if (!navigator.storage) {
    return markStorageHealth({ persistence: "unsupported" });
  }

  const alreadyPersistent = navigator.storage.persisted
    ? await navigator.storage.persisted()
    : false;

  const granted = alreadyPersistent || (
    navigator.storage.persist
      ? await navigator.storage.persist()
      : false
  );

  const estimate = navigator.storage.estimate
    ? await navigator.storage.estimate()
    : undefined;

  return markStorageHealth({
    persistence: granted ? "persistent" : "best_effort",
    estimate: estimate
      ? {
          usage: estimate.usage,
          quota: estimate.quota,
          usageRatio: estimate.usage && estimate.quota
            ? estimate.usage / estimate.quota
            : undefined,
        }
      : undefined,
    lastPersistRequestGranted: granted,
  });
}
```

Call this:
- on first app load;
- on campaign create;
- on campaign open;
- after large imports;
- before session Run Mode if status is unknown.

If persistence is `best_effort`, show a visible warning and prompt for export/backup.

## 14. Fog Rendering Details

### 14.1 GM Full View

Render order:

```text
background
map image
GM-only annotations
grid
all tokens if showHiddenTokens
public/private labels depending GM settings
fog overlay if showFogOverlay or fog_edit
selection/tools
```

Fog overlay in GM view should tint hidden-to-player areas but not obscure the map completely.

### 14.2 Player View

Render order:

```text
black background
map image clipped/masked by fog
public grid
public tokens
public labels
public overlays
```

Never render:
- GM-only annotations;
- hidden tokens;
- private labels;
- notes;
- editing controls.

### 14.3 Raster Mask Strategy

MVP approach:
1. Store one internal grayscale PNG fog mask per scene map.
2. Use intrinsic map pixel coordinates for reveal/hide operations.
3. Apply rectangle/brush operations to the mask in backend storage on operation commit.
4. Increment fog revision and use it for cache-busting mask URLs.
5. Generate player render by compositing map image with mask.

For player rendering:

```text
draw map image to canvas
set globalCompositeOperation = destination-in
draw fog mask converted from luminance to alpha
reset composite operation
draw public overlays/tokens
```

If mask is `0 hidden / 255 visible`, `destination-in` keeps revealed pixels.

### 14.4 Debouncing

Brush movement can generate many updates.

Recommended:
- update local GM canvas immediately;
- publish vector `FogOperation` messages to player display at 20-30fps max during brush drag;
- let `/player` apply operations to its local fog canvas;
- persist fog mask after 300-500ms debounce;
- final authoritative fog snapshot on pointer up.

Current MVP publishes only committed operations. GM preview may show the local draft immediately, but `/player` changes only after backend persistence succeeds.

Forbidden live path:

```text
canvas -> toDataURL/base64 -> BroadcastChannel -> decode -> draw
```

Acceptable live path:

```text
pointer move -> FogOperation -> transport -> player applies operation locally
pointer up -> toBlob/ArrayBuffer/ImageBitmap or asset_ref snapshot -> resync
```

If using `postMessage`, include `ArrayBuffer`/`ImageBitmap` in the transfer list for snapshots where supported.

## 15. Display History And Undo

### 15.1 History Entry

```ts
type DisplayHistoryEntry = {
  id: string;
  campaignId: CampaignId;
  previousStateId?: DisplayStateId;
  nextStateId: DisplayStateId;
  commandId: string;
  sourceType?: "scene" | "map" | "asset" | "note" | "combat" | "manual";
  sourceId?: string;
  timestamp: IsoDateTime;
};
```

### 15.2 Undo Semantics

Display undo should restore previous `PlayerDisplayState`.

It should not undo domain mutations unless explicitly implemented later. Example:
- If fog reveal changed the fog mask and updated player display, `display.undo` restores previous display state but may not revert the fog mask.
- A separate `map.undoFogOperation` can exist later.

For MVP, keep display undo and domain undo separate.

## 16. Public/Private Safety Tests

### 16.1 Required Unit Tests

Map sanitizer:
- GM-only token excluded.
- Hidden-until-revealed token excluded when fog hidden.
- Hidden-until-revealed token included when center point revealed.
- Player-visible token included.
- GM-only label omitted.
- Hidden label omitted.
- Public label included.
- GM-only layer annotations omitted.

Notes:
- staging snippet sends only snippet body.
- full private note body is not present in display payload.

Display:
- blackout payload contains no previous sensitive payload.
- undo restores previous display state.
- staged state does not publish until confirmed.

Storage:
- `ensurePersistentStorage()` records `persistent` when granted.
- `ensurePersistentStorage()` records `best_effort` when denied.
- volatile-storage warning appears for `best_effort`.
- `QuotaExceededError` is recorded in `StorageHealthRecord.lastWriteError`.

Fog transport:
- brush drag emits `DISPLAY_FOG_OPERATION`.
- brush drag does not emit `DISPLAY_FOG_SNAPSHOT`.
- no live fog path calls `toDataURL()`.
- pointer-up emits or schedules authoritative snapshot sync.

Display transport:
- `postMessage` transport validates `origin` and `source`.
- `BroadcastChannel` transport is selected only when available.
- stale heartbeat marks connection stale/disconnected.

### 16.2 Required E2E Tests

Use Playwright for visual browser verification. Current `/gm` coverage must include:

- healthy backend cockpit screenshot;
- campaign/session/scene creation;
- runtime activation;
- layout drag/resize persistence after refresh;
- backend-unavailable degraded screenshot.

Player display coverage should use two pages:

```text
page1 = /gm
page2 = /player
```

Tests:
- open player display and receive heartbeat;
- send map and screenshot both pages;
- blackout hides player content;
- reveal area changes player map but GM still sees full map;
- hidden token appears in GM page but not player page;
- public snippet appears, private note text does not.
- refreshing `/player` resyncs from active display state.
- transport fallback/reconnect UI appears when heartbeat goes stale.
- storage persistence denial renders visible warning.

## 17. Error Handling

### 17.1 Player Window Blocked

Browsers can block `window.open` unless triggered by a direct user gesture.

UX:
- show "Open Player Display" as a real button;
- if blocked, show instructions;
- allow manual `/player` URL opening.

### 17.2 Display Disconnected

If heartbeat is stale:
- status panel shows stale/disconnected;
- display actions still update active state in storage;
- when `/player` reconnects, it syncs latest state.

### 17.3 Asset Missing

If player display cannot load asset:
- render safe fallback;
- report missing asset to GM via heartbeat/ack error later;
- never expose raw private metadata.

Fallback:

```text
Content unavailable
```

### 17.4 Storage Quota

Browser storage can hit quota.

MVP:
- show clear import failure;
- show storage usage if available;
- allow deleting assets.
- catch `QuotaExceededError` and record it in `StorageHealthRecord.lastWriteError`.
- require export/backup affordance in the storage warning UI.

Later:
- OPFS and export/import management.

## 18. Security And Privacy

This is local-first, but still handle privacy boundaries carefully.

### 18.1 MVP Threat Model

MVP `/player` is a non-adversarial presentation surface running on the GM machine.

It is designed for:
- a second monitor connected to the GM machine;
- a projector;
- a TV/table display;
- a shared player-facing browser window in online play.

It is designed to prevent accidental reveal through sanitized rendering, explicit public payloads, projection controls, preview, blackout, and undo.

It is not designed to secure private campaign data from a user who controls the `/player` browser context. In the MVP browser architecture, `/gm` and `/player` are same-origin app surfaces and may share the same JavaScript bundle, IndexedDB, OPFS, and browser devtools environment. That is not a remote-client permissions model.

If Myroll later supports players opening `/player` on their own devices or connecting to a remote player display URL, the architecture must change. Remote or untrusted player clients require:
- server-mediated sanitized payloads or an equivalent host process;
- no direct access to private local campaign storage;
- a separate origin, process, or storage boundary;
- authentication and authorization;
- public/private data separation before anything reaches the client.

Do not rely on client-side route separation alone for adversarial security.

### 18.2 MVP Privacy Rules

Rules:
- `/player` renders sanitized payload only.
- no private note bodies in display messages.
- no hidden token data in public map payload.
- no GM-only fields in public entity payload.
- asset visibility checked before display.
- public snippets explicit.

Local data is not encrypted in MVP unless product requirements change. Document this clearly later.

## 19. Performance Targets

MVP targets:
- player display state publish under 100ms for non-map content;
- map fog reveal visible on player display under 200ms after pointer up;
- GM map pan/zoom at interactive speed for 1080p/4K map images;
- support at least 100 tokens on a map without severe lag;
- blackout immediate, ideally under 50ms.

Avoid massive state broadcasts:
- send references to assets, not blobs;
- send compact fog mask references/data URLs only when changed;
- debounce brush updates.

## 20. Implementation Milestones

### Milestone 1: Local App Shell

Deliver:
- `/gm`;
- `/player`;
- IndexedDB wrapper;
- app runtime settings;
- basic campaign/scene creation.
- storage persistence check via `navigator.storage.persisted()` / `persist()`;
- visible best-effort/volatile storage warning;
- campaign export/backup placeholder.

Acceptance:
- refresh preserves active campaign/scene;
- app records storage persistence status;
- GM is warned if storage is best-effort.

### Milestone 2: Display Service

Deliver:
- open player window;
- `postMessage` transport for opener-managed player windows;
- BroadcastChannel transport for same-partition windows;
- storage sync fallback for reconnect;
- heartbeat/status panel;
- blackout/intermission;
- identify display.

Acceptance:
- GM can open player window, see connected status, blackout it, and identify it;
- transport kind is visible in debug/status state;
- app detects stale heartbeat and offers reconnect.

### Milestone 3: Static Public Content

Deliver:
- import image asset;
- send image/handout/text to player display;
- preview renderer;
- staged publish for text/snippet.

Acceptance:
- player display can show image/text and blackout; preview matches output.

### Milestone 4: Map MVP

Deliver:
- map asset;
- GM map renderer;
- player map renderer;
- send map to player;
- fit/fill settings.

Acceptance:
- GM sees full map; player sees map in separate fullscreen-friendly window.

### Milestone 5: Manual Fog MVP

Deliver:
- fog mask;
- rectangle reveal/hide;
- brush reveal/hide;
- player masking;
- fog edit view;
- player preview.

Acceptance:
- GM sees full map while players see only revealed regions.

### Milestone 6: Tokens

Deliver:
- add token;
- token visibility;
- label visibility;
- public payload filtering.

Acceptance:
- hidden token visible to GM but never rendered to player until made public/revealed.

### Milestone 7: Scene Runtime

Deliver:
- scene activation;
- linked map/fog/tokens;
- scene context row;
- linked entities;
- linked public snippets;
- active encounter staging;
- staged display publish;
- widget focus without scene-scoped layouts.

Acceptance:
- activating a scene restores GM context without changing `/player`;
- publishing staged display explicitly updates `/player` through existing public sanitizers.

### Milestone 8: Notes And Snippets

Deliver:
- markdown note storage/import into SQLite;
- public snippet snapshot creation from selected note text or direct entry;
- safe markdown preview;
- publish snippet to `/player` text mode.

Acceptance:
- selected snippet can be shown to players;
- editing the private note afterward does not change the snippet body;
- full note body and `note_id` remain absent from public text payloads.

### Milestone 9: Party And Combat Basics

Deliver:
- entity custom fields: complete in Slice 10;
- party cards and public party projection: complete in Slice 10;
- manual combat tracker: complete in Slice 11;
- sanitized public initiative projection: complete in Slice 11.

Acceptance:
- party widget uses shared entity data and projects only sanitized cards;
- combat widget uses optional shared entity/token references without adding rules automation;
- public initiative projection shows order/current turn only and excludes HP, AC, private conditions, notes, entity tags, private fields, and hidden combatants.

## 21. Open Decisions

1. Framework: React/Vite, Next, Svelte, or other.
2. State store: Zustand, Redux Toolkit, Jotai, or custom event store.
3. Storage wrapper: Dexie or direct IndexedDB.
4. Asset storage: IndexedDB Blob first vs OPFS first.
5. Fog persistence format: PNG blob vs raw mask bytes.
6. Live fog publishing: during brush drag vs on pointer up.
7. Notes sync later: direct File System Access, Obsidian/Notion/OneNote, or no live sync.
8. Canvas library: custom DOM transforms, React Flow-style library, or canvas-based workspace.
9. Desktop packaging later: PWA, Electron, Tauri, or none.

Recommended MVP defaults:
- React + Vite;
- Zustand for UI/runtime state;
- Dexie for IndexedDB;
- IndexedDB Blob storage first, OPFS later;
- PNG fog mask first;
- live fog preview locally, publish on pointer up first, then optimize;
- imported/internal markdown first, File System Access later;
- custom DOM-based canvas for widgets first.
