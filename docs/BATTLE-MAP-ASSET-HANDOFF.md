# Battle Map Asset Handoff

Date: 2026-05-02

This is the entry note for the Myroll battle-map integration slice. The generated battle maps started as curated external input artifacts; the first production pack is now bundled with the app as an immutable asset-pack version.

Product requirement update: the current curated static maps should ship with Myroll directly. End users should not have to import this pack manually after installation.

Implementation status update:

- The production pack is committed under `bundled/asset_packs/myroll_battle_maps_production_v1/`.
- The backend bundled registry scans `project_root/bundled/asset_packs` plus optional `MYROLL_BUNDLED_ASSET_PACKS_DIR` paths.
- Bundled maps are exposed through `GET /api/bundled-asset-packs` and `GET /api/bundled-asset-packs/{pack_id}/maps`.
- Adding a bundled map uses copy-on-add through managed `data/assets/` storage via `POST /api/campaigns/{campaign_id}/bundled-maps`.
- User uploads now support batch image upload and `token_image` assets.
- The GM map workbench has bundled-map browsing plus grid size and fine/coarse nudge controls.

## Current Production Pack

Production pack root:

```text
/Volumes/External/projects/comfyui/asset_packs/myroll_battle_maps_production_v1
```

Important files:

- `manifest.json`: app-facing source of truth for accepted maps.
- `taxonomy.json`: browse taxonomy for collections/groups/categories.
- `assets/battle-maps/fantasy/<collection>/<group>/<category>/category.json`: category-local grid contract and compact category listing.
- `assets/battle-maps/fantasy/<collection>/<group>/<category>/images/*.webp`: curated delivery images.
- `curation/rejections.json`: rejected source images and reasons.
- `curation/contact_sheets/accepted/`: per-category accepted review sheets.
- `curation/contact_sheets/rejected/`: per-category rejected review sheets.
- `HANDOFF.md`: pack-local handoff with generation and curation details.

Counts:

- 700 generated source images reviewed.
- 608 accepted production WebP maps.
- 92 rejected source images.
- 25 production categories.

Verified manifest notes:

- `manifest.json` is the authoritative import source for this pack.
- `taxonomy.json` is useful for browsing by `collection -> group -> category`, but the importer should still validate against `manifest.json` and category-local `category.json`.
- Pack-level `asset.file` values are relative to the production pack root.
- Category-local `category.json` asset `file` values are relative to that category directory.
- `checksum` is an object with `sha256`, not a bare string.
- `image.gridless = true` is present on accepted assets; Myroll should still rely on the metadata/grid contract rather than inspecting pixels for a grid.

## Provenance

Raw source packs are preserved unchanged:

- `/Volumes/External/projects/comfyui/asset_packs/myroll_battle_maps_v1`
- `/Volumes/External/projects/comfyui/asset_packs/myroll_battle_maps_v2_diverse_spacious`
- `/Volumes/External/projects/comfyui/asset_packs/myroll_battle_maps_v3_weird_fantasy`

Generation happened in the ComfyUI workspace:

- V1 core: `/Volumes/External/projects/comfyui/pipelines/generate_battlemap_asset_pack.py`
- V2 diverse/spacious: `/Volumes/External/projects/comfyui/pipelines/generate_battlemap_v2_diverse_spacious.py`
- V3 weird fantasy: `/Volumes/External/projects/comfyui/pipelines/generate_battlemap_v3_weird_fantasy.py`
- Production curation/export: `/Volumes/External/projects/comfyui/tools/curate_battle_maps.py`

V2/V3 quality depended on tighter category prompts plus layout-guided img2img/blockout inputs. Prompt-only generation was not reliable enough for broad playable movement space.

## Curation Policy

The production pack rejects images that are not practical battle maps:

- obvious perspective/isometric/3D views;
- visible text, signatures, UI marks, or logo-like artifacts;
- too little playable movement space;
- disconnected decorative islands with weak tactical paths;
- abstract texture-like outputs;
- strong category mismatch;
- poor top-down readability.

Accepted images have stable descriptive filenames and are gridless. The tactical scale comes from `asset.grid` in `manifest.json` and from category-local `category.json`, not from baked grid pixels.

## Integration Slice

The first implementation is backend-first in behavior: the browser UI depends on the validated registry and add-to-campaign endpoint rather than reading pack files directly.

There are three related but separate asset workflows:

1. A bundled static asset-pack registry for curated packs shipped with the app.
2. A local development/admin importer for trusted curated packs such as this production battle-map pack.
3. A user-facing asset import flow for maps, token portraits, monster tokens, handouts, and other locally collected images.

The bundled workflow should make shipped maps available after install without manual import. The development/admin workflow may read a configured manifest path from the local machine. The user-facing workflow should use an explicit user-consent boundary such as browser upload or a future file/directory picker flow; it must not reintroduce the removed public `source_path` HTTP import.

Distribution recommendation:

- To avoid adding a separate storage/release-artifact dependency during the first integration slice, it is acceptable to commit this first production pack as a versioned immutable bundled asset pack.
- Treat committed production packs as append-only/replaced-by-new-version, not as frequently rewritten binary working files.
- Keep a tiny representative fixture pack for tests even if the full production pack is also committed.
- Revisit Git LFS, GitHub release assets, or another artifact store only if repository size or update frequency becomes a real problem.
- In development, allow `MYROLL_BUNDLED_ASSET_PACKS_DIR` or similar config to point at the local production pack root.
- In packaged releases, include the curated pack under the app resources directory and register it automatically on startup.

Recommended first slice:

1. Read `/Volumes/External/projects/comfyui/asset_packs/myroll_battle_maps_production_v1/manifest.json`.
2. Validate manifest schema, category paths, relative asset paths, checksums, image dimensions, and grid dimensions.
3. Resolve each `asset.file` relative to the production pack root and reject absolute paths or traversal.
4. Register the pack as a read-only bundled catalog.
5. When a GM adds a bundled map to a campaign, import or reference that WebP through the existing backend image validation/public-serving boundary.
6. Create normal campaign `map_image` asset records or equivalent campaign asset references.
7. Create campaign map records with square grid settings from `asset.grid`.
8. Persist `categoryKey`, `collection`, `categoryLabel`, source provenance, curation status, and bundled pack version as metadata for search/filter/regeneration.
9. Add the GM category browser after catalog validation and storage behavior are stable.

Chosen storage behavior for this first version: copy-on-add into managed content-addressed storage. Read-only bundled blob serving remains a possible future optimization, but it is not part of the current public display path.

Product rule: Myroll must overlay the grid live. Never infer tactical scale from prompt text, filename text, or visual contents.

GM map-workbench requirement:

- The current numeric grid size/offset model is the right persistence primitive.
- The UI should expose fast grid-size controls plus four-direction nudge controls, likely beside the grid toggle/settings, so the GM can scale and align the live grid over gridless maps without editing the image.
- Size controls should increase/decrease `grid_size_px`; fine/coarse nudges should update `grid_offset_x` and `grid_offset_y`.
- The map image itself remains the canonical pixel coordinate space for fog and tokens.
- Player grid visibility remains a scene-map/player-display choice, independent from whether the GM uses the grid for alignment.

Token asset requirement:

- Future generated monster/NPC tokens should enter as normal image assets and then be selectable for scene-map portrait tokens.
- Token imports should preserve source/category metadata where available, but public serving must stay gated by the active player-display payload.
