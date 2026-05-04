# Myroll Roadmap

Date: 2026-05-02

## Current Direction

Myroll is now planned as a local-first desktop-ish web app:

```text
SQLite = durable source of truth
FastAPI = local control plane
Filesystem = asset blob storage
Browser = UI/runtime/cache
```

The original browser-only IndexedDB model is no longer the durable persistence foundation for campaign data.

## Generated Battle Map Asset Pack V1

Status: produced externally on 2026-05-01; Myroll application integration is deferred. This pack is the foundational core fantasy layer, not the whole intended map library.

Delivered:
- 10 fantasy battle-map categories with 40 accepted images per category, 400 maps total.
- PNG source files plus WebP delivery copies.
- Pack-level `pack.json`, category-local `category.json`, per-category contact sheets, a pack sample review sheet, and a manual review HTML index.
- Category-local grid contracts:
  - `interior.house_floor`: 16x12, 80 px/cell;
  - `interior.small_chamber`: 10x10, 128 px/cell;
  - `dungeon.stone_complex`: 24x18, 64 px/cell;
  - `dungeon.cave_complex`: 24x18, 64 px/cell;
  - `outdoor.forest_road`: 24x18, 64 px/cell;
  - `outdoor.river_bridge`: 24x18, 64 px/cell;
  - `outdoor.swamp_marsh`: 24x18, 64 px/cell;
  - `settlement.street_square`: 24x18, 64 px/cell;
  - `ruins.temple_shrine`: 24x18, 64 px/cell;
  - `large.arena_lair`: 32x24, 48 px/cell.

Integration rule:
- generated map scale is a category contract, not a model guess at runtime;
- each category directory owns its grid metadata through `category.json`;
- future Myroll import should validate image dimensions against the category grid contract and create normal `map_image` assets plus square grid settings through the existing Slice 5/Slice 6 asset and map pipeline;
- generated images remain gridless, and Myroll overlays the tactical grid live in the renderer.

Explicit deferrals:
- no automatic import into Myroll in this asset-generation pass;
- no Myroll UI category browser changes yet;
- no committed large binary pack in the app repository;
- no fully automated visual QA over all 400 images.

## Generated Battle Map Asset Pack V2: Diverse Spacious Set

Status: produced externally on 2026-05-01; Myroll application integration is deferred. This pack extends V1 with stronger material/color/category variety and wider playable movement space.

Delivered:
- 10 diverse fantasy battle-map categories with 20 accepted images per category, 200 maps total.
- PNG source files plus WebP delivery copies.
- Pack-level `pack.json`, category-local `category.json`, per-category contact sheets, and a pack overview contact sheet.
- Agent visual spot-check of every category contact sheet; manual product scrub is still expected for mixed categories.

Output root:

```text
myroll_battle_maps_v2_diverse_spacious/
  city.rooftops_fog/
  hazard.lava_bridges/
  coast.shipwreck_beach/
  underground.toxic_sewer_canals/
  cavern.crystal_blackrock/
  interior.tavern_night/
  ruins.clean_arena/
  nature.waterfall_cliff_crossing/
  arcane.prismatic_laboratory/
  forest.fey_clearing/
```

Generation notes:
- V1 remains useful as a `core beige fantasy survival pack`.
- V2 should optimize for category/material variety first, not just more fantasy rooms.
- Prompt-only category forcing works reasonably for lava, beach, toxic sewer, blackrock crystal cavern, waterfall, and prismatic laboratory experiments.
- V2 must also optimize for playable movement space. A 2026-05-01 spaciousness experiment generated 20 samples at `/Volumes/External/projects/comfyui/outputs/battlemap_spaciousness_experiment_20260501_01`.
- Prompt-only spaciousness language is not enough for bulk generation: the model still tends to fill maps with small islands, rooms, props, and cover.
- Production categories should carry a spatial composition contract in addition to grid metadata: target at least 60% walkable/playable area, one clearly readable central movement zone or broad connected lanes, 3-5 square wide routes, sparse cover islands, and obstacles biased toward edges.
- Layout-guided img2img with simple open-area blockouts is currently the best direction for spacious maps. It helped `coast.shipwreck_beach`, `cavern.crystal_blackrock`, `ruins.clean_arena`, `nature.waterfall_cliff_crossing`, and `forest.fey_clearing` preserve playable space.
- A follow-up refinement probe at `/Volumes/External/projects/comfyui/outputs/battlemap_spaciousness_refine_20260501_01` showed that low denoise (`0.80`) often produces broken blockout-like images, while flexible layout-guided denoise around `0.90` gives an acceptable ratio for bulk generation plus visual/manual reject cleanup.
- Bulk V2 generation intentionally accepts a usable ratio rather than trying to force a 100% generation success rate; the product workflow should support later manual rejects.
- The 200-image V2 pass is strongest for `underground.toxic_sewer_canals`, `cavern.crystal_blackrock`, `interior.tavern_night`, `ruins.clean_arena`, and `forest.fey_clearing`.
- `city.rooftops_fog` and `arcane.prismatic_laboratory` are mixed but usable; expect more manual rejects or a future tighter workflow before expanding them to 40+ images.
- `nature.waterfall_cliff_crossing` produced highly playable green river/crossing maps, but reads less waterfall-heavy than the category name suggests.
- Geometry-heavy categories need layout-guided generation or stronger structural control:
  - `ruins.clean_arena` benefits from layout-guided img2img;
  - `city.rooftops_fog` benefits from layout-guided img2img, but still needs dark-city prompt tightening;
  - `water.ship_open_sea` is not reliable with the current SDXL battlemap workflow: low denoise preserves the ship silhouette but stays too flat, while higher denoise turns the ship into an island/platform.
- Do not bulk-generate `water.ship_open_sea` until a ship-specific workflow is available, such as a stronger ship layout mask, a ship/deck LoRA, or a different model better trained on top-down vehicles.

## Generated Battle Map Asset Pack V3: Weird Fantasy Set

Status: produced externally on 2026-05-01; Myroll application integration is deferred. This pack extends V1/V2 with darker, celestial, planar, and high-fantasy material extremes.

Delivered:
- 5 weird fantasy battle-map categories with 20 accepted images per category, 100 maps total.
- PNG source files plus WebP delivery copies.
- Pack-level `pack.json`, category-local `category.json`, per-category contact sheets, and a pack overview contact sheet.
- Agent visual spot-check of every category contact sheet; manual product scrub is still expected for mixed categories.

Output root:

```text
myroll_battle_maps_v3_weird_fantasy/
  abyss.bone_cathedral/
  celestial.starforge_sanctum/
  void.astral_orrery/
  elemental.storm_glass_citadel/
  fey.giant_flower_court/
```

Generation notes:
- V3 intentionally covers the more extreme fantasy range that V1 and V2 do not: necrotic/dark, celestial, astral, elemental, and fey spaces.
- `elemental.storm_glass_citadel` and `fey.giant_flower_court` were fixed forward after weak canary output; the final category prompts and layout masks avoid the earlier water/island and flat flower-icon failures.
- The strongest categories are `celestial.starforge_sanctum` and `elemental.storm_glass_citadel`.
- `abyss.bone_cathedral`, `void.astral_orrery`, and `fey.giant_flower_court` are usable but mixed; expect some manual rejects before product import.
- The same import rule from V1/V2 applies: generated maps remain external artifacts for now, and future Myroll import should use category metadata plus the existing map/image asset pipeline.

## Curated Battle Map Production Pack V1

Status: ready as an external integration input as of 2026-05-02. Myroll application import/UI work is still deferred.

Production root:

```text
/Volumes/External/projects/comfyui/asset_packs/myroll_battle_maps_production_v1
```

Delivered:
- curated production-shaped tree under `assets/battle-maps/fantasy/<collection>/<group>/<category>/`;
- 608 accepted gridless WebP battle maps from 700 generated source images;
- 92 rejected source images logged in `curation/rejections.json`;
- stable descriptive filenames derived from category plus generated source names;
- pack-level `manifest.json` and `taxonomy.json`;
- category-local `category.json` files with the authoritative square grid contract;
- accepted and rejected contact sheets for manual review;
- handoff document at `HANDOFF.md` for the next integration chat/slice.

Current collections:
- `core`: 365 accepted maps from the original generic fantasy survival layer;
- `diverse`: 163 accepted maps across lava, coast, sewer, crystal cavern, tavern, arena, waterfall, rooftop, fey, and arcane categories;
- `weird`: 80 accepted maps across abyssal, celestial, elemental, fey, and astral categories.

Integration rule:
- raw generated packs remain preserved and are not the app-facing artifact;
- Myroll should register/import only the curated production `manifest.json`;
- the curated static pack should ship with the app so end users do not have to import it manually after install;
- for the first integration slice, committing the full production pack as a versioned immutable bundled asset pack is acceptable to avoid adding separate artifact-storage infrastructure;
- revisit Git LFS, release assets, or another artifact store only if repository size or asset update frequency becomes a real problem;
- every accepted `asset.file` must pass the existing backend image validation and be copied into managed `data/assets/` storage;
- image scale comes from `asset.grid` and/or the category-local `category.json`, never from prompt text or visual guessing;
- the renderer continues to draw the tactical grid live over gridless images.

Importer slice starting point:
- implement a local development import command or backend-only admin endpoint first;
- validate manifest schema, category paths, asset paths, checksums, image dimensions, and grid dimensions;
- create normal `map_image` asset records, then campaign map records with square grid settings;
- preserve `categoryKey`, `collection`, `categoryLabel`, source provenance, and curation status as searchable metadata;
- add a GM asset browser/category UI only after importer validation and storage behavior are stable.

Roadmap placement:
- this work is large enough to be its own product slice, not a side task inside the LLM slice;
- it should probably run before or instead of the currently queued LLM Slice 14 if imported maps/tokens are the next table-facing priority;
- final slice numbering should be decided during implementation planning.

## Quick NPC Static Seed Catalog Spike

Status: content spike delivered on 2026-05-02. Application UI/API integration is still deferred.

Delivered:
- bundled static JSON array at `bundled/quick_npc_seeds/quick_npc_seeds.json`;
- 300 prewritten minor NPC seeds with D&D race/species labels and male/female gender metadata, but no rules or stat mechanics;
- 25 seeds each for guard/soldier, commoner/villager, merchant/trader, artisan/craftsperson, noble/official/bureaucrat, criminal/spy/smuggler, scholar/scribe/priest, traveler/refugee/pilgrim, wilderness local/guide/hunter, sailor/porter/caravan worker, cultist/zealot/secret believer, and weird/magical stranger;
- compact fields for race, gender, race/gender-aligned name, role, origin, appearance, voice, mannerism, initial attitude, tiny backstory, reusable hook/secret, portrait/search tags, and use tags.

Integration rule:
- Quick NPC draw/filter/search should load shipped static content locally with no runtime LLM call;
- "Use as NPC" should copy the selected seed into an editable GM-owned NPC record or prefilled NPC form;
- the global bundled seed catalog is app content, not mutable campaign state;
- portrait tags are search/linking hints only, and no portrait should be required.
- generated portrait packs are visual enrichment over the seed catalog, mapped by `sourceSeed.id`;
- the app must still work when only the JSON seed catalog is present.

Explicit deferrals:
- no Quick NPC browser surface yet;
- no backend seed-catalog endpoint yet;
- no NPC-specific schema beyond the existing entity/custom-field foundation yet;
- no bundled portrait pack dependency.

## Quick NPC Seed Catalog Integration Slice

Goal: make Quick NPC a first-class live-session primitive for drawing, filtering, using, and promoting ordinary NPCs without waiting for a model call.

Product behavior:
- the GM can open a compact Quick NPC picker from `/gm`, scene tools, or a command;
- the GM can draw a random seed, filter by broad type/race/gender/use tags, or search by name/role/tags/text;
- the GM can reroll/refresh quickly during play;
- the GM can copy/use a seed in notes without creating campaign canon;
- the GM can pin a seed to the current session as temporary working material;
- the GM can promote a selected seed into an editable campaign NPC/entity;
- promoted NPCs become normal private GM-owned records and can later be linked to scenes, notes, tokens, portraits, or public snippets.

Build:
- bundled catalog loader for `bundled/quick_npc_seeds/quick_npc_seeds.json`;
- schema validation for the existing 300-seed top-level JSON array;
- service/query layer for list, filter, search, deterministic random draw, and seed lookup by ID;
- local API endpoints for bundled quick NPC browse/draw and campaign promotion;
- campaign promotion service that copies seed fields into `Entity(kind = "npc")` plus private custom fields or private notes;
- optional scene-linking when promotion happens from an active scene;
- GM Quick NPC card/picker UI with filters, reroll, copy, pin, and promote actions;
- tests for catalog schema, distribution, deterministic draw, search/filter behavior, and promotion copy semantics.

Portrait integration rules:
- portrait generation is an offline/bootstrap pipeline for visual enrichment, not the product primitive;
- generated files and metadata map back to seeds through `sourceSeed.id`;
- the expected portrait pack shape is multiple variants per seed, initially 3 variants per seed for the 300-seed v1 catalog;
- generated portraits must be imported through the existing image asset validation path before linking to NPCs;
- curation can be manual first and VLM-assisted later;
- curation status should distinguish accepted, rejected, artifact, and metadata/race/gender mismatch cases;
- Quick NPC cards must render acceptably with text only when no portrait is available.

Current external generation note:
- a local ComfyUI run is producing 900 candidate portraits for v1 outside this repository;
- current output collection path is `/Volumes/External/projects/comfyui/asset_packs/myroll_quick_npc_portraits_v1/arthemy3_dndportrait_solo_gender_trimmed_v2_full_3v`;
- filenames include type, race, gender, role, name, seed ID, and variant;
- per-image metadata JSON includes the full `sourceSeed`;
- the final portrait `manifest.json` is expected after the run completes;
- do not make Myroll depend on this output path or on the portrait manifest for the base Quick NPC feature.

Core guardrails:
- no runtime LLM call for drawing a Quick NPC;
- no mutation of the bundled seed catalog during campaign play;
- no portrait requirement;
- no raw generated portrait serving from the external ComfyUI directory;
- no public/player display mutation from drawing or promoting a Quick NPC;
- no public visibility for promoted NPC secrets, notes, backstory, or hook fields by default.

Acceptance checkpoint:

```text
start backend with bundled quick_npc_seeds.json
  -> catalog schema validation passes
  -> browse returns 300 seeds
  -> filter type=guard_soldier returns 25 seeds
  -> search by role/tag finds matching seeds
  -> draw with a fixed random seed is deterministic
  -> reroll can exclude currently visible seed IDs
  -> GM opens Quick NPC picker from a live session surface
  -> GM draws a seed and sees a usable text-only NPC card immediately
  -> GM copies the seed summary into a note without creating an entity
  -> GM promotes the seed into a private campaign NPC
  -> promoted NPC contains copied editable fields and sourceSeedId traceability
  -> editing the promoted NPC does not mutate the bundled seed
  -> /player receives no new data until an explicit separate publish action
```

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

## Proposed Next Slice: Asset Import, Battle Map Pack Import, And Grid Calibration

Status: proposed; implementation not started.

Goal: make the new battle-map library and future token/monster asset packs usable inside Myroll without weakening the existing asset safety model.

Status update, 2026-05-02:
- first bundled battle-map integration slice implemented;
- production pack committed at `bundled/asset_packs/myroll_battle_maps_production_v1/`;
- bundled registry validates manifest, taxonomy, category metadata, relative paths, checksums, WebP dimensions, and grid contracts;
- catalog/add APIs added: `GET /api/bundled-asset-packs`, `GET /api/bundled-asset-packs/{pack_id}/maps`, `POST /api/campaigns/{campaign_id}/bundled-maps`;
- storage decision for v1 is copy-on-add into managed `data/assets/`, with deterministic campaign asset/map IDs for idempotent adds;
- user-facing batch upload, `token_image`, bundled map browser, and grid size/nudge controls are included in this slice.

Build:
- bundled static asset-pack distribution:
  - ship the curated production pack with packaged builds/installers;
  - allow the first production pack to live in git as an immutable bundled asset version;
  - keep a tiny fixture pack for importer tests even if the full pack is committed;
  - keep an escape hatch to move packs to Git LFS/release artifacts later if size becomes a problem;
  - allow development builds to discover packs from a configured local bundle directory;
  - register bundled packs automatically on startup so installed users see them without manual import.
- backend-first curated battle-map pack importer:
  - accepts a configured local production `manifest.json`;
  - validates manifest schema, relative paths, category-local `category.json`, SHA-256 checksums, decoded image dimensions, and grid dimensions;
  - rejects absolute paths, path traversal, unsupported formats, checksum mismatches, and images whose decoded dimensions do not match the grid contract;
  - registers accepted WebP files as read-only catalog entries;
  - creates campaign `map_image` assets/references and campaign map records with square grid settings from `asset.grid` when a GM adds a bundled map to a campaign;
  - stores pack/category/provenance/curation metadata and bundled pack version for filtering and regeneration traceability.
- user-facing asset import improvements:
  - multi-file image upload for user maps, handouts, portraits, and token art;
  - kind/visibility/tag defaults per batch;
  - no public HTTP `source_path` import;
  - future directory-picker support only if it preserves explicit user consent and validates every file through the same backend image path.
- GM map-workbench grid calibration:
  - keep the source map gridless;
  - expose fast controls to grow/shrink grid cell size;
  - expose fast four-direction nudge controls for live grid alignment;
  - persist calibration as `grid_size_px`, `grid_offset_x`, and `grid_offset_y`, not as destructive image edits;
  - support fine/coarse nudges and numeric fallback controls;
  - keep player grid visibility separate from GM calibration.
- GM asset/category browser after the importer is stable:
  - browse by collection/group/category using `taxonomy.json` or derived manifest data;
  - search by title/tags/category;
  - create or attach imported maps to scenes;
  - support token portrait selection from imported monster/NPC token assets.

Acceptance checkpoint:

```text
run curated pack import
  -> importer validates manifest/category/checksum/dimensions
  -> bundled maps appear in the GM category browser without manual post-install import
  -> adding a bundled map to a campaign creates a campaign map with live square grid calibration
  -> GM can browse imported categories
  -> GM can assign a map to a scene, resize grid cells, and nudge the grid in four directions
  -> /player shows the gridless image plus the live grid only when player grid is enabled
  -> public blob endpoints still serve only active player-display-referenced assets
```

Explicit deferrals:
- no external artifact-storage setup required in the first integration slice;
- no read-only bundled blob reference path in this slice; copy-on-add is the chosen v1 behavior;
- no marketplace/plugin asset distribution;
- no automatic visual QA over every imported image in the app;
- no dynamic lighting, walls, doors, token vision, measuring, or snap-to-grid in this slice;
- no generic server-path import exposed through the browser API;
- no automatic token/stat sync from monster art.

## Slice 14: LLM Canonization, Recall, And GM Generation Harness

Goal: make a large language model a first-class GM creative workbench without turning it into the source of truth.

Status as of 2026-05-04:
- shipped first Scribe spine: compact `/gm` live capture, transcript correction, provider profile/probe, reviewed context preview, backend-owned recap run, editable recap save, targetless Memory Inbox accept, manual aliases, basic recall, and default export redaction for LLM prompt/response payloads;
- shipped branch proposal/planning marker slice: campaign/session/scene branch context preview, structured proposal sets/options, degraded normalization warnings, proposal card actions, one-marker-per-source-option adoption, active planning marker context eligibility, and `/gm` proposal cockpit inspection;
- shipped player-safe recap/snippet leak-warning gate: public-safe curation, public-safe context preview, structured player-safe draft run, deterministic warning scan, exact-content ack for risky drafts, LLM snippet provenance, and player-display publication tracking;
- shipped proposal canonization bridge: `session.build_recap` can link a memory candidate to one active planning marker when later played evidence confirms it, and `Accept into Memory` atomically creates canon memory while marking the marker/source option `canonized`;
- shipped corpus-backed recall/context packages: selected campaign sources compile into derived Scribe corpus cards, SQLite FTS5 recall runs under admissibility policy, and Scribe LLM context previews/provider prompts use the same corpus-backed evidence bundle;
- shipped real-provider Scribe journey hardening: opt-in Playwright runners now exercise the local/LAN model through live capture, branch proposals, planning-marker adoption, played-event recap, memory accept, recall, and `/player` boundary checks. The recap prompt now renders transcript chronology and canonical evidence-ref IDs explicitly, and direct-evidence memory candidates reject speculative proposal wording as proof;
- planned next: broader Scribe hardening, deferred entity/object patch workflows, and a separate Evidence Board/UX spike for the visual card-based inspection surface;
- deferred: vectors, streaming, tool calls, audio capture/transcription, and autonomous entity mutation.

Detailed build specification:
- `docs/04-llm-product-and-implementation.md` is the implementation-facing spec for this area.
- Treat this roadmap section as the umbrella and guardrail summary; the detailed PRE-LLM through LLM-5 slice breakdown lives in the dedicated LLM document.

Product decision:
- Myroll's LLM value is not "AI writes the campaign"; it is campaign-aware GM assistance for NPC roleplay, settlements, politics/factions, quest boards, character-building hooks, creative options, session summaries, and continuity checks.
- A compact timestamped Live DM Notes capture surface is part of the golden path for useful recaps: it lets the GM type, paste, or dictate short private table events during play.
- Live play is capture-only in v1; after the session, the GM clicks Build Session Recap to assemble live notes, linked notes, NPC/entity changes, combat/session events, planning markers, and approved memory into a reviewed recap/canonization workflow.
- First value loop is Scribe-first, not branch-proposal-first: capture what happened, build a reviewed recap, accept memory, recall it later.
- Branch proposals are primarily prep/review tools after the recap/memory loop works.
- V1 does not record audio, transcribe audio, summarize live during play, require vectors, require streaming, require tool calls, or auto-update entities from transcripts.
- AI output is not campaign truth until the GM commits it.
- Campaign objects such as NPCs, settlements, factions, quests, and character hooks are manual GM-owned Myroll primitives first; the model may prefill fields, suggest updates, or produce drafts, but it does not own or silently create those objects.
- Options are ephemeral. Selections become state. Only committed state enters future model context by default.
- When a prompt asks for options, variants, ideas, complications, hooks, or alternatives, the harness should request structured output with stable option IDs, summaries, and proposed campaign deltas.
- If the GM adopts option 2 from a generated set of options, future context carries only the active planning marker text, not the selected option body and not the entire brainstorm that also contains rejected options.
- Unselected options remain available in run/proposal history for audit, follow-up, or explicit "what did we reject?" recall, but they must not compete with canon in normal generation context.

Dedicated implementation areas:
- GM task catalog:
  - first-class tasks such as NPC roleplay, settlement generation, faction/political moves, quest boards, character arc hooks, next-scene complications, session summaries, player-safe recaps, contradiction checks, and exact recall;
  - for each task, document user job, trigger/UI entry point, required inputs, default context package, output schema, apply/canonization actions, visibility rules, and acceptance behavior.
- Manual campaign object primitives:
  - NPCs, settlements, factions, quest board entries, character hooks, and similar campaign objects must be usable, searchable, editable, and recallable without calling a model;
  - NPC records should reserve an optional portrait/image field for future shipped portrait packs and user-imported portraits;
  - NPC portraits are never required for continuity; voice, relationships, obligations, secrets, and source evidence remain the durable core;
  - portrait choices should support filtering bundled/shipped assets as well as selecting GM-imported assets;
  - any imported or generated portrait must enter Myroll through the existing asset validation/import pipeline before it can be linked to an NPC;
  - LLM tasks may prefill a new manual object form, suggest field updates, summarize evidence into fields, or draft related roleplay/options;
  - object creation/update remains a GM action in the Myroll UI, even when fields were suggested by the model;
  - if a first-class object type does not exist yet, the roadmap should add it before treating the related LLM workflow as more than a draft generator.
- Quick NPC layer:
  - live sessions need an instant "give me a usable minor NPC now" flow that does not wait for a model call;
  - ship Myroll with a curated static Quick NPC library containing several hundred prewritten NPC seeds;
  - Quick NPC seeds should include at minimum name, role/archetype, short origin, visible trait, voice/mannerism cue, immediate attitude, tiny backstory, and one reusable hook or secret;
  - seeds should be filterable by broad type such as guard/soldier, commoner, merchant, artisan, noble/official, criminal/spy, scholar/priest, traveler/refugee, wilderness/local guide, sailor/porter, cultist/zealot, and weird/magical stranger;
  - the UI should support a fast draw/search/filter action from the GM surface and a "Use as NPC" action that creates or prefills a GM-owned NPC record;
  - drawing a Quick NPC is deterministic local content selection, not LLM generation;
  - once used, the selected seed should be copied into the campaign as editable NPC state so later continuity does not depend on the global seed catalog;
  - Quick NPCs may optionally link a portrait from bundled/imported assets, but they must work without a portrait.
- Memory source taxonomy:
  - canon campaign facts;
  - approved session memory;
  - append-only transcript;
  - scene/entity/note state;
  - proposal history;
  - selected/canonized options;
  - rejected options;
  - saved-for-later ideas;
  - player-safe public facts;
  - priority order for retrieval and context packaging.
- Context package strategy:
  - default context sources per task;
  - explicit GM-private modes;
  - public-safe modes;
  - token budget order and trimming rules;
  - where exact recall evidence sits relative to structured memory and recent transcript tail;
  - when proposal/rejection history is allowed or forbidden.
- Memory inbox contract:
  - candidate types: new fact, changed NPC/faction relationship, unresolved hook, selected/canonized option, player-safe recap item, contradiction warning;
  - GM review actions: approve, edit, reject, save for later, link to entity/scene/session;
  - no candidate enters canon without explicit GM action.
- Exact recall contract:
  - SQLite FTS-backed recall first, vector search deferred until scale/quality requires it;
  - branch/status-aware retrieval;
  - trigger detection for explicit recall, entity gaps, continuation gaps, and contradiction checks;
  - bounded cited evidence snippets;
  - timeout/fallback behavior;
  - rejected proposal suppression unless explicitly requested.
- Competitive anti-patterns to avoid:
  - no SillyTavern-level power-user prompt cockpit in the first version;
  - no "write the full campaign" magic button;
  - no autonomous AI DM loop;
  - no model-managed rules or combat automation;
  - no raw brainstorm as durable continuity;
  - no GM secrets sent to a model without explicit context mode and preview.

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
- Provider conformance levels:
  - text-only;
  - JSON best effort;
  - JSON validated;
  - tool-capable later;
  - task templates declare the minimum conformance they need.
- API keys are not stored as raw campaign data in SQLite in the first implementation:
  - prefer environment variables such as `MYROLL_LLM_API_KEY`;
  - allow provider profiles to reference key names/sources;
  - never expose key values through `/health`, `/api/meta`, frontend responses, logs, or Playwright screenshots.
- Provider test APIs:
  - list/test models where supported;
  - run a minimal non-streaming health prompt;
  - return safe error envelopes.
- GM Assistant workspace widget:
  - first shippable UI should expose live capture, Build Session Recap, and Memory Inbox;
  - provider/model status, context preview, run history, branch proposals, and planning markers live behind compact drawers or later tabs;
  - fast trusted preview is allowed when context hash and source classes match the last reviewed preview; stale or changed context forces full preview.
- Proposal lifecycle for option-generating tasks:
  - `proposal_set` records linked to campaign/session/scene/entity context and the originating LLM run;
  - `proposal_option` records with stable option IDs, title, summary, body, possible consequences, inspection-only proposed delta, marker draft, visibility, and status;
  - `planning_marker` records carry the selected GM intent forward as planning context, with scope, expiry, provenance, edit metadata, and lint warnings;
  - statuses: proposed, selected, rejected, saved_for_later, superseded, canonized;
  - shipped actions: "Adopt as Planning Direction", "Save for later", "Reject", "Expire Marker", and "Discard Marker";
  - selected options without active planning markers do not enter normal future context;
  - direct proposal-body canonization and entity/state patches remain deferred and are not silently created.
- Structured response contracts:
  - proposal tasks must return machine-readable options where supported by the provider;
  - each option should include a short GM-facing summary, possible consequences if played, what may be revealed, what remains hidden, and a concise planning marker draft;
  - one/two valid options are stored as degraded success with visible warnings;
  - malformed option rows are discarded only with normalization warnings;
  - malformed output after one schema-repair attempt fails visibly and creates no proposal records.
- Canonization and context hygiene:
  - shipped branch proposals create planning markers, not canon memory, notes, entity drafts, faction/location/quest records, or session state patches;
  - shipped recap memory candidates can canonize a planning marker only after played non-planning evidence supports the accepted memory entry;
  - rejected options are stored as rejected proposal history, not as campaign memory;
  - saved-for-later options enter an idea bank and are not active canon;
  - context packages include approved memory and active planning markers, never raw brainstorm sets by default;
  - canonized markers leave active planning context; accepted memory carries the future canon fact;
  - proposal/rejection history is included only when the GM explicitly selects a brainstorm-history or contradiction-checking context mode.
- Append-only session transcript:
  - live DM note capture events with backend timestamps and per-session order;
  - DM prompts;
  - assistant responses;
  - LLM runs;
  - proposal sets and option status transitions;
  - canonization decisions;
  - accepted draft artifacts;
  - dice/combat events when those domains exist;
  - scene changes;
  - player-display publish events;
  - tool/result references where applicable.
- Structured session memory:
  - campaign/session-scoped record in SQLite as source of truth;
  - optional markdown rendering for human inspection;
  - updated through explicit/manual extraction first, and later through safe-point background updates.
- Exact recall lane:
  - SQLite FTS-backed lexical recall over transcript, notes, approved memory, proposal history, and canonization decisions;
  - alias expansion for fantasy names, transliteration, multilingual notes, and dictation mistakes before vector retrieval is considered;
  - hard retrieval policy filter before any results enter model context;
  - status-aware retrieval that prefers canonized/approved state over proposals, and suppresses rejected options unless explicitly requested;
  - trigger patterns for explicit recall ("what did we decide?", "who was this NPC?", "as discussed"), entity lookup gaps, continuation gaps, and contradiction checks;
  - recall results are injected as bounded evidence snippets with source IDs, not as uncited model "memory";
  - timeout and fallback behavior must keep GM generation responsive.
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
  - canonized generated content and saved-for-later ideas;
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
  - recall exact prior decisions from campaign/session history;
  - extract unresolved hooks;
  - roleplay an NPC from approved NPC card facts and exact recall evidence;
  - prefill or suggest updates for a GM-created NPC card;
  - prefill or suggest updates for settlement records from current campaign context;
  - prefill or suggest faction/political moves and consequences;
  - prefill or suggest quest board entries from unresolved hooks;
  - prefill or suggest character-building hooks and personal arc options;
  - generate creative alternatives/options with structured proposal output;
  - draft next-scene complications;
  - draft NPC/entity ideas for GM-owned records;
  - generate location/item/faction/vehicle ideas;
  - draft player-safe public snippet;
  - draft combat encounter twists without rules automation;
  - draft token/image/map/handout prompts for a diffusion/image harness;
  - draft character sheets as entity/custom-field drafts;
  - check selected notes for contradictions.
- Draft artifacts:
  - proposal set;
  - proposal option;
  - canonization state patch;
  - saved-for-later idea;
  - private note draft;
  - public snippet draft;
  - entity draft;
  - custom field value draft;
  - token draft;
  - map/handout/image prompt draft;
  - character sheet draft;
  - session recap draft.
- Draft apply actions are explicit:
  - select proposal option;
  - edit and canonize selected option in a future canonization slice;
  - save proposal option for later;
  - reject proposal option or proposal set;
  - save as private note;
  - create public snippet;
  - create GM-owned entity from reviewed draft;
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
  - created proposal sets and current option statuses;
  - canonization actions produced from selections;
  - created draft artifacts;
  - applied/not-applied status;
  - error state;
  - retention controls for full prompt/response payloads, with metadata kept after purge/redaction.
- Observability:
  - exact recall triggered/skipped/timed out;
  - recall source count and evidence token estimate;
  - proposal generated/selected/rejected/canonized;
  - whether a context package excluded rejected/proposed branches;
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
- Generated options are not durable campaign truth until a GM selection/canonization action commits them.
- Normal future context includes selected/canonized state, not every option the model proposed.
- Rejected options must not enter normal creative generation context.
- `/player` never talks to LLM endpoints and never receives private LLM context.
- Browser transport remains notify-only and carries no LLM prompt, response, or generated payload.
- Context sent to remote/local models is explicit, previewable, and campaign-scoped.
- Private notes, GM secrets, hidden tokens, private entities, and unrevealed clues are sent only when the selected prompt/context mode explicitly includes GM-private context.
- Public-safe workflows use public-known facts and public snippets/party/map display state only.
- Public-safe drafts require leak review before snippet creation; deterministic warnings should flag suspicious hidden-fact language and private-only references.
- Generated public content is not published automatically.
- Diffusion/image outputs must pass through Slice 5 asset validation before becoming assets.
- Model/tool errors use the standard API error envelope and do not leak API keys or absolute local paths.

Acceptance checkpoint:

```text
configure OpenAI-compatible provider
  -> test provider/model connection
  -> capture timestamped live DM notes during a session
  -> click Build Session Recap after play
  -> preview exact recap evidence package
  -> save reviewed private recap
  -> review memory candidates
  -> accept selected facts into Memory
  -> ask "what did we decide for this scene?"
  -> exact recall returns accepted memory as cited evidence
  -> run player-safe recap from public-safe context
  -> leak warnings are shown where relevant
  -> publish only after explicit GM action
  -> later ask for five next-scene complications
  -> select option 2 and create a planning marker
  -> verify only the selected planning direction enters normal context
  -> run compact simulation
  -> compact result preserves current scene, unresolved hooks, NPC state, combat/mechanics state, and recent verbatim tail
  -> generate NPC/character sheet/image prompt drafts
  -> save one reviewed entity draft as a GM-owned record and one image prompt draft explicitly
  -> refresh browser
  -> provider config, memory, run history, and applied drafts persist from SQLite
```

Explicit deferrals:
- no autonomous agent loop;
- no automatic campaign mutation;
- no automatic proposal selection or canonization;
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
