# Myroll Battle Maps Production Pack V1

Curated on 2026-05-02 from the generated V1/V2/V3 battle-map packs.

This pack is the production-shaped delivery artifact. The raw generated packs are preserved unchanged for provenance and future recuration.

Source generation scripts:

- V1 core pack: `/Volumes/External/projects/comfyui/pipelines/generate_battlemap_asset_pack.py`
- V2 diverse/spacious pack: `/Volumes/External/projects/comfyui/pipelines/generate_battlemap_v2_diverse_spacious.py`
- V3 weird fantasy pack: `/Volumes/External/projects/comfyui/pipelines/generate_battlemap_v3_weird_fantasy.py`
- Curation/export pack: `/Volumes/External/projects/comfyui/tools/curate_battle_maps.py`

## Contents

- Accepted assets: 608
- Source assets reviewed: 700
- Rejected assets: 92
- Delivery format: WebP
- Images are gridless; tactical grid metadata lives in each category and asset manifest entry.

## Directory Layout

```text
assets/battle-maps/fantasy/<collection>/<group>/<category>/category.json
assets/battle-maps/fantasy/<collection>/<group>/<category>/images/*.webp
manifest.json
taxonomy.json
curation/curation_decisions.json
curation/rejections.json
curation/contact_sheets/
```

## Category Summary

| Category | Production Path | Accepted | Rejected |
|---|---:|---:|---:|
| `abyss.bone_cathedral` | `assets/battle-maps/fantasy/weird/abyss/bone-cathedral` | 12 | 8 |
| `arcane.prismatic_laboratory` | `assets/battle-maps/fantasy/diverse/arcane/prismatic-laboratory` | 14 | 6 |
| `cavern.crystal_blackrock` | `assets/battle-maps/fantasy/diverse/cavern/crystal-blackrock` | 19 | 1 |
| `celestial.starforge_sanctum` | `assets/battle-maps/fantasy/weird/celestial/starforge-sanctum` | 19 | 1 |
| `city.rooftops_fog` | `assets/battle-maps/fantasy/diverse/urban/rooftops-fog` | 10 | 10 |
| `coast.shipwreck_beach` | `assets/battle-maps/fantasy/diverse/coast/shipwreck-beach` | 18 | 2 |
| `dungeon.cave_complex` | `assets/battle-maps/fantasy/core/dungeon/cave-complex` | 38 | 2 |
| `dungeon.stone_complex` | `assets/battle-maps/fantasy/core/dungeon/stone-complex` | 38 | 2 |
| `elemental.storm_glass_citadel` | `assets/battle-maps/fantasy/weird/elemental/storm-glass-citadel` | 20 | 0 |
| `fey.giant_flower_court` | `assets/battle-maps/fantasy/weird/fey/giant-flower-court` | 20 | 0 |
| `forest.fey_clearing` | `assets/battle-maps/fantasy/diverse/fey/fey-clearing` | 14 | 6 |
| `hazard.lava_bridges` | `assets/battle-maps/fantasy/diverse/hazards/lava-bridges` | 20 | 0 |
| `interior.house_floor` | `assets/battle-maps/fantasy/core/interior/house-floor` | 38 | 2 |
| `interior.small_chamber` | `assets/battle-maps/fantasy/core/interior/small-chamber` | 40 | 0 |
| `interior.tavern_night` | `assets/battle-maps/fantasy/diverse/interior/tavern-night` | 15 | 5 |
| `large.arena_lair` | `assets/battle-maps/fantasy/core/large-sites/arena-lair` | 31 | 9 |
| `nature.waterfall_cliff_crossing` | `assets/battle-maps/fantasy/diverse/wilderness/waterfall-cliff-crossing` | 19 | 1 |
| `outdoor.forest_road` | `assets/battle-maps/fantasy/core/wilderness/forest-road` | 35 | 5 |
| `outdoor.river_bridge` | `assets/battle-maps/fantasy/core/wilderness/river-crossings` | 35 | 5 |
| `outdoor.swamp_marsh` | `assets/battle-maps/fantasy/core/wilderness/swamp-marsh` | 39 | 1 |
| `ruins.clean_arena` | `assets/battle-maps/fantasy/diverse/ruins/clean-arena` | 17 | 3 |
| `ruins.temple_shrine` | `assets/battle-maps/fantasy/core/ruins/temple-shrine` | 38 | 2 |
| `settlement.street_square` | `assets/battle-maps/fantasy/core/settlement/streets-squares` | 33 | 7 |
| `underground.toxic_sewer_canals` | `assets/battle-maps/fantasy/diverse/underground/toxic-sewer-canals` | 17 | 3 |
| `void.astral_orrery` | `assets/battle-maps/fantasy/weird/void/astral-orrery` | 9 | 11 |

## Import Rule

Import `manifest.json` into Myroll, copy each `asset.file` into managed asset storage, and create map-image records with `asset.grid`. Do not infer scale from pixels at runtime; the category/asset grid contract is authoritative.

## License

This bundled battle map pack is covered by the repository [ASSET-LICENSE.md](../../../ASSET-LICENSE.md) summary and the full [LICENSE.md](../../../LICENSE.md) terms.

In plain English: free use, modification, redistribution, live play, paid GMing, actual-play use, tutorials, reviews, and community sharing are allowed. Resale as an asset pack, map pack, VTT marketplace module, paid download, paid database, or substantially similar product requires separate written permission from Damyan Deshev.
