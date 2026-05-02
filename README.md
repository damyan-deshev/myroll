# Myroll

Local-first tabletop RPG control room for GMs, DMs, Keepers, Narrators, and anyone else carrying the plot while pretending this was all planned.

Myroll is a private GM/DM workspace plus a deliberately boring player-facing display. The GM prepares, links, hides, reveals, stages, and panics in one browser tab. The players see only the surface the GM explicitly publishes.

This is not trying to become a social network with dice.

## What this is

**Myroll** is a local-first campaign tool that gives a GM:

- private campaign notes, scene context, actors, encounters, assets, maps, tokens, and fog,
- a separate player display for a projector, table screen, second monitor, Discord stream, Google Meet share, or whatever cable arrangement survived the evening,
- explicit publish controls so "prepared privately" and "shown publicly" remain different states,
- SQLite-backed local data with export/restore paths for backups and migration,
- a FastAPI backend and Vite frontend that run on `127.0.0.1`.

It is built for the common table reality: one person has all the secrets, everyone else should only see the interesting consequences.

## What this is not

- Not a full VTT.
- Not a campaign marketplace.
- Not remote multiplayer infrastructure.
- Not an account system.
- Not a place to put your only copy of a three-year campaign without backups. Please love yourself a little.

Myroll assumes a local, single-user GM setup. That constraint is intentional. It keeps the product small enough to inspect and mean enough to be useful.

## The two-display contract

The important idea is that Myroll has two surfaces.

The **GM/DM workspace** is where the messy truth lives: hidden tokens, private notes, linked entities, scene state, encounter prep, fog controls, and the little buttons that should not be visible to players unless you enjoy narrative bankruptcy.

At this moment in the small pocket of eternity, the GM/DM sees this:

![GM map workbench showing hidden fog controls, token setup, scene context, and private campaign state](docs/screenshots/gm-map-workbench.png)

Meanwhile, the **player display** is a clean projection surface. It can sit on a second monitor, be thrown onto a wall, be pointed at the table, or be shared through Discord/Meet. It shows the map, revealed fog, public labels, visible tokens, and staged scene content. It does not show the GM's private scaffolding.

At the same moment, the players see this:

![Player map projection showing only the revealed map area and public tokens](docs/screenshots/player-map-projection.png)

That separation is the product. The UI is allowed to be practical. The boundary is not allowed to be vague.

## Bundled battle map library

Myroll now ships with a first-party battle map catalog, not an empty asset shelf.

![GM bundled battle map browser showing the shipped map catalog, collection filters, category search, and add-to-campaign action](docs/screenshots/bundled-map-library/gm-bundled-map-browser.png)

The committed pack is `myroll_battle_maps_production_v1`: 608 gridless WebP maps, 25 categories, and 3 collection lanes: `core`, `diverse`, and `weird`. The GM browses it directly in the Map Workbench, filters by collection/category/search, and adds a bundled map to the current campaign with one click.

Built-in maps are copied into campaign asset storage only when added, so exports, restores, public display gating, and player-safe blob serving keep using the same campaign-owned asset flow. Every bundled map also carries an explicit grid contract; the image itself remains gridless, and the GM can tune square size and nudge offsets before saving the map grid.

Available bundled categories:

- `core`: Cave Complex, Stone Dungeon Complex, House Floor, Small Chamber, Arena Lair, Temple Shrine, Settlement Streets And Squares, Forest Road, River Crossings, Swamp Marsh.
- `diverse`: Prismatic Laboratory, Crystal Blackrock Cavern, Shipwreck Beach, Fey Clearing, Lava Bridges, Night Tavern, Clean Arena, Toxic Sewer Canals, Foggy Rooftops, Waterfall Cliff Crossing.
- `weird`: Bone Cathedral, Starforge Sanctum, Storm Glass Citadel, Giant Flower Court, Astral Orrery.

<details>
<summary>Bundled map category gallery</summary>

| Collection | Category | Maps | Grid contract | Overview | Representative map |
|---|---|---:|---|---|---|
| core / dungeon | Cave Complex | 38 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/core__dungeon-cave-complex-overview.jpg" width="180" alt="Cave Complex bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/core__dungeon-cave-complex-sample.jpg" width="180" alt="Goblin Cave Main Cavern Stalagmites representative bundled map"><br>Goblin Cave Main Cavern Stalagmites |
| core / dungeon | Stone Dungeon Complex | 38 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/core__dungeon-stone-complex-overview.jpg" width="180" alt="Stone Dungeon Complex bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/core__dungeon-stone-complex-sample.jpg" width="180" alt="Crypt Halls Guard Room Sarcophagi representative bundled map"><br>Crypt Halls Guard Room Sarcophagi |
| core / interior | House Floor | 38 | 16x12 @ 80px | <img src="docs/screenshots/bundled-map-library/categories/core__interior-house-floor-overview.jpg" width="180" alt="House Floor bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/core__interior-house-floor-sample.jpg" width="180" alt="Abandoned Manor Wing Central Hallway Broken Furniture representative bundled map"><br>Abandoned Manor Wing Central Hallway Broken Furniture |
| core / interior | Small Chamber | 40 | 10x10 @ 128px | <img src="docs/screenshots/bundled-map-library/categories/core__interior-small-chamber-overview.jpg" width="180" alt="Small Chamber bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/core__interior-small-chamber-sample.jpg" width="180" alt="Ritual Chamber Central Altar Four Pillars representative bundled map"><br>Ritual Chamber Central Altar Four Pillars |
| core / large-sites | Arena Lair | 31 | 32x24 @ 48px | <img src="docs/screenshots/bundled-map-library/categories/core__large-arena-lair-overview.jpg" width="180" alt="Arena Lair bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/core__large-arena-lair-sample.jpg" width="180" alt="Ruined Arena Central Boss Area Cover Clusters representative bundled map"><br>Ruined Arena Central Boss Area Cover Clusters |
| core / ruins | Temple Shrine | 38 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/core__ruins-temple-shrine-overview.jpg" width="180" alt="Temple Shrine bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/core__ruins-temple-shrine-sample.jpg" width="180" alt="Forest Shrine Central Altar Mossy Stones representative bundled map"><br>Forest Shrine Central Altar Mossy Stones |
| core / settlement | Settlement Streets And Squares | 33 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/core__settlement-street-square-overview.jpg" width="180" alt="Settlement Streets And Squares bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/core__settlement-street-square-sample.jpg" width="180" alt="Village Market Central Fountain Barrels And Crates representative bundled map"><br>Village Market Central Fountain Barrels And Crates |
| core / wilderness | Forest Road | 35 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/core__outdoor-forest-road-overview.jpg" width="180" alt="Forest Road bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/core__outdoor-forest-road-sample.jpg" width="180" alt="Muddy Forest Trail Fallen Wagon Brush Cover representative bundled map"><br>Muddy Forest Trail Fallen Wagon Brush Cover |
| core / wilderness | River Crossings | 35 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/core__outdoor-river-bridge-overview.jpg" width="180" alt="River Crossings bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/core__outdoor-river-bridge-sample.jpg" width="180" alt="Stone Bridge Central Bridge Riverbanks representative bundled map"><br>Stone Bridge Central Bridge Riverbanks |
| core / wilderness | Swamp Marsh | 39 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/core__outdoor-swamp-marsh-overview.jpg" width="180" alt="Swamp Marsh bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/core__outdoor-swamp-marsh-sample.jpg" width="180" alt="Witch Marsh Wooden Boardwalk Murky Water representative bundled map"><br>Witch Marsh Wooden Boardwalk Murky Water |
| diverse / arcane | Prismatic Laboratory | 14 | 16x12 @ 80px | <img src="docs/screenshots/bundled-map-library/categories/diverse__arcane-prismatic-laboratory-overview.jpg" width="180" alt="Prismatic Laboratory bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/diverse__arcane-prismatic-laboratory-sample.jpg" width="180" alt="Prismatic Alchemy Hall Large Central Empty Work Floor Teal Magical Light representative bundled map"><br>Prismatic Alchemy Hall Large Central Empty Work Floor Teal Magical Light |
| diverse / cavern | Crystal Blackrock Cavern | 19 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/diverse__cavern-crystal-blackrock-overview.jpg" width="180" alt="Crystal Blackrock Cavern bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/diverse__cavern-crystal-blackrock-sample.jpg" width="180" alt="Blackrock Crystal Hall Central Open Cavern Floor Cyan Crystals representative bundled map"><br>Blackrock Crystal Hall Central Open Cavern Floor Cyan Crystals |
| diverse / coast | Shipwreck Beach | 18 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/diverse__coast-shipwreck-beach-overview.jpg" width="180" alt="Shipwreck Beach bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/diverse__coast-shipwreck-beach-sample.jpg" width="180" alt="Tropical Wreck Beach Broken Hull Edge Driftwood Cover representative bundled map"><br>Tropical Wreck Beach Broken Hull Edge Driftwood Cover |
| diverse / fey | Fey Clearing | 14 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/diverse__forest-fey-clearing-overview.jpg" width="180" alt="Fey Clearing bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/diverse__forest-fey-clearing-sample.jpg" width="180" alt="Moonlit Fey Glade Open Mossy Glade Violet Flowers representative bundled map"><br>Moonlit Fey Glade Open Mossy Glade Violet Flowers |
| diverse / hazards | Lava Bridges | 20 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/diverse__hazard-lava-bridges-overview.jpg" width="180" alt="Lava Bridges bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/diverse__hazard-lava-bridges-sample.jpg" width="180" alt="Black Obsidian Plaza Two Lava Channels Heat Shimmer representative bundled map"><br>Black Obsidian Plaza Two Lava Channels Heat Shimmer |
| diverse / interior | Night Tavern | 15 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/diverse__interior-tavern-night-overview.jpg" width="180" alt="Night Tavern bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/diverse__interior-tavern-night-sample.jpg" width="180" alt="Tavern Yard At Night Cleared Central Floor Ale Barrels representative bundled map"><br>Tavern Yard At Night Cleared Central Floor Ale Barrels |
| diverse / ruins | Clean Arena | 17 | 32x24 @ 48px | <img src="docs/screenshots/bundled-map-library/categories/diverse__ruins-clean-arena-overview.jpg" width="180" alt="Clean Arena bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/diverse__ruins-clean-arena-sample.jpg" width="180" alt="Sand Coliseum Floor Huge Central Sand Floor Sparse Rocks representative bundled map"><br>Sand Coliseum Floor Huge Central Sand Floor Sparse Rocks |
| diverse / underground | Toxic Sewer Canals | 17 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/diverse__underground-toxic-sewer-canals-overview.jpg" width="180" alt="Toxic Sewer Canals bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/diverse__underground-toxic-sewer-canals-sample.jpg" width="180" alt="Alchemical Sewer Junction Two Toxic Canals Green Glow representative bundled map"><br>Alchemical Sewer Junction Two Toxic Canals Green Glow |
| diverse / urban | Foggy Rooftops | 10 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/diverse__city-rooftops-fog-overview.jpg" width="180" alt="Foggy Rooftops bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/diverse__city-rooftops-fog-sample.jpg" width="180" alt="Slate Roof Terraces Broad Central Roof Deck Low Parapet Cover representative bundled map"><br>Slate Roof Terraces Broad Central Roof Deck Low Parapet Cover |
| diverse / wilderness | Waterfall Cliff Crossing | 19 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/diverse__nature-waterfall-cliff-crossing-overview.jpg" width="180" alt="Waterfall Cliff Crossing bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/diverse__nature-waterfall-cliff-crossing-sample.jpg" width="180" alt="Cliff Waterfall Trail Waterfall Edge Mist Spray representative bundled map"><br>Cliff Waterfall Trail Waterfall Edge Mist Spray |
| weird / abyss | Bone Cathedral | 12 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/weird__abyss-bone-cathedral-overview.jpg" width="180" alt="Bone Cathedral bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/weird__abyss-bone-cathedral-sample.jpg" width="180" alt="Bone Cathedral Nave Long Open Central Aisle Emerald Ghostfire representative bundled map"><br>Bone Cathedral Nave Long Open Central Aisle Emerald Ghostfire |
| weird / celestial | Starforge Sanctum | 19 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/weird__celestial-starforge-sanctum-overview.jpg" width="180" alt="Starforge Sanctum bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/weird__celestial-starforge-sanctum-sample.jpg" width="180" alt="Starforge Sanctum Huge Open Radiant Floor White Gold Light representative bundled map"><br>Starforge Sanctum Huge Open Radiant Floor White Gold Light |
| weird / elemental | Storm Glass Citadel | 20 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/weird__elemental-storm-glass-citadel-overview.jpg" width="180" alt="Storm Glass Citadel bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/weird__elemental-storm-glass-citadel-sample.jpg" width="180" alt="Storm Glass Plaza Broad Glass Central Floor Cyan Lightning representative bundled map"><br>Storm Glass Plaza Broad Glass Central Floor Cyan Lightning |
| weird / fey | Giant Flower Court | 20 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/weird__fey-giant-flower-court-overview.jpg" width="180" alt="Giant Flower Court bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/weird__fey-giant-flower-court-sample.jpg" width="180" alt="Giant Flower Court Large Central Petal Meadow Pink Petals representative bundled map"><br>Giant Flower Court Large Central Petal Meadow Pink Petals |
| weird / void | Astral Orrery | 9 | 24x18 @ 64px | <img src="docs/screenshots/bundled-map-library/categories/weird__void-astral-orrery-overview.jpg" width="180" alt="Astral Orrery bundled map category overview"> | <img src="docs/screenshots/bundled-map-library/categories/weird__void-astral-orrery-sample.jpg" width="180" alt="Astral Orrery Bridge Large Central Round Platform Violet Nebula Glow representative bundled map"><br>Astral Orrery Bridge Large Central Round Platform Violet Nebula Glow |

</details>

## How it works

1. The backend stores campaign state, assets, fog, runtime display state, backups, and exports locally.
2. The GM works in the private workspace at `/gm`.
3. The player display opens at `/player`.
4. The GM stages or publishes what should be public.
5. The player display refreshes through a small transport envelope and fetches the current player-safe surface from the API.

The boring version: Python, SQLite, FastAPI, React, Vite.

The useful version: the GM gets a cockpit; the players get a window.

## Quick start

Run the full development stack:

```bash
./scripts/start_dev.sh
```

Then open:

- GM workspace: `http://127.0.0.1:5173/gm`
- player display: `http://127.0.0.1:5173/player`
- backend health: `http://127.0.0.1:8000/health`

The scripts create and use `.venv`, install Python dependencies, run migrations, seed local development data, and start Vite. Node dependencies are installed under `frontend/`.

## Demo campaign

For a resettable demo with actual maps, portraits, notes, tokens, fog, scenes, and a player display state that looks like someone is already in trouble:

```bash
MYROLL_DEMO_RESET=1 ./scripts/start_demo.sh
```

Use the same URLs:

- `http://127.0.0.1:5173/gm`
- `http://127.0.0.1:5173/player`

Demo data lives under `data/demo/` by default and is ignored by git. Break it freely. That is its job.

## Development commands

Backend only:

```bash
./scripts/start_backend.sh
```

Frontend only:

```bash
npm --prefix frontend run dev
```

Backend tests:

```bash
.venv/bin/python -m pytest backend/tests
```

Frontend tests:

```bash
npm --prefix frontend test
```

Frontend build:

```bash
npm --prefix frontend run build
```

## Project map

- `backend/app/` - FastAPI app, SQLite persistence, migrations, asset handling, fog state, backups, exports, and demo seed logic.
- `frontend/src/` - GM workspace, player display, API client, transport envelope, styles, and tests.
- `docs/` - product decisions, architecture notes, roadmap, backlog, and review follow-up.
- `docs/screenshots/` - public README screenshots generated from the demo stack.
- `scripts/` - local development, demo reset, startup, and restore helpers.

## Public repository boundary

The public repository includes application code, tests, documentation, development scripts, and public demo fixtures.

It does not include local databases, private campaign data, exports, backups, generated runtime artifacts, editor state, dependency folders, or archived private working material.

If a file is needed to run the product, it belongs here. If a file only explains how the sausage was made, it probably does not.

## Design bias

Myroll favors:

- explicit publishing over accidental visibility,
- local files over mandatory cloud accounts,
- inspectable state over clever magic,
- boring backups over heroic recovery stories,
- practical table flow over maximal feature checklists.

There are enough dramatic reveals in tabletop RPGs already. The software does not need to provide extra ones.

---

Maintained by [Damyan Deshev](https://github.com/damyan-deshev) - local-first software, deterministic data paths, retrieval, evaluation, and practical product systems.
