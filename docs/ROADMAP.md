# Myroll Roadmap

Date: 2026-04-27

## Current Direction

Myroll is now planned as a local-first desktop-ish web app:

```text
SQLite = durable source of truth
FastAPI = local control plane
Filesystem = asset blob storage
Browser = UI/runtime/cache
```

The original browser-only IndexedDB model is no longer the durable persistence foundation for campaign data.

## Slice 1: Local Backend Foundation

Goal: prove a clean local bootstrap path.

Status: complete.

Deliver:
- FastAPI backend scaffold.
- SQLite database with Alembic migrations.
- SQLAlchemy connection PRAGMAs on every connection.
- Pre-migration backup for existing non-empty DB files.
- Idempotent transactional demo seed.
- Read-only health/meta/campaign/scene APIs.
- Portable `scripts/start_backend.sh`.
- Backend tests using temporary databases only.

Done when:
- clean checkout can run the backend through the start script;
- DB migrates and seeds once;
- `/health` and `/api/meta` report useful local state;
- `/api/campaigns` returns the deterministic demo campaign;
- tests are green.

## Slice 2: Backend Writes And Runtime Activation

Status: complete.

Delivered:
- campaign, session, and scene creation APIs;
- singleton `app_runtime` table;
- runtime activation action endpoints;
- runtime response with active IDs and labels;
- standard API error envelope;
- seed upgrade to `2026-04-27-v2`;
- tests for writes, runtime activation, validation, and safe database errors.

## Slice 3: GM Frontend Shell With Persistent Canvas

Status: complete.

Delivered:
- Vite + React + TypeScript frontend scaffold under `frontend/`.
- `scripts/start_dev.sh` for backend + Vite local development.
- `/gm` as the first usable browser surface.
- Persistent `workspace_widgets` backend model with future scope support:
  - `scope_type = "global"` and `scope_id = null` in Slice 3;
  - future `campaign` and `scene` layouts can use the same primitive.
- Workspace widget APIs:
  - `GET /api/workspace/widgets`;
  - `PATCH /api/workspace/widgets/{widget_id}`;
  - `POST /api/workspace/widgets/reset`.
- Deterministic default cockpit widgets:
  - functional: backend status, campaigns, sessions, scenes, runtime;
  - disabled placeholders: map display, notes, party tracker, combat tracker, dice roller.
- Drag/resize layout editing:
  - frontend updates local position immediately;
  - backend PATCH only runs on drag/resize stop;
  - failed saves keep local layout and show an unsaved indicator.
- Campaign/session/scene creation from the cockpit.
- Runtime activation and clear actions from the cockpit.
- Backend unavailable state that still renders a degraded GM shell.
- `VITE_API_BASE_URL` support with same-origin Vite proxy as the default.
- Playwright visual/e2e coverage for:
  - healthy `/gm` cockpit;
  - create campaign/session/scene;
  - activate scene;
  - refresh and recover runtime/layout;
  - degraded backend-unavailable shell.
- Reference screenshots under `artifacts/playwright/`.

Acceptance checkpoint:

```text
start dev stack
  -> open /gm
  -> backend status is visible
  -> create campaign
  -> create session
  -> create scene
  -> activate scene
  -> runtime panel updates from returned backend state
  -> move/resize a widget
  -> refresh page
  -> active runtime and widget layout persist
  -> Playwright screenshots confirm the visible UI state
```

Explicit deferrals retained:
- no `/player` route yet;
- no map/image import;
- no real notes backend;
- no real party/combat/dice domain behavior;
- no pan/zoom/minimap/focus modes/snap guides;
- no auth;
- no Docker;
- no browser storage as campaign source of truth.

## Slice 4: Local Player Display Service

Status: complete.

Delivered:
- `/player` fullscreen public presentation route.
- Backend singleton `player_display_runtime` as public display source of truth.
- Display modes:
  - `blackout`;
  - `intermission`;
  - `scene_title`.
- GM `Player Display` cockpit widget:
  - open/reconnect player window;
  - heartbeat status;
  - identify;
  - blackout;
  - intermission;
  - show active scene title.
- Local transport:
  - `postMessage` for opener-managed player windows;
  - `BroadcastChannel` fallback for same-profile windows;
  - browser messages carry notifications/heartbeat only;
  - `/player` refetches backend truth.
- Failure handling:
  - initial `/player` backend failure renders an intentional degraded screen;
  - later refetch failure keeps the last successful public state;
  - blackout remains pure black.
- Playwright visual/e2e screenshots for connected GM, intermission, scene title, identify, blackout, degraded initial failure, and reconnecting last-known-state.

Acceptance checkpoint:

```text
start dev stack
  -> open /gm
  -> click Open Player Display
  -> /player opens as blackout/intermission
  -> identify display
  -> blackout from GM
  -> refresh /player
  -> /player reconnects to latest public state
```

Explicit deferrals:
- no remote public URL;
- no WebRTC/relay/TURN;
- no map rendering yet;
- no audio implementation yet, but keep tab-sharing audio in mind for future soundboard.

## Slice 5: Asset Metadata And Image Display

Goal: create the bridge from local files to public displayable content.

Status: complete.

Delivered:
- Expanded asset metadata in SQLite:
  - name;
  - visibility;
  - original filename;
  - tags;
  - duration placeholder;
  - image dimensions;
  - checksum and managed relative storage path.
- Managed filesystem blob storage under `data/assets/`.
- Browser upload for PNG, JPEG, and WebP.
- Server-path import was removed after security review; uploads are the supported user-consent boundary.
- Defensive backend validation:
  - MIME type, extension, filename, width, and height are not trusted;
  - Pillow derives actual image format and dimensions;
  - 25 MB file limit;
  - 50 megapixel decoded image limit;
  - decompression bomb warnings/errors are rejected;
  - blob writes are temp-file-first and content-addressed.
- Asset APIs:
  - `GET /api/campaigns/{campaign_id}/assets`;
  - `POST /api/campaigns/{campaign_id}/assets/upload`.
- Player display image APIs:
  - `POST /api/player-display/show-image`;
  - `GET /api/player-display/assets/{asset_id}/blob`.
- Public blob endpoint only serves the currently active public image in `player_display_runtime`.
- GM `Asset Library` widget:
  - upload image;
  - set kind/visibility/name/tags;
  - list assets;
  - send public-displayable image to `/player`.
- `/player` image mode with fit/fill/stretch/actual-size rendering.
- Playwright screenshots for image display, image blob failure, and blackout recovery.

Acceptance checkpoint:

```text
import image
  -> asset metadata persists in SQLite
  -> blob exists under data/assets
  -> send image to player display
  -> /player shows image only
  -> blackout still works
```

Explicit deferrals:
- no full map model yet;
- no fog;
- no token layers.

## Slice 6: Map Display MVP

Goal: turn images into scene-linked maps with separate GM and player render paths.

Status: complete.

Delivered:
- `maps` and `scene_maps` backend schema with Alembic migration `20260427_0006`.
- One active scene map per scene enforced with a SQLite partial unique index.
- Transactional scene map activation:
  - assignment with `is_active = true` uses the same activation helper;
  - activate map A then map B leaves only B active.
- Map APIs:
  - `GET /api/campaigns/{campaign_id}/maps`;
  - `POST /api/campaigns/{campaign_id}/maps`;
  - `GET /api/campaigns/{campaign_id}/scenes/{scene_id}/maps`;
  - `POST /api/campaigns/{campaign_id}/scenes/{scene_id}/maps`;
  - `PATCH /api/maps/{map_id}/grid`;
  - `PATCH /api/scene-maps/{scene_map_id}`;
  - `POST /api/scene-maps/{scene_map_id}/activate`.
- Public display API:
  - `POST /api/player-display/show-map`.
- `player_display_runtime.mode` now supports `map`.
- `show-map` publishes public display state only:
  - it does not mutate `app_runtime`;
  - it does not activate/deactivate scene maps;
  - empty body uses active runtime scene plus that scene's active map;
  - explicit `scene_map_id` publishes that scene map without side effects.
- Public map payload contains only sanitized display data:
  - scene map ID;
  - map ID;
  - asset ID;
  - relative active-only blob URL;
  - image dimensions;
  - title;
  - fit mode;
  - square grid render settings.
- Public blob endpoint still serves only the current active player-display image/map asset.
- Grid settings are validated and normalized:
  - size bounded to 4..500 px;
  - offsets must be finite;
  - opacity bounded to 0..1;
  - color normalized to safe `#RRGGBB`.
- GM `Map Display` widget is functional:
  - list `map_image` assets;
  - create campaign maps;
  - assign maps to the selected scene;
  - activate scene map;
  - edit grid calibration;
  - edit player fit/grid visibility;
  - send selected scene map to `/player`.
- Shared map renderer:
  - accepts sanitized render props, not raw backend records;
  - renders HTML image plus SVG square grid overlay;
  - handles image/map unavailable states intentionally.
- `/player` renders map mode and preserves identify/reconnect behavior.
- Playwright screenshots for map display:
  - `player-map-fit-grid.png`;
  - `player-map-unavailable.png`;
  - `player-map-blackout.png`.

Acceptance checkpoint:

```text
assign map to scene
  -> activate scene
  -> GM sees full map
  -> send map to player
  -> /player shows clean map on black presentation background
```

Explicit deferrals:
- no fog editing yet;
- no tokens yet;
- no pan/zoom, minimap, measuring, dynamic lighting, walls, doors, or line of sight.

## Slice 7: Manual Fog MVP

Goal: prove the core public/private map safety feature.

Status: complete.

Delivered:
- `scene_map_fog_masks` backend schema with Alembic migration `20260427_0007`.
- One durable fog mask per scene map.
- Internal managed grayscale PNG masks under the asset directory:
  - `0` hidden;
  - `255` visible;
  - dimensions locked to campaign map dimensions.
- Fog starts hidden-all.
- Private fog APIs:
  - `GET /api/scene-maps/{scene_map_id}/fog`;
  - `POST /api/scene-maps/{scene_map_id}/fog/enable`;
  - `POST /api/scene-maps/{scene_map_id}/fog/operations`;
  - `GET /api/scene-maps/{scene_map_id}/fog/mask`.
- Public active-only fog endpoint:
  - `GET /api/player-display/fog/{fog_mask_id}/mask`.
- Fog operations in intrinsic map pixel coordinates:
  - reveal/hide rectangle;
  - reveal/hide hard brush;
  - reveal all;
  - hide all.
- Fog operation commit persists the mask and increments fog revision.
- If `/player` is currently showing the same scene map, fog operation commit republishes `player_display_runtime` with updated fog payload.
- Browser transport remains notify-only; no fog payloads, mask bytes, or raster snapshots travel over `postMessage`/`BroadcastChannel`.
- GM map preview:
  - full map remains visible;
  - hidden player areas render as tint overlay;
  - failed save keeps local draft and shows unsaved/error state.
- `/player` map renderer:
  - masks map image with public fog mask;
  - keeps public/private boundary through sanitized map payload;
  - shows intentional unavailable state if fog mask bytes fail.
- Playwright screenshots:
  - `gm-fog-edit-overlay.png`;
  - `player-fog-reveal-rect.png`;
  - `player-fog-hide-rect.png`;
  - `player-fog-brush.png`;
  - `player-fog-mask-unavailable.png`.

Acceptance checkpoint:

```text
GM sees full map
  -> player sees hidden/fogged map
  -> GM reveals rectangle
  -> player display updates
  -> hidden regions remain visible to GM only
  -> blackout still works instantly
```

Explicit deferrals:
- no tokens;
- no polygon reveal;
- no soft brush or opacity brush;
- no live fog transport during drag;
- no base64/Data URL fog transport;
- no pan/zoom, minimap, measuring, dynamic lighting, walls, doors, or line of sight.

## Slice 8: Tokens And Visibility

Goal: add map tokens without breaking the public/private boundary.

Status: complete.

Delivered:
- `scene_map_tokens` backend schema with Alembic migration `20260427_0008`.
- Token coordinates use intrinsic map pixels:
  - `x/y` are token center point;
  - `width/height` are rendered token size;
  - `rotation` is around token center.
- Token APIs:
  - `GET /api/scene-maps/{scene_map_id}/tokens`;
  - `POST /api/scene-maps/{scene_map_id}/tokens`;
  - `PATCH /api/tokens/{token_id}`;
  - `DELETE /api/tokens/{token_id}`.
- Shape and portrait tokens:
  - `circle`;
  - `square`;
  - `marker`;
  - `portrait`.
- Token visibility:
  - `gm_only`;
  - `player_visible`;
  - `hidden_until_revealed`.
- Label visibility:
  - `gm_only`;
  - `player_visible`;
  - `hidden`.
- Centralized public map sanitizer:
  - filters hidden tokens;
  - omits private labels;
  - includes `hidden_until_revealed` tokens only when their center point is visible in the fog mask;
  - includes public portrait asset URLs only when they are safe for the active public display payload.
- Active-only public asset serving now supports token portrait assets referenced by the current public map payload.
- Token mutations compare old/new sanitized public map payload and republish `player_display_runtime` only when the public payload changes.
- GM Map Display token controls:
  - create token at center or by map click;
  - select token from list/map;
  - drag to move;
  - drag corner to resize;
  - rotate with numeric control;
  - edit visibility, label visibility, shape, color, opacity, and portrait asset;
  - delete token.
- Shared map renderer renders token layer above map/fog/grid and falls back from failed portrait images to styled markers.
- `/player` renders tokenized map payloads from sanitized public display state only.
- Browser transport remains notify-only and carries no token payload, labels, asset IDs, or coordinates.
- Backend tests cover token schema, validation, public sanitizer behavior, fog-gated token reveal, active-only portrait serving, republish semantics, and timestamp serialization.
- Frontend tests cover token API calls, GM token editing behavior, renderer public/private behavior, failed token saves, and portrait fallback.
- Playwright product QA covers:
  - GM token editing;
  - player-visible token with hidden label;
  - public portrait token;
  - fog-revealed hidden token.

Acceptance checkpoint:

```text
add hidden token
  -> GM sees it
  -> player does not
make token public
  -> player sees it
hide label
  -> player sees token without private label
create hidden-until-revealed token
  -> fog reveal makes it public
create portrait token
  -> public token portrait blob is served only while referenced by active player display
```

## Slice 9: Notes And Public Snippets

Goal: make text reveals and handouts first-class public display content without exposing private notes.

Status: complete as of Slice 9.

Delivered:
- SQLite-backed private notes with optional campaign/session/scene/asset links;
- markdown upload that copies text into SQLite and keeps only a source label, not a live filesystem dependency;
- server-path note import was removed after security review; uploads are the supported user-consent boundary;
- explicit public snippet records created from note text or entered directly;
- "copy selection to snippet" snapshots selected note text into `public_snippets.body` at that moment;
- GM Notes widget for browse/create/edit/import, snippet preview, and explicit publish;
- `/player` text mode for public snippet projection;
- shared safe markdown renderer with raw HTML disabled and links rendered inert;
- display action that builds player payloads only from `public_snippets.title/body/format`, never the full source note.
- seed upgrade to `2026-04-27-v9` with deterministic demo note/snippet and no overwrite of user edits.
- private GM note/snippet APIs:
  - `GET /api/campaigns/{campaign_id}/notes`;
  - `POST /api/campaigns/{campaign_id}/notes`;
  - `GET /api/notes/{note_id}`;
  - `PATCH /api/notes/{note_id}`;
  - `POST /api/campaigns/{campaign_id}/notes/import-upload`;
  - `GET /api/campaigns/{campaign_id}/public-snippets`;
  - `POST /api/campaigns/{campaign_id}/public-snippets`;
  - `PATCH /api/public-snippets/{snippet_id}`.
- public display API:
  - `POST /api/player-display/show-snippet`.
- public text payloads omit `note_id` and never expose private note body, source paths, tags, or private links.
- note updates do not mutate existing public snippet snapshots.
- `/player` text path fetches only public player-display state.
- Playwright product QA covers:
  - private note with secret text;
  - snippet created from safe selected text;
  - private note edited after snippet creation;
  - publish to `/player`;
  - refresh recovery;
  - blackout hiding public text.

Acceptance checkpoint:

```text
create/import private note containing secret text
  -> select only safe text
  -> snapshot selection into public snippet
  -> edit private note afterward
  -> publish snippet to player display
  -> /player shows only snippet content
  -> private note body and later edits are not present in public payload
  -> refresh /player
  -> text display recovers from backend state
  -> blackout still works
```

Explicit deferrals:
- no Obsidian/OneNote/Notion sync yet;
- no backlinks/frontmatter intelligence yet;
- no rich text editor beyond pragmatic markdown/plain text handling;
- no AI note generation.
- no authoritative range pointers;
- no note delete/archive.

## Slice 10: Entities, Custom Fields, Party Tracker, And Public Party Projection

Goal: establish system-agnostic entities and make party cards a real GM/player loop.

Status: complete as of Slice 10.

Delivered:
- `entities`, `custom_field_definitions`, `custom_field_values`, `party_tracker_configs`, `party_tracker_members`, and `party_tracker_fields` backend schema with Alembic migration `20260427_0010`.
- Entity kinds:
  - `pc`;
  - `npc`;
  - `creature`;
  - `location`;
  - `item`;
  - `handout`;
  - `faction`;
  - `vehicle`;
  - `generic`.
- Entity visibility defaults private:
  - `private`;
  - `public_known`.
- Typed custom fields:
  - `short_text`;
  - `long_text`;
  - `number`;
  - `boolean`;
  - `select`;
  - `multi_select`;
  - `radio`;
  - `resource`;
  - `image`.
- Custom field keys are campaign-unique lowercase slugs; key and field type are immutable after creation.
- Custom field values are validated JSON and only apply to configured entity kinds.
- Explicit party tracker roster:
  - one config per campaign;
  - Slice 10 roster accepts `pc` entities only;
  - ordered party members;
  - ordered card fields;
  - `party_tracker_fields.public_visible` gates public projection.
- `party_tracker` workspace widget is functional even if older persisted widget config still marks it as placeholder.
- Party widget supports entity create/edit, field definition management, typed field values, PC roster editing, card field visibility, layout selection, GM preview, and publish.
- `/api/player-display/show-party` publishes sanitized party cards.
- `/player` supports `party` mode and renders only the public party payload.
- Strict public party sanitizer:
  - includes only roster entities with `visibility = public_known`;
  - includes only selected party fields with `public_visible = true`;
  - excludes notes, tags, private entities, non-roster entities, and non-public field values;
  - includes portrait URLs only for `public_displayable` image assets;
  - image field values are converted to safe public asset metadata only when the referenced asset is public-displayable.
- Active-only blob serving now includes party portrait/image field assets referenced by the current active public `party` payload.
- Existing token `entity_id` reference validates same-campaign entity ownership, but token public expansion from entities remains deferred.

Acceptance checkpoint:

```text
create PC entity
  -> define typed custom fields
  -> enter field values
  -> add PC to explicit party roster
  -> mark selected fields public-visible
  -> publish party
  -> /player shows only public party cards
  -> private notes/tags/private fields are absent
  -> refresh /gm and /player
  -> entity, party config, and public display recover from SQLite
```

Explicit deferrals:
- no combat tracker;
- no initiative;
- no public entity browser;
- no bestiary import;
- no rules automation;
- no relationships UI;
- no entity delete/archive;
- no token stat sync;
- no health bars, auras, conditions UI, or combat integration.

## Slice 11: Combat Tracker Basics + Public Initiative Projection

Goal: add a live-session combat widget that is useful without becoming a full rules engine.

Status: complete as of Slice 11.

Delivered:
- `combat_encounters` and `combatants` backend schema with Alembic migration `20260427_0011`.
- `player_display_runtime.mode` now supports `initiative`.
- Combat encounters are campaign-scoped and may link to session and scene.
- Combatants may be manual, entity-linked, token-linked, or both.
- Combatants store:
  - initiative/order;
  - active turn relationship through the encounter;
  - disposition;
  - HP/current/max/temp;
  - AC;
  - private conditions;
  - curated public status;
  - private notes;
  - explicit public initiative visibility.
- Public initiative visibility is independent from linked entity or token visibility:
  - entity/token visibility can seed defaults at creation;
  - `combatants.public_visible` remains the only public initiative gate.
- Turn navigation:
  - order is controlled by `order_index`;
  - next/previous skip defeated combatants;
  - wrapping adjusts round correctly;
  - all-defeated/empty encounters clear active combatant without spinning the round.
- Private GM APIs:
  - encounter list/create/read/update;
  - combatant create/update/delete;
  - reorder;
  - next/previous turn.
- Public display API:
  - `POST /api/player-display/show-initiative`.
- Public initiative payload is sanitized:
  - includes only `public_visible` combatants;
  - excludes HP, temp HP, AC, private conditions, notes, entity tags, private fields, and hidden combatants;
  - includes only curated `public_status_json`;
  - portrait URLs are included only for active payload-referenced public-displayable image assets.
- Active-only player blob serving now includes initiative portraits referenced by the current active public `initiative` payload.
- `combat_tracker` workspace widget is functional even if older persisted widget config still marks it as placeholder.
- `/player` supports `initiative` mode and renders public order/current turn only.
- Playwright screenshots:
  - `gm-combat-tracker-editing.png`;
  - `gm-combat-tracker-after-refresh.png`;
  - `player-initiative-order.png`;
  - `player-initiative-blackout.png`.

Acceptance checkpoint:

```text
create encounter
  -> add party/NPC combatants
  -> reorder initiative
  -> advance active turn
  -> refresh browser
  -> encounter state persists
  -> publish initiative
  -> /player shows only public order/current turn
  -> private combat data does not leak
```

Explicit deferrals:
- no automated rule system;
- no damage formulas;
- no full condition engine;
- no saving throws or stat block import;
- no token stat sync;
- no health bars, auras, or condition badges on map tokens;
- no public HP/AC projection;
- no dynamic lighting or token vision.

## Slice 12: Scene Orchestration

Status: complete.

Goal: make scenes the private live-session context unit while preserving the core invariant:

```text
Scene activation != public display mutation
```

Delivered:
- Alembic migration `20260427_0012_scene_orchestration`.
- `scene_contexts` with one context row per scene.
- `scene_entity_links` for GM-private scene/entity relevance.
- `scene_public_snippet_links` for explicit scene/snippet staging.
- Deterministic `scene_context` workspace widget seed.
- Private GM APIs:
  - `GET /api/scenes/{scene_id}/context`;
  - `PATCH /api/scenes/{scene_id}/context`;
  - `POST /api/scenes/{scene_id}/entity-links`;
  - `DELETE /api/scene-entity-links/{link_id}`;
  - `POST /api/scenes/{scene_id}/public-snippet-links`;
  - `DELETE /api/scene-public-snippet-links/{link_id}`;
  - `POST /api/scenes/{scene_id}/publish-staged-display`.
- Scene Context workspace widget:
  - current selected/active scene;
  - private scene activation;
  - active map summary;
  - linked notes;
  - linked entities;
  - linked public snippets;
  - active encounter selection;
  - staged public display mode;
  - explicit publish action.
- Notes widget selected-scene focus/filter.
- Combat widget auto-selects the scene context active encounter.
- `publish-staged-display` uses existing map, initiative, snippet, scene-title, intermission, and blackout display behavior.
- `activate-scene`, context patch, link, and unlink operations do not mutate `player_display_runtime`.
- Playwright screenshots:
  - `gm-scene-context-configured.png`;
  - `gm-scene-context-after-activation.png`;
  - `player-scene-context-before-publish.png`;
  - `player-scene-context-after-publish.png`.

Acceptance checkpoint:

```text
configure scene context
  -> link active map, note/snippet, entity, and encounter
  -> activate scene privately
  -> GM cockpit focuses scene context
  -> /player remains unchanged
  -> publish staged display explicitly
  -> /player updates through existing public display sanitizer
  -> private notes/entities/combat fields remain private
```

Explicit deferrals:
- no automatic public reveal on scene activation;
- no scene-scoped widget layouts;
- no campaign timeline/calendar automation;
- no soundboard/music preset loading;
- no remote multiplayer scene sync.

## Slice 13: Backup, Export, Restore, And Public Demo Hardening

Status: complete.

Goal: make the local-first tool safer to carry between machines and demo without fragile manual steps, while keeping the committed demo public-safe and English-first.

Build:
- storage settings:
  - `MYROLL_EXPORT_DIR`, default `data/exports`;
  - `MYROLL_SEED_MODE=dev|none`, default `dev`;
  - optional `MYROLL_DEMO_NAME_MAP_PATH`.
- storage APIs:
  - `GET /api/storage/status`;
  - `POST /api/storage/backup`;
  - `POST /api/storage/export`;
  - `GET /api/storage/exports/{archive_name}`.
- export archive:
  - atomic `myroll.<YYYYMMDDTHHMMSSZ>.export.tar.gz`;
  - `myroll-export.json` manifest;
  - SQLite snapshot under `db/myroll.sqlite3`;
  - managed `assets/` tree excluding `.tmp`;
  - checksums and byte sizes.
- offline restore:
  - `scripts/restore_export.sh <archive> <target-data-dir> [--force]`;
  - validates tar paths against traversal;
  - refuses non-empty target dirs unless forced;
  - restores DB and assets into a new data dir.
- demo scripts:
  - `scripts/reset_demo.sh`;
  - `scripts/start_demo.sh`;
  - isolated default demo data dir `data/demo`;
  - normal Ship Ambush dev seed is disabled during demo reset.
- English public-safe demo profile:
  - campaign `Chronicle of the Lantern Vale`;
  - scenes: `Lake of the Last Horn`, `The Blue Forest Road`, `The Crooked Loom House`, `Workshop of Stolen Time`;
  - deterministic entities, party tracker, custom fields, notes/snippets, map/fog/tokens, combat encounter, and scene context.
- generated demo asset pack:
  - `demo/assets/generated/lantern_vale_chronicle/`;
  - 12 optimized original dark-fairytale images;
  - `manifest.json` records stable keys, roles, prompts, default visibility, and intended usage.
- local demo override mapping:
  - committed template `demo/local/name-map.example.json`;
  - ignored local override `demo/local/name-map.private.json`;
  - ignored optional private manifests `demo/local/*.private.*`;
  - public demo uses original English names when no private map is present.
- GM `Storage / Demo` workspace widget:
  - profile hint;
  - shortened DB/asset paths;
  - DB and asset sizes;
  - seed/schema status;
  - local-demo-override active indicator;
  - latest backup/export;
  - create backup/export;
  - download latest export.

Delivered:
- Implemented storage/export backend service with atomic archive creation and safe download endpoint.
- Implemented offline restore CLI/script with path traversal validation.
- Added demo reset/start scripts that operate on an isolated data dir and run with `MYROLL_SEED_MODE=none`.
- Added original public deterministic demo seed with optional ignored local display-name overrides.
- Added generated demo asset pack and safe manifest under `demo/assets/generated/lantern_vale_chronicle/`.
- Added `.gitignore` protection for local demo override maps and optional private local manifests.
- Added `Storage / Demo` workspace widget and frontend storage API client.
- Added backend and frontend tests for storage, export, restore, demo seed, local demo override behavior, and widget actions.

Acceptance checkpoint:

```text
reset demo profile
  -> load original public campaign
  -> inspect Storage / Demo widget
  -> create backup/export
  -> restore archive into clean data dir
  -> start from restored data dir
  -> campaign, assets, maps, fog, tokens, notes, snippets, party, combat, scene context, and widget layout load
```

Explicit deferrals:
- no cloud sync;
- no account system;
- no encrypted archive/vault format;
- no in-place live restore;
- no UI restore button;
- no Git LFS unless the demo asset pack becomes too large;
- no LLM work in Slice 13.

## Post-Slice 13 UX Surface Rework: Multi-Surface GM Shell

Goal: make the laptop GM experience usable after the cockpit grew beyond what one floating widget canvas can comfortably hold.

Delivered:
- Changed `/gm` from the all-widget floating canvas into a docked GM Overview surface.
- Added focused GM routes:
  - `/gm/map` for the full Map Workbench;
  - `/gm/library` for assets, notes, and public snippets;
  - `/gm/actors` for party/entities;
  - `/gm/combat` for encounters and initiative;
  - `/gm/scene` for scene orchestration;
  - `/gm/floating` for the preserved advanced floating workspace.
- Kept the persistent `workspace_widgets` canvas as an advanced/power-user surface instead of deleting it.
- Added top-level GM navigation and laptop-oriented panel sizing/scrolling.
- Updated Playwright coverage so old floating workflows still run through `/gm/floating`, while `/gm` and focused surfaces get visual smoke coverage.

Acceptance checkpoint:

```text
open /gm on a laptop viewport
  -> overview columns fit without horizontal overflow
  -> open focused surfaces from top nav
  -> map workbench gets a full working surface
  -> old floating canvas remains available at /gm/floating
  -> full product QA journey still passes
```

Explicit deferrals:
- no scene-scoped workspace layouts;
- no split-pane docking customization;
- no saved per-surface panel presets;
- no pan/zoom/minimap in the GM shell itself.

## Slice 14: LLM Session Memory And GM Generation Harness

Goal: make a large language model a first-class GM copilot without turning it into the source of truth.

Build:
- OpenAI-compatible provider profiles:
  - name;
  - base URL;
  - model ID;
  - API key source;
  - streaming support flag;
  - JSON-mode support flag;
  - tool-call support flag;
  - image/diffusion harness support flag for later workflows;
  - timeout and retry settings.
- API keys are not stored as raw campaign data in SQLite in the first implementation:
  - prefer environment variables such as `MYROLL_LLM_API_KEY`;
  - allow provider profiles to reference key names/sources;
  - never expose key values through `/health`, `/api/meta`, frontend responses, logs, or Playwright screenshots.
- Provider test APIs:
  - list/test models where supported;
  - run a minimal non-streaming health prompt;
  - return safe error envelopes.
- GM Assistant workspace widget:
  - provider/model status;
  - context picker;
  - prompt template picker;
  - request preview showing exactly what campaign/session/scene data will be sent;
  - run button;
  - response viewer;
  - run history;
  - draft artifact actions.
- Append-only session transcript:
  - DM prompts;
  - assistant responses;
  - LLM runs;
  - accepted draft artifacts;
  - dice/combat events when those domains exist;
  - scene changes;
  - player-display publish events;
  - tool/result references where applicable.
- Structured session memory:
  - campaign/session-scoped record in SQLite as source of truth;
  - optional markdown rendering for human inspection;
  - updated through explicit/manual extraction first, and later through safe-point background updates.
- Default D&D memory sections:
  - session title;
  - current scene;
  - immediate DM needs;
  - party state;
  - NPCs;
  - locations;
  - plot threads and clues;
  - player decisions;
  - combat/mechanics state;
  - tone and table preferences;
  - generated content;
  - short chronological worklog.
- Context compaction pipeline inspired by large coding harness session-memory behavior:
  - compact boundary records;
  - compact summary messages;
  - preserved verbatim tail;
  - post-compact structured attachments;
  - exact transcript reference for details;
  - fallback summarizer if structured memory is missing, stale, empty, or too large.
- Configurable thresholds:
  - initial memory token threshold;
  - memory update token delta;
  - significant-event threshold;
  - compact threshold;
  - blocking threshold;
  - preserved tail turn/token budget.
- Safe-point rules:
  - do not extract or compact during unresolved tool calls;
  - do not split dice roll request/result/adjudication;
  - do not split a combat round;
  - do not split a rules lookup from its answer;
  - preserve active scene start if it is recent.
- Prompt template registry for GM tasks:
  - summarize current session;
  - summarize public-known facts only;
  - summarize GM-only hidden state;
  - extract unresolved hooks;
  - draft next-scene complications;
  - generate NPC/entity ideas;
  - generate location/item/faction/vehicle ideas;
  - draft player-safe public snippet;
  - draft combat encounter twists without rules automation;
  - draft token/image/map/handout prompts for a diffusion/image harness;
  - draft character sheets as entity/custom-field drafts;
  - check selected notes for contradictions.
- Draft artifacts:
  - private note draft;
  - public snippet draft;
  - entity draft;
  - custom field value draft;
  - token draft;
  - map/handout/image prompt draft;
  - character sheet draft;
  - session recap draft.
- Draft apply actions are explicit:
  - save as private note;
  - create public snippet;
  - create entity;
  - update selected entity fields;
  - create token draft from entity;
  - create image prompt record;
  - import generated image as asset only after explicit GM action.
- Diffusion/image harness integration is prompt-first in this slice:
  - LLM can generate prompts and negative prompts;
  - prompt records can be saved with campaign/scene/entity links;
  - calling an external diffusion endpoint is allowed only if configured and explicitly invoked;
  - generated images enter Myroll through the existing asset validation/import pipeline;
  - generated assets default private until the GM marks them public-displayable.
- LLM run history:
  - provider profile ID;
  - model ID;
  - prompt template ID;
  - selected context snapshot;
  - request metadata;
  - response text/JSON;
  - token usage if available;
  - created draft artifacts;
  - applied/not-applied status;
  - error state.
- Observability:
  - memory extraction started/completed/failed;
  - why extraction/compact was skipped;
  - token estimates before/after compact;
  - number of messages summarized and preserved;
  - compact trigger;
  - fallback reason;
  - whether post-compact context would immediately retrigger compaction.

Core guardrails:
- LLM is never the durable source of truth.
- LLM never mutates campaign state directly.
- LLM output is a draft until the GM explicitly applies it.
- `/player` never talks to LLM endpoints and never receives private LLM context.
- Browser transport remains notify-only and carries no LLM prompt, response, or generated payload.
- Context sent to remote/local models is explicit, previewable, and campaign-scoped.
- Private notes, GM secrets, hidden tokens, private entities, and unrevealed clues are sent only when the selected prompt/context mode explicitly includes GM-private context.
- Public-safe workflows use public-known facts and public snippets/party/map display state only.
- Generated public content is not published automatically.
- Diffusion/image outputs must pass through Slice 5 asset validation before becoming assets.
- Model/tool errors use the standard API error envelope and do not leak API keys or absolute local paths.

Acceptance checkpoint:

```text
configure OpenAI-compatible provider
  -> test provider/model connection
  -> select active campaign/scene context
  -> preview exact context package
  -> ask for current-session summary
  -> save response as private note draft
  -> create a player-safe snippet draft from selected output
  -> publish only after explicit GM action
  -> force memory extraction
  -> inspect structured session memory
  -> run compact simulation
  -> compact result preserves current scene, unresolved hooks, NPC state, combat/mechanics state, and recent verbatim tail
  -> generate NPC/character sheet/image prompt drafts
  -> apply one entity draft and one image prompt draft explicitly
  -> refresh browser
  -> provider config, memory, run history, and applied drafts persist from SQLite
```

Explicit deferrals:
- no autonomous agent loop;
- no automatic campaign mutation;
- no automatic player-display publish;
- no unsandboxed tool execution by the model;
- no generic web browsing/search in the first LLM slice;
- no model-managed rules automation;
- no vector database unless a later scale problem proves it is needed;
- no live multi-turn chat history as a separate product surface;
- no remote player relay, auth, WebSocket/SSE, or cloud sync;
- no storing raw API keys in exported demo data.

## Later Candidates

These are intentionally not ordered before the core map/display/session loop is reliable:
- soundboard and tab-sharing audio behavior;
- command palette and hotkeys;
- calendar/time/weather utilities;
- curated NPC library and reusable generator template packs;
- shop/travel/session generators;
- deeper diffusion/image harness automation after Slice 14 proves prompt/draft flow;
- desktop packaging with Electron or Tauri;
- remote player clients, relay, WebRTC, TURN, auth, or LAN exposure.
