# Myroll High-Level Architecture

Date: 2026-05-02
Status: Draft 1

## 1. Architectural Thesis

Myroll is a local-first browser application with two primary runtime surfaces:

```text
/gm
  private GM workspace

/player
  dedicated player-facing display window
```

Both surfaces read from the same local campaign state, but they do not expose the same data. The GM workspace owns the complete operational state. The player display subscribes only to sanitized public display state.

The most important architectural decision:

```text
Player Display is a top-level service, not a sub-feature of the map widget.
```

Map + fog is one mode of the player display. The same display surface must also support handouts, images, text reveals, NPC portraits, initiative, timers, scene titles, mood boards, intermission, and blackout.

### 1.1 Current Implementation Pivot

The MVP implementation now uses a local backend as the durable persistence foundation:

```text
SQLite:
  durable source of truth

FastAPI:
  local control plane

Filesystem:
  asset blob storage

Browser:
  UI/runtime/cache
```

This supersedes the earlier browser-only IndexedDB durability model for core campaign data. Browser storage may still be used later for UI cache, layout drafts, display runtime convenience, or offline artifacts, but it is not the authoritative campaign database.

The local backend must bind to `127.0.0.1` by default. LAN or internet access is not part of the MVP runtime model.

## 2. System Context

```text
                           ┌──────────────────────┐
                           │ Local Files / Assets │
                           │ images, markdown     │
                           └──────────┬───────────┘
                                      │
                                      ▼
┌────────────────────────────────────────────────────────────────────┐
│ Browser App                                                        │
│                                                                    │
│  ┌──────────────────────┐  DisplayTransport layer      ┌────────┐  │
│  │ /gm                  │◄────────────────────────────►│/player │  │
│  │ GM Workspace         │                              │Display │  │
│  └──────────┬───────────┘                              └────────┘  │
│             │                                                      │
│             ▼                                                      │
│  ┌──────────────────────┐                                          │
│  │ Local App Store      │                                          │
│  │ IndexedDB / OPFS     │                                          │
│  └──────────────────────┘                                          │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

MVP runs fully local on the GM machine:
- local FastAPI backend;
- local SQLite database;
- no accounts;
- no multi-user networking;
- no cloud dependency;
- no remote player clients.

Future packaging can wrap the same app in Electron, Tauri, or a PWA installation, but the initial architecture should work as a local backend plus browser UI.

## 3. Runtime Surfaces

### 3.1 GM Workspace (`/gm`)

Responsibilities:
- render private canvas and widgets;
- manage campaigns, sessions, scenes, maps, notes, entities, and assets;
- control player display state;
- show persistent player display status;
- provide command palette and hotkeys;
- edit fog, tokens, map layers, public snippets, and display presets;
- store all campaign state locally.

The GM workspace may render player previews, but previews are separate sanitized render surfaces.

### 3.2 Player Display (`/player`)

Responsibilities:
- render only active `PlayerDisplayState`;
- render no GM controls by default;
- support fullscreen presentation;
- support blackout/intermission;
- receive sanitized display updates;
- report connection/heartbeat status to the GM workspace;
- tolerate refresh/reconnect.

The player display should never query private campaign data directly in a way that could render it accidentally. It should receive a public display view model.

Important boundary:

```text
MVP /player is a non-adversarial presentation surface running on the GM machine.
It is not a security boundary for remote or untrusted clients.
```

The MVP design prevents accidental reveal during projection and screen sharing. It assumes players are viewing the projector, table TV, second monitor, or shared player window, not controlling the `/player` browser context.

If players later open `/player` on their own devices, the architecture must change. Same-origin browser code with access to the local campaign database is not a permissions model. Remote or untrusted player clients require server-mediated sanitized payloads, separate storage access, a separate origin/process boundary, or equivalent isolation.

### 3.3 Optional Preview Surface

The GM workspace can embed a preview renderer that uses the same public view model as `/player`.

This guarantees:
- preview matches output;
- map/widget code is reused;
- private GM state does not leak through preview.

## 4. Bounded Contexts

### 4.1 Campaign Context

Owns top-level durable user data.

Entities:
- `Campaign`
- `Session`
- `Scene`
- `Asset`
- `Layout`

Responsibilities:
- campaign creation/opening;
- active campaign/session selection;
- asset metadata and managed asset import;
- persistence boundaries;
- import/export later.

Current asset implementation:
- image assets can be imported by browser upload or server-path copy;
- imported bytes are copied into managed `data/assets/` storage;
- SQLite stores asset metadata, checksums, visibility, dimensions, and relative storage keys;
- client MIME type, extension, filename, width, and height are not trusted;
- image metadata comes from backend validation.
- externally generated battle-map packs are fixture/input artifacts, not runtime blobs; the app-facing artifact is the curated production `manifest.json` plus category-local `category.json` files, and a future importer should validate every accepted WebP through the same backend image path before copying it into managed storage.
- curated static asset packs may be shipped with packaged builds as read-only bundled resources and auto-registered on startup, so installed users do not manually import the built-in map library.
- the first production pack may live in git as an immutable bundled asset version to avoid introducing separate artifact-storage infrastructure; move to Git LFS/release artifacts only if size or update frequency justifies it.
- user-facing bulk asset import should build on explicit browser upload or a future user-selected directory picker, not on arbitrary public HTTP filesystem paths.
- generated monster/NPC token art should enter as ordinary image assets and become selectable by scene-map portrait tokens through the existing public/private asset gates.

### 4.2 Scene Runtime Context

Owns the current live-session context.

Entities:
- `Scene`
- `SceneContext`
- `SceneEntityLink`
- `ScenePublicSnippetLink`
- `SceneActivation`
- `SceneDisplayPreset`
- `SceneRuntimeState`

Responsibilities:
- activate a scene;
- restore linked map/fog/tokens for GM focus;
- pin relevant notes/entities/widgets;
- stage player display intent;
- publish staged player display only through an explicit action;
- record revealed facts or display history later.

Scene Runtime is the bridge between the private GM truth and the public player fiction.

Current backend implementation:
- active runtime context is stored in the singleton `app_runtime` row;
- activation happens through action endpoints;
- runtime responses include active IDs and labels for frontend bootstrap;
- activation operations are transactional;
- scene orchestration state is stored in `scene_contexts`;
- entity relevance is stored in `scene_entity_links`;
- staged public snippets are stored in `scene_public_snippet_links`;
- `activate-scene`, context patch, link, and unlink operations do not mutate `player_display_runtime`;
- `publish-staged-display` is the explicit bridge from scene context to public display state and reuses existing public display sanitizers.

### 4.3 Player Display Context

Owns presentation state and public output.

Entities:
- `PlayerDisplayState`
- `PlayerDisplayWindow`
- `DisplayConnection`
- `DisplayHistoryEntry`

Responsibilities:
- open/reconnect player display window;
- publish display states;
- blackout;
- undo/restore previous display state;
- identify display;
- show GM status;
- sanitize payloads;
- coordinate `/gm`, preview, and `/player`.

This context must remain independent from Map. Map contributes display payloads, but does not own the display service.

Current implementation:
- `/player` is a fullscreen public presentation route.
- active public display state is stored in singleton `player_display_runtime`;
- supported public modes currently include blackout, intermission, scene title, image display, map display, text snippets, party cards, and initiative order;
- image display payloads contain public-safe metadata plus a relative public blob URL;
- map display payloads contain public-safe map metadata, grid render settings, and a relative public blob URL;
- `/api/player-display/assets/{asset_id}/blob` serves only assets referenced by the active public display payload, including image/map assets, public token portraits, public party portraits/image fields, and public initiative portraits;
- browser transport is notify-only and carries heartbeat/revision messages, not display payloads;
- `/player` refetches public display state after notifications and on polling fallback;
- `/player` does not fetch private campaign, scene, or GM runtime APIs;
- blackout is a pure black safe state;
- initial backend failure is visually degraded, while later refetch failure preserves last known public state.

### 4.4 Map Context

Owns map assets, fog, tokens, layers, and map rendering.

Entities:
- `MapAsset`
- `MapSceneState`
- `GMMapViewState`
- `PlayerMapViewState`
- `FogMask`
- `Token`
- `MapLayer`

Responsibilities:
- render full GM map;
- render sanitized player map view;
- edit fog masks;
- manage tokens and token visibility;
- grid calibration;
- player display fit/fill/scaling metadata.

MVP map model should avoid dynamic lighting, walls, doors, and token vision simulation.

Current implementation:
- map images are imported through the Asset context as `map_image` assets;
- campaign maps reference validated image assets and store square grid calibration;
- scene maps assign campaign maps to scenes;
- one active scene map per scene is enforced by a SQLite partial unique index;
- scene map activation is transactional;
- scene activation affects GM runtime only and does not publish to `/player`;
- `show-map` publishes public display state only and never mutates `app_runtime` or scene-map activation;
- explicit `scene_map_id` publishing is allowed without changing active scene map state;
- scene-map fog masks store durable public visibility as internal grayscale PNGs;
- fog operations use intrinsic map pixel coordinates and commit on pointer-up/action, not during every drag frame;
- public fog mask bytes are served only when referenced by the current active player display payload;
- scene-map tokens use intrinsic map pixel coordinates with `x/y` as center point, `width/height` as rendered size, and rotation around center;
- generated battle-map category keys may provide default square grid calibration, but the renderer still overlays the grid live rather than relying on baked-in grid pixels;
- gridless generated maps should be calibrated in the GM map workbench by changing live grid size and offsets, not by rewriting the source image or changing token/fog coordinate space;
- token visibility is sanitized before public display:
  - `gm_only` never appears in player payloads;
  - `player_visible` appears even under fog;
  - `hidden_until_revealed` appears only when token center is visible in the fog mask;
  - labels appear only when `label_visibility = player_visible`;
- public token portrait assets are served only when referenced by the current active player display payload;
- the shared map renderer accepts sanitized render props and renders image, grid, optional fog, and token overlays;
- missing map blobs/assets degrade intentionally instead of publishing a blank map as success.

### 4.5 Entity Context

Owns campaign objects and typed custom fields.

Entities:
- `Entity`
- `CustomFieldDefinition`
- `CustomFieldValue`
- `PartyTrackerConfig`
- `PartyTrackerMember`
- `PartyTrackerField`

MVP entity types:
- `pc`
- `npc`
- `creature`
- `location`
- `item`
- `handout`
- `faction`
- `vehicle`
- `generic`

Responsibilities:
- system-agnostic typed fields;
- explicit public/private entity visibility;
- entity portrait references through managed assets;
- optional token/entity linkage;
- party tracker roster and card field configuration;
- future bestiary/import support.

Current implementation:
- entities are campaign-scoped and default to `private`;
- custom field definitions are campaign-scoped typed primitives with immutable key/type;
- custom field values are validated JSON and apply only to configured entity kinds;
- the party tracker uses an explicit ordered PC roster rather than inferring all PCs;
- party card fields are ordered and have independent `public_visible` flags;
- `show-party` builds public payloads through a strict sanitizer:
  - only roster entities with `visibility = public_known`;
  - only selected fields with `public_visible = true`;
  - no entity notes, tags, private entities, non-roster entities, or private field values;
  - portraits and image fields expose URLs only for `public_displayable` image assets;
- `/player` party mode renders only sanitized party cards and never calls private entity APIs.

### 4.6 Notes Context

Owns private GM notes and explicit public snippet snapshots.

Entities:
- `NoteSource`
- `Note`
- `PublicSnippet`

Responsibilities:
- local markdown upload/path import by copying text into SQLite;
- private note viewing/editing;
- explicit public snippet creation from selected text or direct entry;
- linking notes to sessions, scenes, and assets;
- sending snippets to player display.

Current implementation:
- `note_sources` stores campaign-scoped source metadata and source labels only.
- `notes` stores private title/body/tags plus optional session, scene, and asset links.
- `public_snippets` stores public title/body/format snapshots and optional `note_id` traceability.
- A snippet is not a live view over a note. Updating a private note does not update existing snippets.
- `show-snippet` builds player display payloads only from `public_snippets`; the payload does not include `note_id`.
- GM preview and `/player` text mode share a safe markdown renderer with raw HTML disabled and inert links.

### 4.7 Canvas Context

Owns GM layout and widget instances.

Entities:
- `Canvas`
- `CanvasWidgetInstance`
- `Layout`
- `FocusMode`

Responsibilities:
- pan/zoom;
- draggable/resizable widgets;
- saved layouts;
- locked Run Mode;
- widget focus/search;
- scene-specific layout restoration.

Canvas is an organization layer, not the domain model. Widgets render state owned by other contexts.

Current implementation:
- `/gm` is a docked laptop-friendly GM overview.
- Focused GM routes own dense workflows: `/gm/map`, `/gm/library`, `/gm/actors`, `/gm/combat`, and `/gm/scene`.
- The original large positioned draggable/resizable workspace remains available at `/gm/floating`.
- Widget layout is persisted in SQLite through `workspace_widgets`.
- Slice 3 uses only global layout scope, but the schema already supports future campaign or scene scopes.
- Layout PATCH is performed on drag/resize stop; pointer movement updates only local UI state.
- Failed layout saves leave the local position in place and show an unsaved indicator.
- Floating widgets remain an advanced organization layer, not the map engine or default laptop workflow.

### 4.8 Tools Context

Owns lightweight live-session tools.

Initial tools:
- party tracker;
- combat tracker;
- dice roller;
- timer/clock;
- soundboard later;
- weather/time later.

Tools should use shared primitives:
- entities;
- scenes;
- player display actions;
- custom fields;
- command registry.

### 4.9 Command Context

Owns global actions, command palette, and hotkeys.

Entities:
- `Command`
- `CommandInvocation`
- `HotkeyBinding`

Responsibilities:
- command palette;
- hotkey routing;
- display safety commands;
- widget actions;
- scene actions;
- undoable operations where appropriate.

## 5. Major Data Flow

### 5.1 Send Map To Player Display

```text
GM clicks Send Scene Map
  -> /api/player-display/show-map validates scene map and active blob
  -> backend writes player_display_runtime(mode="map")
  -> GM browser sends notify-only transport message
  -> /player refetches public display state
  -> /player renders sanitized map payload through shared map renderer
  -> /gm display widget updates from heartbeat/public display state
```

Private data never travels to `/player`.

### 5.2 Fog Reveal

```text
GM edits FogMask in MapContext
  -> MapContext updates durable fog state
  -> if /player is showing that scene map, DisplayManager republishes active map state
  -> /player updates revealed view
  -> /gm preview/status updates
```

Current MVP publish happens on committed operations. During drag, GM preview may update locally, but browser transport remains notify-only and does not carry fog payloads or mask bytes.

### 5.3 Send Note Snippet

```text
GM selects markdown text
  -> NotesContext copies selected text into PublicSnippet.body
  -> GM previews PublicSnippet through safe markdown renderer
  -> GM publishes explicit snippet
  -> DisplayManager writes text mode to player_display_runtime
  -> /player renders snippet only
```

The full private note body is never used as display payload input. Public snippets are snapshots, not live note ranges.

The full note body is never sent to player display.

### 5.4 Publish Party Cards

```text
GM edits Entities and CustomFieldValues
  -> GM configures PartyTracker roster and public-visible card fields
  -> GM publishes party
  -> DisplayManager writes party mode to player_display_runtime
  -> /player renders sanitized party cards only
```

The public party payload is built from the party tracker sanitizer, not raw entity records. Entity notes, tags, private entities, private fields, and non-roster entities do not enter the display payload.

Combat tracker implementation:

```text
GM creates encounter
  -> adds manual/entity/token combatants
  -> controls order, round, active turn, HP/AC/private conditions/public status
  -> publishes initiative explicitly
  -> DisplayManager writes initiative mode to player_display_runtime
  -> /player renders sanitized order/current turn only
```

The public initiative payload is built from a combat sanitizer, not raw encounter rows. `combatants.public_visible` is the only public initiative gate. Linked public tokens or public-known entities may seed defaults when a combatant is created, but do not remain live bindings. Public initiative excludes HP, AC, temp HP, private conditions, combat notes, entity tags, private fields, and hidden combatants.

### 5.5 Activate Scene

```text
GM activates Scene
  -> AppRuntime sets active scene
  -> SceneContext loads linked notes/entities/snippets/active encounter
  -> Widgets focus the selected scene
  -> DisplayManager leaves player_display_runtime unchanged
  -> GM sees active scene cockpit
```

Scene activation never automatically reveals new player-facing content.

Publishing staged scene display is a separate command:

```text
GM clicks Publish Staged Display
  -> /api/scenes/{scene_id}/publish-staged-display validates staged mode readiness
  -> existing map/snippet/initiative/scene-title/intermission/blackout display path runs
  -> player_display_runtime changes only after successful publish
  -> /player refetches public display state
```

Scene context is GM-private. It can contain linked entities, notes, snippets, active encounter references, and staging metadata, but `/player` never fetches scene context APIs.

## 6. Storage Strategy

### 6.1 MVP Storage

Current MVP implementation default:
- SQLite stores structured campaign data.
- Alembic owns schema migrations from day one.
- Existing non-empty DB files are backed up before migration.
- Filesystem storage under `data/assets/` stores large asset blobs.
- SQLite stores asset metadata and relative paths.
- Asset blobs use content-addressed managed paths and are written temp-file-first.
- Browser storage is cache/runtime only unless a later decision changes this.

SQLite runtime requirements:

```text
PRAGMA foreign_keys = ON
PRAGMA journal_mode = WAL
PRAGMA synchronous = NORMAL
PRAGMA busy_timeout = 5000
```

These PRAGMAs must be applied on every SQLAlchemy connection through an event hook.

### 6.2 Browser Storage Context

Do not use IndexedDB as the source of truth for structured campaign data in the current implementation.

Browser storage may still be useful for:
- UI cache;
- layout drafts before persistence;
- temporary previews;
- display runtime convenience;
- offline artifacts if explicitly designed later.

If browser storage is used for important cache/runtime artifacts, the app should still surface persistence status where relevant. It must not imply that browser persistence protects the durable campaign database.

### 6.3 File System Access

Browser File System Access API can be an optional enhancement for Chromium-based browsers:
- open local markdown folder/vault;
- read/write note files;
- preserve Obsidian vault structure.

Fallback:
- import markdown files;
- store local copies;
- export later.

The app should not make direct file-system support mandatory for MVP.

### 6.4 Persistence Requirements

Persist:
- campaigns;
- scenes;
- assets;
- fog masks;
- token positions/visibility;
- player display last state;
- display history/undo stack;
- canvas layouts;
- custom fields;
- notes/snippets.

Do not persist:
- transient hover state;
- selection state unless useful;
- open context menus;
- temporary previews unless intentionally staged.

### 6.5 Storage Health

The app should maintain a storage health view model:

```text
Storage Health:
  persistence: persistent / best-effort / unsupported / unknown
  estimated usage
  estimated quota
  last backup/export
  last write error
```

If persistence is `best-effort`, the GM workspace should show a visible warning until dismissed for the session. For critical campaign work, the app should keep nudging toward export/backup.

### 6.6 Backup, Export, And Restore

Slice 13 adds a local safety layer around the SQLite/filesystem persistence model:

- `POST /api/storage/backup` snapshots the current SQLite DB into `data/backups/`.
- `POST /api/storage/export` creates an atomic `myroll.<timestamp>.export.tar.gz` archive.
- Export archives contain:
  - `myroll-export.json`;
  - SQLite snapshot under `db/myroll.sqlite3`;
  - managed `assets/` files, excluding `.tmp`;
  - checksums and byte sizes.
- `GET /api/storage/status` reports shortened paths, DB/asset sizes, schema/seed versions, latest backup/export, profile hint, and demo local-demo-override status.
- Restore is offline/script-only through `scripts/restore_export.sh <archive> <target-data-dir>`.

Restore validates tar paths against traversal and refuses non-empty targets unless explicitly forced. There is no in-place live restore and no GM UI restore button in Slice 13. Export archives are local convenience packages, not encrypted vaults.

### 6.7 Demo Profile

The committed demo is an original public profile named `Chronicle of the Lantern Vale`.

Demo rules:

- demo reset uses isolated `data/demo` by default;
- normal dev seed is disabled during demo reset;
- generated assets are stored under `demo/assets/generated/lantern_vale_chronicle/`;
- demo reset imports those images through the same image validation and managed asset pipeline as user assets;
- local demo display-name overrides are local-only overrides in ignored `demo/local/name-map.private.json`;
- the committed template `demo/local/name-map.example.json` stays public-safe.

Public demo exports should be generated without a local demo override map. Exports created while a local demo override map is active may contain those local display names.

## 7. Inter-Window Communication

### 7.1 MVP Transport

Use a layered transport for communication between `/gm` and `/player`.

Transport order:
1. `window.postMessage()` when `/gm` opened `/player` and holds a `WindowProxy` reference.
2. `BroadcastChannel` for same-origin, same-storage-partition windows.
3. Durable active display state in the local backend/SQLite store as reconnect/sync backup.

`BroadcastChannel` is convenient but only works for compatible same-origin contexts in the same storage partition. Private/incognito windows, separate browser profiles, and some embedded/partitioned contexts can break this assumption. `postMessage()` is a useful fallback for opener-managed player windows and supports transferables for heavy binary payloads, but it requires strict `origin` and `source` validation.

Channel names should include campaign or app instance identity:

```text
myroll:{campaignId}:display
```

Messages:
- `DISPLAY_STATE_PUBLISHED`
- `DISPLAY_BLACKOUT`
- `DISPLAY_IDENTIFY`
- `DISPLAY_HEARTBEAT`
- `DISPLAY_CONNECTED`
- `DISPLAY_DISCONNECTED`
- `DISPLAY_REQUEST_SYNC`

### 7.2 Transport Capabilities

Transport capabilities should be explicit:

```text
DisplayTransport:
  kind: postMessage | broadcastChannel | storageSync
  supportsTransferables: boolean
  requiresWindowReference: boolean
  crossesStoragePartition: boolean
```

MVP expected capabilities:
- `postMessage`: supports transferables, requires a window reference, can work across origins if explicitly allowed, but Myroll should use exact same-origin validation.
- `BroadcastChannel`: no window reference needed, good for normal same-profile tabs/windows, but no cross-partition guarantee.
- `storageSync`: slow fallback only; useful for reconnecting, not live fog.

### 7.3 Persistence Backup

Because a player window can refresh or reconnect, active `PlayerDisplayState` should also be stored durably through the local backend.

On `/player` load:
1. read active display state;
2. request sync through available transport;
3. render latest sanitized state.

### 7.4 Future Transports

Possible later:
- `SharedWorker` for stronger multi-window coordination;
- local WebSocket if packaged as desktop;
- WebRTC only if true remote player display becomes a product goal.

Do not introduce these for MVP unless needed.

## 8. Rendering Architecture

### 8.1 Shared Public Renderers

Public renderers should be shared by:
- `/player`;
- GM preview pane.

Examples:
- `PlayerDisplayRenderer`
- `PublicMapRenderer`
- `PublicHandoutRenderer`
- `PublicTextRenderer`
- `PublicPartyRenderer`
- `PublicInitiativeRenderer`
- `PublicTimerRenderer`

These renderers accept sanitized public view models only.

### 8.2 Private GM Renderers

GM renderers can access full domain state:
- `GMMapWidget`
- `FogEditor`
- `NotesWidget`
- `EntityInspector`
- `PartyTrackerWidget`
- `CombatTrackerWidget`
- `DisplayStatusPanel`

Private renderers must not be reused directly in `/player`.

### 8.3 Map Rendering

MVP can use Canvas 2D or DOM/SVG overlays over an image.

Recommendation:
- use Canvas 2D for map image, fog mask, grid, and token layer if performance matters;
- use DOM/SVG for controls and maybe labels if easier;
- keep renderer abstraction so implementation can change.

Avoid early WebGL unless needed.

### 8.4 Live Fog Transport

Live fog updates must not serialize and broadcast full raster masks during pointer drag.

During drag:
- send compact vector operations such as `reveal_brush`, `hide_brush`, `reveal_rect`, and `hide_rect`;
- let `/player` apply those operations to its local fog canvas;
- throttle operation messages to a sane rate;
- keep GM rendering immediate.

Current MVP does not use live drag transport. It persists and republishes only when the operation is committed.

On pointer-up or debounce:
- persist the authoritative fog mask;
- send a compact raster snapshot or storage reference for resync;
- prefer `Blob`, `ArrayBuffer`, `ImageBitmap`, or an asset reference over base64/Data URL transport;
- use transferables when using `postMessage()`.

Data URLs and repeated full-canvas serialization are forbidden in live fog paths.

## 9. Safety Boundaries

### 9.1 Presentation Boundary Vs Security Boundary

The MVP safety model is accidental-reveal prevention, not adversarial client security.

`/player` should be treated as:
- a public presentation renderer;
- a projection/screen-share target;
- a sanitized rendering path;
- a same-machine companion window.

`/player` should not be treated as:
- a trusted remote player client;
- a permissioned user role;
- a browser-isolated private-data boundary;
- a replacement for server-side authorization.

This distinction must remain visible in product copy, technical docs, and future planning.

Future remote player clients need a different architecture:
- server or host process sends sanitized public payloads only;
- player clients have no local access to private campaign storage;
- authentication and authorization exist outside the shared browser app;
- private and public data are separated before reaching the untrusted client.

### 9.2 Sanitized View Models

Anything sent to `/player` must pass through a sanitizer/projection function.

Example:

```text
MapSceneState + EntityStore + FogMask
  -> createPlayerMapPayload()
  -> PlayerMapPayload
```

The payload includes:
- public map asset reference;
- visible fog mask/render data;
- player-visible tokens only;
- public labels only;
- public overlays only;
- display fit/fill settings.

The payload excludes:
- GM notes;
- hidden tokens;
- GM-only labels;
- unrevealed map annotations;
- private entity fields;
- source note bodies.

### 9.3 Display History

Display-changing actions should record history:
- previous state;
- next state;
- action name;
- timestamp;
- sceneId;
- source object.

MVP history depth can be small, e.g. 10 states.

Blackout should not destroy history. It should be reversible.

### 9.4 Explicit Public Marking

Only explicit public snippets/assets should be displayable from notes.

Images and handouts can be marked:
- private;
- staged;
- public-displayable.

## 10. Suggested Folder Architecture

This is framework-neutral, but assumes a TypeScript web app.

```text
src/
  app/
    routes/
      gm/
      player/
  domains/
    campaign/
    scene/
    display/
    map/
    entity/
    notes/
    canvas/
    tools/
    command/
  components/
    gm/
    player/
    shared/
  storage/
    indexedDb/
    assetStore/
    migrations/
  messaging/
    broadcastChannel/
  renderers/
    public/
    gm/
  state/
    stores/
    selectors/
  tests/
```

The key rule:

```text
domains/* owns data and operations.
components/* owns rendering and interaction.
storage/* owns persistence.
messaging/* owns cross-window communication.
```

## 11. Technology Assumptions

Recommended stack, subject to final implementation choice:
- TypeScript;
- React;
- Vite for MVP speed unless SSR/routing needs justify Next;
- TanStack Query for backend state;
- FastAPI local backend;
- SQLite durable source of truth;
- Alembic migrations;
- filesystem asset blob storage;
- Canvas 2D for map/fog rendering;
- layered display transport: `postMessage`, `BroadcastChannel`, and storage sync fallback;
- Playwright for visual/end-to-end display tests.

The earlier browser-only IndexedDB persistence assumption has been superseded. Browser storage is cache/runtime convenience only unless a future decision changes that boundary.

## 12. Testing Strategy

### 12.1 Unit Tests

Test:
- display state reducers;
- map payload sanitization;
- token visibility filtering;
- fog mask operations;
- fog operation serialization;
- storage persistence health reducer;
- display transport selection;
- public snippet snapshot and text payload safety;
- custom field validation;
- command registry behavior.

### 12.2 Integration Tests

Test:
- send map to player;
- blackout and undo;
- fog reveal updates player payload;
- fog drag sends vector operations, not raster snapshots;
- hidden token is not included in player payload;
- note snippet sends only snippet;
- scene activation restores correct state.
- storage persistence denial shows volatile-storage warning.

### 12.3 Browser/E2E Tests

Use Playwright:
- open `/gm`;
- run the cockpit create/activate/layout-persist flow;
- screenshot healthy and degraded GM states;
- open `/player` as second page/window;
- send display state;
- screenshot both surfaces;
- assert GM sees full map;
- assert player sees only public view;
- assert blackout hides all public content;
- assert preview matches player output.
- assert display reconnect works after `/player` refresh.
- assert stale heartbeat marks display disconnected.

Visual regression tests are especially valuable for public/private display separation.

## 13. Development Slices

The authoritative implementation order is maintained in `ROADMAP.md`. Current high-level order:

1. Local backend foundation: complete.
2. Backend writes and runtime activation: complete.
3. GM frontend shell with persistent workspace canvas: complete.
4. Local player display service: complete.
5. Asset metadata and image display: complete.
6. Map display MVP: complete.
7. Manual fog MVP: complete.
8. Tokens and visibility: complete.
9. Notes and public snippets: complete.
10. Entities, custom fields, party tracker, and public party projection: complete.
11. Combat tracker basics and public initiative projection: complete.
12. Scene orchestration and GM context staging: complete.
13. Backup, export, restore, and public demo hardening: complete.
14. Multi-surface GM shell rework: complete.
15. Asset import, battle-map pack import, and grid calibration: proposed.
16. LLM session memory and GM generation harness: queued unless asset import takes precedence.

## 14. Architectural Anti-Goals

Do not build in MVP:
- server-side sync;
- player accounts;
- multi-user permissions;
- dynamic lighting;
- walls/doors;
- marketplace/plugin API;
- rule automation engine;
- full remote VTT protocol.

Avoid irreversible architecture choices that make these impossible later, but do not pay their complexity cost now.
