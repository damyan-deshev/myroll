# Handoff: Battle Map Asset Integration

Date: 2026-05-02

## What Was Done

The three generated battle-map packs were curated into `myroll_battle_maps_production_v1`.

Raw source packs were not deleted or rewritten:

- `myroll_battle_maps_v1`: core fantasy survival layer.
- `myroll_battle_maps_v2_diverse_spacious`: diverse spacious layer.
- `myroll_battle_maps_v3_weird_fantasy`: weird fantasy layer.

The curated production pack contains 608 accepted WebP maps and 92 rejected source images logged for traceability.

## How The Images Were Produced

Generation happened outside the Myroll app in the local ComfyUI workspace:

- ComfyUI project root: `/Volumes/External/projects/comfyui`
- Model/layout inputs: `/Volumes/External/projects/comfyui/models` and `/Volumes/External/projects/comfyui/inputs/myroll_layouts`
- V1 core generation script: `/Volumes/External/projects/comfyui/pipelines/generate_battlemap_asset_pack.py`
- V2 diverse/spacious generation script: `/Volumes/External/projects/comfyui/pipelines/generate_battlemap_v2_diverse_spacious.py`
- V3 weird fantasy generation script: `/Volumes/External/projects/comfyui/pipelines/generate_battlemap_v3_weird_fantasy.py`
- Curation/export script: `/Volumes/External/projects/comfyui/tools/curate_battle_maps.py`

The useful generation lesson is that prompt-only generation was not enough for broad movement space. V2 and V3 rely on tighter category prompts plus layout-guided img2img/blockout inputs for categories where the model tended to overfill the map or drift into decorative/non-playable images.

## How Curation Worked

1. A source inventory was built from each raw pack's `category.json`.
2. Labelled contact sheets were generated under `curation/contact_sheets/source/`.
3. Images were rejected aggressively when they were not readable top-down battle maps, had too little playable movement space, were too abstract/texture-like, had obvious perspective/3D issues, contained text/UI artifacts, or strongly missed category identity.
4. Accepted images were copied into a production-shaped `assets/battle-maps/fantasy/...` tree and renamed with stable descriptive filenames.
5. `manifest.json`, `taxonomy.json`, per-category `category.json` files, and rejection logs were generated.

The repeatable curation script is `/Volumes/External/projects/comfyui/tools/curate_battle_maps.py`.

## Where Things Are

- Production pack root: `/Volumes/External/projects/comfyui/asset_packs/myroll_battle_maps_production_v1`
- Global manifest: `/Volumes/External/projects/comfyui/asset_packs/myroll_battle_maps_production_v1/manifest.json`
- Taxonomy: `/Volumes/External/projects/comfyui/asset_packs/myroll_battle_maps_production_v1/taxonomy.json`
- Curation decisions: `/Volumes/External/projects/comfyui/asset_packs/myroll_battle_maps_production_v1/curation/curation_decisions.json`
- Reject log: `/Volumes/External/projects/comfyui/asset_packs/myroll_battle_maps_production_v1/curation/rejections.json`
- Accepted review sheets: `/Volumes/External/projects/comfyui/asset_packs/myroll_battle_maps_production_v1/curation/contact_sheets/accepted`
- Rejected review sheets: `/Volumes/External/projects/comfyui/asset_packs/myroll_battle_maps_production_v1/curation/contact_sheets/rejected`

## Integration Slice Starting Point

Start from the existing Myroll asset and map-image pipeline, not from ComfyUI.

Recommended slice:

1. Add a local import command or backend endpoint that reads this pack's `manifest.json`.
2. For every accepted asset, copy `asset.file` into Myroll managed blob storage.
3. Create a normal Myroll image asset with the manifest title, tags, checksum, width, height, and source provenance.
4. Create or attach map metadata from `asset.grid`, keeping the image gridless and overlaying the grid live in the renderer.
5. Store `categoryKey`, `collection`, `categoryLabel`, and `categoryPath` as searchable metadata.
6. Add a GM UI browser for imported battle-map assets after the importer is stable.

Important product rule: do not let the UI guess the tactical scale from image contents. The grid contract is deterministic and comes from the manifest/category metadata.
