# Myroll Decision Register

Date: 2026-04-27

## DR-001: Use A Local Backend For MVP Persistence

Decision: use FastAPI as a local control plane and SQLite as durable source of truth.

Rationale:
- Browser IndexedDB persistence is not a good primary durability story for this use case.
- A local backend gives migrations, backups, stable data paths, seeded demos, and a path toward richer local runtime services.

Consequences:
- Browser storage is downgraded to UI runtime/cache.
- Backend startup and database hygiene become product-critical.

## DR-002: SQLite With Defensive Defaults

Decision: every SQLite connection must enable:

```text
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
```

Rationale:
- Foreign keys must be enforced, not decorative.
- WAL and busy timeout make local development/runtime behavior more robust.

Consequences:
- PRAGMAs must be installed through the SQLAlchemy connection event hook.
- Tests must verify runtime connections, not only migration/init connections.

## DR-003: Alembic From Day One

Decision: use Alembic immediately.

Rationale:
- Local-first data lives long enough to need migrations.
- A homegrown schema bootstrap would become accidental migration infrastructure.

Consequences:
- Runtime app, Alembic, tests, and seed logic all read DB path from the same settings layer.
- Seed logic stays separate from migrations.

## DR-004: Backup Before Migration

Decision: before migration, copy an existing non-empty SQLite DB to `data/backups/`.

Rationale:
- A bad local migration is a higher-risk failure than a failed first boot.

Consequences:
- Empty or missing DB files do not get backups.
- Backup filenames include UTC timestamp and `.pre-migration`.

## DR-005: No Remote Player Link In MVP

Decision: MVP player display is a local `/player` tab/window meant for fullscreen, tab sharing, or Chromecast tab casting.

Rationale:
- Chrome/Meet already support tab sharing and tab audio.
- Remote player URLs imply a different transport and threat model.

Consequences:
- No relay, WebRTC, TURN, or public campaign URL in MVP.
- Audio remains a future consideration for player-facing tab sharing.

## DR-006: Singleton Runtime Context

Decision: active campaign/session/scene state lives in one `app_runtime` row with `id = "runtime"`.

Rationale:
- Myroll is currently a personal local tool, not a multi-workspace service.
- Frontend bootstrapping needs one clear active context.

Consequences:
- The database enforces the singleton with primary key plus `CHECK (id = 'runtime')`.
- Runtime activation endpoints are transactional.
- Failed activation must leave runtime unchanged.

## DR-007: Runtime Activation Uses Action Endpoints

Decision: activate campaign/session/scene through action endpoints rather than raw runtime snapshot writes.

Rationale:
- Activation has domain semantics: setting a scene also sets its campaign and linked session.
- Command-like endpoints keep implicit consistency logic on the backend.

Consequences:
- Activation endpoints return the current runtime response body.
- `activate-session` preserves active scene only when the scene belongs to that session.

## DR-008: API Error Envelope

Decision: public API errors use a standard envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": []
  }
}
```

Rationale:
- The frontend should not special-case FastAPI's default `detail` response shape.
- Validation, not-found, and safe database errors need one stable contract.

Consequences:
- FastAPI validation errors are translated.
- HTTP exceptions are translated.
- SQLAlchemy integrity errors are translated to a safe generic database error.

## DR-009: Persistent Scoped Workspace Widgets

Decision: GM cockpit layout is stored in backend `workspace_widgets`, not browser storage.

Rationale:
- Widget position is part of the durable local workspace experience.
- Layout persistence should survive browser cache clearing.
- Scoping needs to exist before scene-specific layouts arrive.

Consequences:
- Slice 3 uses `scope_type = "global"` and `scope_id = null`.
- Future campaign or scene layouts should reuse the same `scope_type` and `scope_id` primitive.
- Widget `config_json` must remain a valid JSON object and is returned as parsed `config`.
- Drag and resize persist on stop, not on every pointer movement.

## DR-010: Canvas Shell Before Full Canvas Domain

Decision: build a positioned widget workspace first, without pan/zoom, minimap, snap guides, or map-domain canvas behavior.

Rationale:
- The first frontend must prove the current backend loop: status, create, browse, activate, persist layout.
- Map and fog canvas behavior is a separate product domain with stricter rendering and public/private safety requirements.

Consequences:
- `/gm` is a cockpit surface now.
- Map display stays placeholder-only until its asset/map/player-display slice exists; as of Slice 6 it is functional.
- The workspace canvas is an organization layer, not a map engine.

## DR-011: Placeholder Widget Policy

Decision: cockpit placeholders are allowed only when they are visibly disabled and expose no fake controls.

- The layout should communicate the intended run-focused GM operating shape without pretending unfinished domains work.
- Fake controls create incorrect product expectations and misleading tests.

Consequences:
- Placeholder widgets document their future slice ownership.
- Current placeholder kinds are `party_tracker`, `combat_tracker`, and `dice_roller`.
- A placeholder must become functional only when its backend/domain slice exists.

## DR-012: Visual E2E Is Required For UI Slices

Decision: frontend slices require Playwright browser tests with screenshots, not only DOM/unit tests.

Rationale:
- The GM cockpit and player display are visual operating surfaces.
- DOM assertions can pass while layout, refresh timing, or degraded states are visibly wrong.
- Playwright already caught Slice 3 selection/reload races that unit tests did not cover.

Consequences:
- UI slices should include Playwright coverage for happy path, refresh/reconnect, and degraded states.
- Screenshots are written to `artifacts/playwright/`.
- DOM-only test coverage is insufficient for `/gm` and `/player` acceptance.

## DR-013: Player Display Runtime Is Backend Truth

Decision: active public presentation state lives in singleton `player_display_runtime`, not in browser transport or the future `display_states` history table.

Rationale:
- `/player` must recover after refresh/reconnect.
- Browser windows and channels are unreliable coordination surfaces.
- Public display state needs a separate truth from private GM runtime.

Consequences:
- `player_display_runtime.id` is constrained to `player_display`.
- `mode` is constrained to the implemented public display modes: `blackout`, `intermission`, `scene_title`, `image`, `map`, `text`, and `party`.
- `show-scene-title` reads from `app_runtime` when needed but never mutates it.
- Existing `display_states` remains reserved for future presets/history.

## DR-014: Browser Display Transport Is Notify-Only

Decision: `postMessage` and `BroadcastChannel` carry only heartbeat and changed-state notifications.

Rationale:
- Backend state should win.
- Browser messages should not become accidental public display payloads.
- `/player` should fetch the same sanitized public state after every notification.

Consequences:
- Transport messages include namespace, type, display window ID, revision, identify revision, and sent timestamp.
- Transport messages never carry title, subtitle, scene names, campaign names, or payload content.
- `/player` calls only public display endpoints.
- If refetch fails after a successful public state, `/player` keeps the last known state and marks reconnecting without replacing content.

## DR-015: Asset Blobs Are Managed Content-Addressed Files

Decision: imported image bytes are copied into `data/assets/` under content-addressed relative paths; SQLite stores metadata and the managed storage key.

Rationale:
- Asset files need to be portable with the local data directory.
- Server-path import must not leave hidden dependencies on Desktop, Downloads, or external folders.
- Duplicate image bytes should not waste storage, but repeated imports may still be separate asset records.

Consequences:
- Browser upload and server-path import both copy bytes into managed storage.
- Server-path import never stores the original absolute path as the asset location.
- Duplicate checksums may share `relative_path`, while asset IDs remain distinct.
- Export/backup can later package SQLite plus `data/assets/` without path archaeology.

## DR-016: Image Metadata Comes From Backend Validation

Decision: backend image import does not trust client MIME type, extension, filename, width, height, or other client metadata.

Rationale:
- Browser-provided metadata is advisory and unsafe.
- The backend must know the actual image format and dimensions before storing public-displayable assets.
- Large compressed images can create memory pressure after decode.

Consequences:
- Pillow validates PNG, JPEG, and WebP.
- Image MIME type, extension, width, and height are derived from the decoded image.
- Import enforces both byte-size and decoded-pixel limits.
- Decompression bomb warnings/errors are rejected.
- Blob writes are atomic: temp file first, final content-addressed path second.

## DR-017: Player Display Asset Blob Endpoint Is Active-State Scoped

Decision: `/api/player-display/assets/{asset_id}/blob` serves only the active public image/map asset referenced by `player_display_runtime`.

Rationale:
- `/player` needs image/map bytes, but the endpoint must not become a generic asset server.
- Public display should expose only the currently projected public state.

Consequences:
- Private assets are not served.
- Public but inactive assets are not served.
- Missing blobs and invalid storage paths return standard error envelopes without absolute filesystem paths.
- Player display image/map payloads contain only public-safe metadata and a relative public blob URL.

## DR-018: Scene Maps Enforce One Active Map Per Scene

Decision: scene map assignment supports multiple maps per scene, but exactly one active scene map is allowed per scene.

Rationale:
- A scene may need alternate map versions or phases.
- GM preview and later fog/token state need one unambiguous active scene map.
- The invariant is important enough to enforce in SQLite, not only in UI logic.

Consequences:
- `scene_maps` has a partial unique index on `scene_id` where `is_active = 1`.
- Activation is transactional: clear active maps for the scene, flush, then set the selected map active.
- Assignment with `is_active = true` uses the same activation helper as the explicit activate endpoint.
- `show-map` does not activate maps; publishing and GM scene-map state remain separate operations.

## DR-019: Map Renderer Accepts Sanitized Render Props

Decision: the shared map renderer consumes sanitized `MapRenderPayload` props, not raw backend records or ORM-shaped private data.

Rationale:
- `/player` must render only public display state.
- GM preview can share rendering code without sharing private backend object shapes.
- The public/private boundary should remain visible in the frontend type layer before fog and tokens add more hidden state.

Consequences:
- GM preview converts `SceneMap` records into render props before rendering.
- `/player` converts `player_display_runtime.payload` into render props before rendering.
- Browser transport remains notify-only and never carries map titles, asset metadata, grid settings, or payload content.
- Missing blobs/assets render intentional unavailable states, not silent black or empty map success.

## DR-020: Square Grid Calibration Before Fog And Tokens

Decision: Slice 6 supports square grid calibration only, stored on campaign maps and optionally shown per scene-map/player projection.

Rationale:
- Fog and token geometry need a map coordinate foundation.
- Square grids are enough for the MVP map display loop.
- Hex grids, pan/zoom, measuring, and token snapping would expand the scope before the public map pipeline is proven.

Consequences:
- Grid size is bounded and grid offsets must be finite.
- Grid color is normalized to safe `#RRGGBB`; opacity is bounded to `0..1`.
- Scene-map player settings decide whether the grid is public-visible and how the map fits on `/player`.
- Hex grids, pan/zoom, token snapping, measuring, and line-of-sight remain deferred.

## DR-021: Fog Masks Are Scene-Map Visibility State

Decision: manual fog lives as one durable internal mask per scene map, not as an Asset Library record or browser-only canvas state.

Rationale:
- Fog is public/private visibility state for a specific scene-map assignment.
- `/player` must recover fogged map state after refresh.
- GM and player renderers need the same sanitized map payload boundary before tokens arrive.

Consequences:
- Fog masks are grayscale PNGs under managed internal storage.
- `0` means hidden from players and `255` means visible.
- Fog operation coordinates are intrinsic map pixels.
- Fog operation commits persist the mask, increment fog revision, and republish player display only when the same scene map is currently projected.
- Public fog mask bytes are served only when referenced by the current active `player_display_runtime` map payload.
- Browser transport remains notify-only and never carries fog payloads, mask URLs, or mask bytes.

## DR-022: Token Coordinates Use Map-Intrinsic Center Points

Decision: token `x/y` values are center points in intrinsic map pixel coordinates. Token `width/height` are rendered size in intrinsic map pixels, and rotation is around token center.

Rationale:
- Fog visibility and token placement need one stable coordinate convention.
- CSS transform origins, top-left positioning, and device pixel ratios should not leak into persistence.

Consequences:
- GM drag/resize converts screen coordinates back into intrinsic map pixels before saving.
- `hidden_until_revealed` checks the token center point against the fog mask.
- Future snap-to-grid, measuring, and token bounds logic must preserve this convention.

## DR-023: Public Map Payload Uses One Sanitizer

Decision: public map payload generation, including tokens, must go through one centralized sanitizer.

Rationale:
- Tokens are public/private objects, not just rendered shapes.
- Hand-rolled filtering in individual endpoints would eventually leak hidden tokens, private labels, or private portrait assets.

Consequences:
- `show-map`, fog republish, and token republish all use the same payload builder.
- GM-only tokens are excluded from public payloads.
- `hidden_until_revealed` tokens are included only when the token center is revealed by fog.
- Labels appear only when `label_visibility = player_visible`.

## DR-024: Token Mutations Conditionally Republish Public Display

Decision: token create/update/delete compares the old and new sanitized public map payload for the active displayed scene map before republishing `player_display_runtime`.

Rationale:
- Public display should update live when visible token state changes.
- Private-only edits should not increment public display revision or broadcast unnecessary notifications.
- Deletes need old token state to know whether public payload changed.

Consequences:
- Token mutation responses include `player_display` only when public display changed.
- GM broadcasts notify-only transport only after a successful mutation that returns new public display state.
- Public token portrait bytes are served only while referenced by the active public payload.

## DR-025: Public Snippets Are Snapshot Records

Decision: public snippets are explicit records with their own public body, not live views or authoritative ranges over private notes.

Rationale:
- A private note can contain spoilers, prep text, and later edits that should not change what players see.
- "Create from selection" must copy selected text at that moment so the GM can review a stable public reveal before publishing.

Consequences:
- `public_snippets.note_id` is traceability only.
- Updating a note does not mutate linked snippets.
- Slice 9 does not store authoritative range pointers.

## DR-026: Text Player Payloads Are Built Only From Public Snippets

Decision: `show-snippet` builds `player_display_runtime.payload` only from `public_snippets.title`, `public_snippets.body`, and `public_snippets.format`.

Rationale:
- `/player` must never receive full private note bodies.
- The public/private boundary should be enforced in the backend payload builder, not left to frontend discipline.

Consequences:
- Text payloads do not expose `note_id`.
- `show-snippet` does not mutate app runtime, notes, snippets, scene state, or assets.
- Tests must include a private-note secret phrase that is absent from player display payloads.

## DR-027: Safe Markdown Rendering For Notes And Text Display

Decision: GM snippet preview and `/player` text mode use the same safe markdown renderer with raw HTML disabled and links rendered inert.

Rationale:
- The player display is a projection surface, not a web browser destination.
- Rendering must not make raw HTML, scripts, or unexpected navigation part of the public reveal path.

Consequences:
- Do not use `rehypeRaw`.
- Raw HTML stays disabled.
- Links are displayed as text/non-navigating content in Slice 9.

## DR-028: Entities Are System-Agnostic Typed Records

Decision: Slice 10 entities are campaign-scoped system-agnostic records with explicit kind, visibility, optional portrait asset, tags, private notes, and typed custom field values.

Rationale:
- The product should support many RPG systems and homebrew workflows before hard-coding combat/stat assumptions.
- Party cards, NPCs, locations, items, factions, and future combatants need the same flexible data primitive.

Consequences:
- Entity visibility defaults to `private`.
- Custom fields are campaign-scoped and typed, but not rules-specific.
- Custom field keys are stable lowercase slugs and field type/key are immutable after creation.
- Field values are validated JSON and only apply to configured entity kinds.

## DR-029: Party Tracker Uses An Explicit Roster

Decision: party tracker membership is persisted as an ordered roster, not inferred from all public PCs.

Rationale:
- A campaign can contain retired PCs, guest PCs, NPC companions, or private test entities.
- Public party projection should be a deliberate GM-curated card set.

Consequences:
- There is one party tracker config per campaign.
- Slice 10 roster accepts `pc` entities only.
- Card fields are separately ordered through `party_tracker_fields`.
- `party_tracker_fields.public_visible` controls which selected fields are eligible for player projection.

## DR-030: Public Party Projection Uses A Strict Sanitizer

Decision: `show-party` builds public party payloads only through a sanitizer over party config, roster entities, and selected public fields.

Rationale:
- Entity records contain private notes, tags, and fields that should never reach `/player`.
- Public projection must stay explicit and inspectable like map, token, fog, and snippet payloads.

Consequences:
- Public party payload includes only roster entities with `visibility = public_known`.
- It excludes entity notes, tags, private entities, non-roster entities, and fields where `public_visible = false`.
- Portrait URLs and image field asset URLs appear only for `public_displayable` image assets.
- `/api/player-display/assets/{asset_id}/blob` serves party images only when referenced by the active public `party` payload.
- Browser transport remains notify-only and never carries entity/party payloads.

## DR-031: Token Entity References Do Not Expand Public Data Yet

Decision: Slice 10 validates optional `scene_map_tokens.entity_id` references but does not expand entity data into token public payloads.

Rationale:
- Entity data has its own public/private sanitizer and should not accidentally leak through map tokens.
- Token stat sync, labels from entity display names, health bars, and combat integration need a separate design.

Consequences:
- Token create/update rejects entity IDs from another campaign.
- Public token payload remains the Slice 8 sanitized token payload.
- Entity-driven token overlays are deferred to a later explicit slice.

## DR-032: LLM Is A Drafting Layer, Not Source Of Truth

Decision: the LLM assistant may generate summaries, ideas, snippets, entities, character sheets, token drafts, and image/map prompts, but it never mutates durable campaign state directly.

Rationale:
- Myroll's durable truth is SQLite plus managed asset blobs.
- Live D&D assistance is useful only if the GM stays in control of private/public boundaries and accepted fiction.
- Model output can be useful, wrong, spoiler-leaking, or stylistically off; applying it must be explicit.

Consequences:
- LLM responses are stored as run history and draft artifacts.
- Drafts require explicit GM apply actions before becoming notes, snippets, entities, tokens, image prompts, or assets.
- Generated public content is never sent to `/player` automatically.
- `/player` never calls LLM endpoints or receives LLM-private context.

## DR-033: Session Memory Uses Transcript Plus Structured State

Decision: live-session LLM continuity uses an append-only transcript for exact details and a bounded structured session memory record for model-facing continuity and compaction.

Rationale:
- A single late summary is too fragile for live campaign continuity.
- Exact transcript needs to remain available for details without stuffing all old turns into model context.
- D&D continuity depends on current scene, NPC motivations, secrets, clues, player decisions, and active mechanics more than full chat history.

Consequences:
- Compaction creates explicit compact boundary records.
- Model-facing context is rebuilt from compact summary, preserved verbatim tail, and structured attachments.
- Tail selection must not split dice adjudication, tool results, rules lookups, combat rounds, or active scene starts.
- Session memory is inspectable and bounded.

## DR-034: LLM Context Packages Must Be Previewable And Scoped

Decision: every LLM run is built from an explicit context package selected by the GM, with a preview of what campaign/session/scene data will be sent.

Rationale:
- Some models may be remote, and private GM content should not be sent accidentally.
- Myroll already enforces strict public/private boundaries for player display; LLM context needs the same discipline.
- Different assistant tasks require different context scopes: public recap, GM-only prep, entity drafting, image prompt drafting, or contradiction checking.

Consequences:
- Prompt templates declare allowed context modes.
- Public-safe workflows use public-known data only.
- GM-private workflows may include notes, secrets, hidden tokens, unrevealed clues, and private entities only when explicitly selected.
- LLM run history stores the selected context snapshot and prompt template metadata.

## DR-035: Generated Images Enter Through Asset Validation

Decision: LLM/diffusion image workflows produce prompt records and generated files, but any generated image must enter Myroll through the existing Slice 5 asset import/validation pipeline.

Rationale:
- Image generation output is still untrusted bytes.
- The product already has validated metadata, managed blob storage, checksums, visibility, and public-display gating.
- Bypassing the asset pipeline would weaken public display and backup/export guarantees.

Consequences:
- Diffusion prompts and negative prompts can be first-class draft artifacts.
- Generated images default private.
- Marking generated images public-displayable remains an explicit GM action.
- Public image/map/token use still depends on active player-display payload references.

## DR-036: Public Initiative Visibility Is Explicit Combat State

Decision: public initiative projection is gated only by `combatants.public_visible`, not by linked entity visibility or linked token visibility.

Rationale:
- A visible token or public-known entity should not automatically reveal turn order participation.
- Combat reveal timing is table-state, not a direct consequence of map/entity public state.
- Entity/token visibility can be useful as a creation-time default, but it must not become a live binding.

Consequences:
- Linked entity/token visibility may seed `public_visible` when creating a combatant.
- After creation, changing entity/token visibility does not change initiative projection.
- Player initiative payloads include only combatants with `public_visible = true`.

## DR-037: Combat Conditions Are Private, Public Status Is Curated

Decision: `conditions_json` stores GM/private combat state, while `public_status_json` stores bounded player-facing status labels.

Rationale:
- Some combat state is safe to reveal, such as "Blessed".
- Other state is intentionally hidden, such as secret charm, delayed effects, or GM-only notes.
- Arbitrary nested JSON would quietly become a mini content system and increase leak risk.

Consequences:
- `public_status_json` accepts only strings or small `{ label }` objects.
- `conditions_json`, HP, AC, temp HP, and combat notes never enter public initiative payloads.
- `/player` initiative mode renders only the sanitized public status list.

## DR-038: Initiative Projection Uses A Strict Sanitizer

Decision: `show-initiative` builds `player_display_runtime.payload` through a public initiative sanitizer rather than exposing raw encounter or combatant records.

Rationale:
- Combatant rows contain private mechanics and GM notes.
- Public initiative needs current turn/order without revealing HP, AC, hidden enemies, tags, conditions, or private entity data.
- The display contract should stay consistent with maps, tokens, snippets, and party cards.

Consequences:
- Public initiative payload includes encounter ID, round, active combatant ID, and sanitized combatant rows.
- Portrait URLs appear only for public-displayable image assets referenced by the active payload.
- `/api/player-display/assets/{asset_id}/blob` serves initiative portraits only while referenced by active `initiative` display state.
- `show-initiative` does not mutate encounter turn state.

## DR-039: Scene Activation Is Private GM Context

Decision: `activate-scene` updates the GM runtime context only and never mutates `player_display_runtime`.

Rationale:
- A GM often needs to focus notes, maps, encounters, and entities before revealing anything to players.
- Automatic public display mutation during scene activation creates accidental reveal risk.
- The product invariant is that public presentation changes are explicit GM actions.

Consequences:
- Scene activation can update `app_runtime.active_scene_id` and GM cockpit focus.
- `/player` remains unchanged after private scene activation.
- Tests must compare `player_display_runtime.updated_at` before and after `activate-scene`.

## DR-040: Scene Display Staging Requires Explicit Publish

Decision: scene context stores staged public display intent, but only `POST /api/scenes/{scene_id}/publish-staged-display` mutates public display state.

Rationale:
- Staging lets the GM prepare the next reveal without changing what players see.
- Publish readiness depends on mode-specific validation, such as active map availability, linked snippet selection, or active encounter presence.
- A single publish action creates a clear UI and audit boundary.

Consequences:
- `staged_display_mode = none` is rejected on publish.
- `public_snippet` publish requires the staged snippet to be explicitly linked to the scene.
- `active_map` and `initiative` publish reuse the existing map and initiative display paths.
- GM broadcast notifications happen only after successful backend publish.

## DR-041: Scene Context Reuses Public Sanitizers

Decision: scene context APIs are GM-private, and staged publish calls existing player-display serializers/sanitizers instead of serializing scene context directly.

Rationale:
- Scene context can include private notes, entity links, GM notes, and combat state.
- The public/private boundary already exists in map, snippet, initiative, and player-display display builders.
- Reusing those paths avoids a second leak-prone serialization layer.

Consequences:
- Scene context responses are never consumed by `/player`.
- Private notes, entity fields, combat notes, hidden combatants, and GM-only links cannot enter player payloads through scene context.
- Adding new staged modes later requires wiring to the relevant existing public display sanitizer.

## DR-042: Scene-Aware Widgets Keep Global Workspace Layout

Decision: Slice 12 keeps the workspace layout global while widgets gain selected-scene focus and filters.

Rationale:
- Scene-scoped layouts are useful later, but would add layout migration and user-model complexity now.
- The current need is orchestration: focus the existing tools around the active scene.
- Global widget layout remains stable during live sessions.

Consequences:
- `scene_context` coordinates scene links, active encounter, and staged display.
- Notes and combat widgets can react to selected/active scene.
- No scene-scoped workspace layout or automatic widget rearrangement is part of Slice 12.

## DR-043: Export Archives Package SQLite Plus Managed Assets

Decision: Slice 13 exports a local `.tar.gz` archive containing a SQLite snapshot, the managed `assets/` tree, and a `myroll-export.json` manifest with file sizes and checksums.

Rationale:
- SQLite is the durable source of truth for structured data.
- Managed filesystem blobs are required for images, maps, portraits, and fog masks.
- A manifest makes restores and future integrity checks inspectable without inventing a database-specific export format.

Consequences:
- Export archives are named `myroll.<timestamp>.export.tar.gz`.
- `.tmp` files are excluded.
- Archive paths are validated during restore to prevent path traversal.
- Export archives are local convenience packages, not encrypted vaults.

## DR-044: Restore Is Offline And Targets A New Data Directory

Decision: restore is script-only in Slice 13 and writes into a target data directory, refusing non-empty targets unless `--force` is supplied.

Rationale:
- Live in-place restore can destroy the active campaign state and complicate open DB handles.
- The safest portable workflow is export, restore elsewhere, then start the app with `MYROLL_DATA_DIR`/`MYROLL_DB_PATH` pointed at the restored directory.
- A script keeps the UX honest until restore semantics are battle-tested.

Consequences:
- No GM UI restore button in Slice 13.
- `scripts/restore_export.sh` validates archive paths and restores DB/assets offline.
- The restore script prints the env command needed to start from restored data.

## DR-045: Public Demo Data Is Original And Public-Safe

Decision: committed demo data and generated asset names use public-safe original names. Local display-name overrides live only in ignored private mapping files.

Rationale:
- The demo should be shareable with non-Bulgarian users.
- A public repo/demo should not smell like borrowed campaign IP.
- The user's private table can still use local display names locally without pushing them into committed fixtures.

Consequences:
- `demo/local/name-map.example.json` is committed as a safe template.
- `demo/local/name-map.private.json` and optional private manifests are ignored.
- Demo reset applies private display-name overrides only when the local ignored map exists.
- Public/demo exports should be generated without the private map.

## DR-046: Generated Demo Assets Stay Small And Enter Through The Existing Asset Pipeline

Decision: Slice 13 commits only a small generated dark-fairytale demo image pack, and demo reset imports those files through the existing image validation/managed-storage pipeline.

Rationale:
- The demo needs real visual material for maps, portraits, and handouts.
- Large binary packs would bloat the repo and make day-to-day development slower.
- Generated images should still be treated as untrusted bytes and validated like uploads/imports.

Consequences:
- Generated assets live under `demo/assets/generated/lantern_vale_chronicle/`.
- The manifest records stable asset keys, prompts, roles, default visibility, and intended scene/entity usage.
- Imported demo blobs are copied into the active demo data dir under managed content-addressed paths.
- Git LFS remains deferred unless the pack size becomes a real problem.

## DR-047: Default GM UX Uses Focused Surfaces, Floating Canvas Remains Advanced

Decision: `/gm` is now a docked overview with focused GM workbench routes, while the original draggable/resizable widget canvas remains available at `/gm/floating`.

Rationale:
- The full cockpit outgrew a single laptop viewport once maps, fog, tokens, notes, party, combat, scene context, player display, and storage all became real.
- Map/fog/token work needs a large dedicated surface, not a small floating widget.
- The floating canvas remains valuable for power users and custom situational layouts, so it should not be removed.

Consequences:
- `/gm` is the default laptop-friendly overview.
- `/gm/map`, `/gm/library`, `/gm/actors`, `/gm/combat`, and `/gm/scene` are focused surfaces.
- `/gm/floating` preserves persistent `workspace_widgets` drag/resize behavior and continues to be covered by regression tests.
- Future UI work should prefer focused surfaces for dense workflows and reserve floating panels for contextual overlays or advanced custom layouts.
