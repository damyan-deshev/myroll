# Myroll Backlog

Date: 2026-05-02

## Completed

- Slice 1 backend foundation.
- Slice 2 backend writes and runtime activation.
- Slice 3 GM frontend shell with persistent workspace canvas.
- Slice 4 local player display service.
- Slice 5 asset metadata and image display.
- Slice 6 map display MVP.
- Slice 7 manual fog MVP.
- Slice 8 tokens and visibility.
- Slice 9 notes and public snippets.
- Slice 10 entities, custom fields, party tracker, and public party projection.
- Slice 11 combat tracker basics and public initiative projection.
- Slice 12 scene orchestration and GM context staging.
- Slice 13 backup, export, restore, and original public demo hardening.
- Post-Slice 13 laptop UX rework: docked `/gm` overview, focused GM surfaces, and preserved `/gm/floating` advanced canvas.

## Near Term

- Plan the asset import/battle-map integration slice:
  - bundled static asset-pack registration so built-in maps ship with the app;
  - curated production battle-map pack importer;
  - multi-file user asset import for maps, handouts, portraits, and token art;
  - GM grid size and nudge controls for gridless maps;
  - category/search browser for imported map assets.
- Slice 14 LLM/session-memory work after backup/export hardening.
- Improve per-surface ergonomics incrementally: panel density, shortcuts, and focused map workbench controls.

## Product Risks To Keep Visible

- Do not let browser storage become an accidental source of truth again.
- Do not add player remote URL/relay work before the local player display is solid.
- Do not let `/api/player-display/assets/{asset_id}/blob` become a generic asset server; it must serve only the active public display image.
- Do not turn placeholder widgets into fake controls before their backend domains exist.
- Do not introduce auth, Docker, WebSockets, or remote player clients before the local display loop is stable.
- Do not accept player-display work without visual/e2e screenshots; DOM-only checks are not enough for this product surface.
- Do not let `/player` fetch private campaign/runtime APIs; it must consume public display state only.
- Do not let `show-map` mutate GM runtime or scene-map activation state.
- Do not serve arbitrary map/image assets from the public blob endpoint; active display payload still gates the bytes.
- Do not let `/api/player-display/fog/{fog_mask_id}/mask` become a generic fog mask server; it must serve only the active public display fog mask.
- Do not let tokens bypass fog visibility or public map sanitization.
- Do not let token portraits turn `/api/player-display/assets/{asset_id}/blob` into a generic portrait server; it must serve only assets referenced by the active public payload.
- Do not let public text display read from private notes. Text payloads must be built from `public_snippets` only.
- Do not turn public snippets into live views over notes. A snippet is a snapshot record, and private note edits must not change it automatically.
- Do not enable raw HTML in markdown rendering for notes or player text display.
- Do not let public party projection read raw entity records directly. It must pass through the party sanitizer.
- Do not expose entity notes, tags, private entities, non-roster entities, or non-public custom fields in `party` player payloads.
- Do not let party portrait/image field assets turn the player blob endpoint into a generic entity asset server.
- Do not make custom fields rules-specific in the core model; Slice 10 fields are typed data primitives, not D&D automation.
- Do not infer public initiative visibility from token/entity visibility after combatant creation. `combatants.public_visible` is the only public initiative gate.
- Do not expose HP, AC, temp HP, private conditions, combat notes, entity tags, or private fields in `initiative` player payloads.
- Do not let initiative portraits turn the player blob endpoint into a generic portrait server; active public initiative payload references gate the bytes.
- Do not build rules automation into the combat tracker before the manual model is proven in sessions.
- Do not let scene activation mutate `player_display_runtime`. Scene activation is private GM context only.
- Do not publish scene context directly to `/player`; staged scene display must reuse the existing public display sanitizers.
- Do not turn scene-linked entities, snippets, or notes into implicit public content.
- Do not let LLM output mutate campaign state directly. It must create drafts that the GM explicitly applies.
- Do not send hidden/private campaign context to a model unless the GM selected a GM-private context mode and can preview the payload.
- Do not expose API keys, absolute paths, or raw prompt payloads through public endpoints, logs, screenshots, `/health`, or `/api/meta`.
- Do not publish generated snippets/images/maps/party data to `/player` automatically from an LLM response.
- Do not bypass the existing asset validation pipeline for diffusion/image outputs.
- Do not reintroduce public arbitrary `source_path` imports while adding bulk asset import; user-facing import must keep an explicit user-selected file boundary.
- Do not require installed users to manually import the built-in static map pack after setup.
- Do not let bundled production packs become frequently rewritten binary churn in git; treat committed packs as immutable versions and move to LFS/release artifacts only when size/update frequency forces it.
- Do not let battle-map pack import serve images directly from the external pack directory; imported assets must be copied into managed storage.
- Do not treat generated map prompts, filenames, or contact sheets as tactical scale; use manifest/category grid contracts only.
- Do not calibrate gridless maps by rewriting the source image or changing fog/token coordinate space; use live grid size and offsets.
- Do not commit local demo display-name overrides or private local asset manifests; public demo data stays English and original.
- Do not restore exports in-place over live user data; restore remains offline/script-only into a new data dir.
- Do not treat export archives as encrypted vaults; they are local convenience packages.
- Do not force dense laptop workflows back into one global floating canvas. Use focused GM surfaces by default and keep floating panels as advanced/contextual tools.
