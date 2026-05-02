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

## Bundled Content Is A First-Class Feature

**Need identified:** a GM tool should not start from an empty asset shelf or force every table to import basic encounter content before the product feels useful.

**Need satisfied:** Myroll ships with a first-party battle map catalog that is immediately available in the GM workspace.

![GM bundled battle map browser showing the shipped map catalog, collection filters, category search, and add-to-campaign action](docs/screenshots/bundled-map-library/gm-bundled-map-browser.png)

The committed pack is `myroll_battle_maps_production_v1`: 608 gridless WebP maps, 25 categories, and 3 collection lanes: `core`, `diverse`, and `weird`. The GM browses it directly in the Map Workbench, filters by collection/category/search, and adds a bundled map to the current campaign with one click.

Built-in maps are copied into campaign asset storage only when added, so exports, restores, public display gating, and player-safe blob serving keep using the same campaign-owned asset flow. Every bundled map also carries an explicit grid contract; the image itself remains gridless, and the GM can tune square size and nudge offsets before saving the map grid.

Available bundled categories:

- `core`: Cave Complex, Stone Dungeon Complex, House Floor, Small Chamber, Arena Lair, Temple Shrine, Settlement Streets And Squares, Forest Road, River Crossings, Swamp Marsh.
- `diverse`: Prismatic Laboratory, Crystal Blackrock Cavern, Shipwreck Beach, Fey Clearing, Lava Bridges, Night Tavern, Clean Arena, Toxic Sewer Canals, Foggy Rooftops, Waterfall Cliff Crossing.
- `weird`: Bone Cathedral, Starforge Sanctum, Storm Glass Citadel, Giant Flower Court, Astral Orrery.

### Visual category gallery

**core / dungeon · Cave Complex**<br>
<img src="docs/screenshots/bundled-map-library/categories/core__dungeon-cave-complex-sample.jpg" width="320" alt="Goblin Cave Main Cavern Stalagmites representative bundled map"><br>
38 maps · 24x18 @ 64px · representative: Goblin Cave Main Cavern Stalagmites<br>
<img src="docs/screenshots/bundled-map-library/categories/core__dungeon-cave-complex-overview.jpg" width="220" alt="Cave Complex bundled map category overview">

**core / dungeon · Stone Dungeon Complex**<br>
<img src="docs/screenshots/bundled-map-library/categories/core__dungeon-stone-complex-sample.jpg" width="320" alt="Crypt Halls Guard Room Sarcophagi representative bundled map"><br>
38 maps · 24x18 @ 64px · representative: Crypt Halls Guard Room Sarcophagi<br>
<img src="docs/screenshots/bundled-map-library/categories/core__dungeon-stone-complex-overview.jpg" width="220" alt="Stone Dungeon Complex bundled map category overview">

**core / interior · House Floor**<br>
<img src="docs/screenshots/bundled-map-library/categories/core__interior-house-floor-sample.jpg" width="320" alt="Abandoned Manor Wing Central Hallway Broken Furniture representative bundled map"><br>
38 maps · 16x12 @ 80px · representative: Abandoned Manor Wing Central Hallway Broken Furniture<br>
<img src="docs/screenshots/bundled-map-library/categories/core__interior-house-floor-overview.jpg" width="220" alt="House Floor bundled map category overview">

**core / interior · Small Chamber**<br>
<img src="docs/screenshots/bundled-map-library/categories/core__interior-small-chamber-sample.jpg" width="320" alt="Ritual Chamber Central Altar Four Pillars representative bundled map"><br>
40 maps · 10x10 @ 128px · representative: Ritual Chamber Central Altar Four Pillars<br>
<img src="docs/screenshots/bundled-map-library/categories/core__interior-small-chamber-overview.jpg" width="220" alt="Small Chamber bundled map category overview">

**core / large-sites · Arena Lair**<br>
<img src="docs/screenshots/bundled-map-library/categories/core__large-arena-lair-sample.jpg" width="320" alt="Ruined Arena Central Boss Area Cover Clusters representative bundled map"><br>
31 maps · 32x24 @ 48px · representative: Ruined Arena Central Boss Area Cover Clusters<br>
<img src="docs/screenshots/bundled-map-library/categories/core__large-arena-lair-overview.jpg" width="220" alt="Arena Lair bundled map category overview">

**core / ruins · Temple Shrine**<br>
<img src="docs/screenshots/bundled-map-library/categories/core__ruins-temple-shrine-sample.jpg" width="320" alt="Forest Shrine Central Altar Mossy Stones representative bundled map"><br>
38 maps · 24x18 @ 64px · representative: Forest Shrine Central Altar Mossy Stones<br>
<img src="docs/screenshots/bundled-map-library/categories/core__ruins-temple-shrine-overview.jpg" width="220" alt="Temple Shrine bundled map category overview">

**core / settlement · Settlement Streets And Squares**<br>
<img src="docs/screenshots/bundled-map-library/categories/core__settlement-street-square-sample.jpg" width="320" alt="Village Market Central Fountain Barrels And Crates representative bundled map"><br>
33 maps · 24x18 @ 64px · representative: Village Market Central Fountain Barrels And Crates<br>
<img src="docs/screenshots/bundled-map-library/categories/core__settlement-street-square-overview.jpg" width="220" alt="Settlement Streets And Squares bundled map category overview">

**core / wilderness · Forest Road**<br>
<img src="docs/screenshots/bundled-map-library/categories/core__outdoor-forest-road-sample.jpg" width="320" alt="Muddy Forest Trail Fallen Wagon Brush Cover representative bundled map"><br>
35 maps · 24x18 @ 64px · representative: Muddy Forest Trail Fallen Wagon Brush Cover<br>
<img src="docs/screenshots/bundled-map-library/categories/core__outdoor-forest-road-overview.jpg" width="220" alt="Forest Road bundled map category overview">

**core / wilderness · River Crossings**<br>
<img src="docs/screenshots/bundled-map-library/categories/core__outdoor-river-bridge-sample.jpg" width="320" alt="Stone Bridge Central Bridge Riverbanks representative bundled map"><br>
35 maps · 24x18 @ 64px · representative: Stone Bridge Central Bridge Riverbanks<br>
<img src="docs/screenshots/bundled-map-library/categories/core__outdoor-river-bridge-overview.jpg" width="220" alt="River Crossings bundled map category overview">

**core / wilderness · Swamp Marsh**<br>
<img src="docs/screenshots/bundled-map-library/categories/core__outdoor-swamp-marsh-sample.jpg" width="320" alt="Witch Marsh Wooden Boardwalk Murky Water representative bundled map"><br>
39 maps · 24x18 @ 64px · representative: Witch Marsh Wooden Boardwalk Murky Water<br>
<img src="docs/screenshots/bundled-map-library/categories/core__outdoor-swamp-marsh-overview.jpg" width="220" alt="Swamp Marsh bundled map category overview">

**diverse / arcane · Prismatic Laboratory**<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__arcane-prismatic-laboratory-sample.jpg" width="320" alt="Prismatic Alchemy Hall Large Central Empty Work Floor Teal Magical Light representative bundled map"><br>
14 maps · 16x12 @ 80px · representative: Prismatic Alchemy Hall Large Central Empty Work Floor Teal Magical Light<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__arcane-prismatic-laboratory-overview.jpg" width="220" alt="Prismatic Laboratory bundled map category overview">

**diverse / cavern · Crystal Blackrock Cavern**<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__cavern-crystal-blackrock-sample.jpg" width="320" alt="Blackrock Crystal Hall Central Open Cavern Floor Cyan Crystals representative bundled map"><br>
19 maps · 24x18 @ 64px · representative: Blackrock Crystal Hall Central Open Cavern Floor Cyan Crystals<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__cavern-crystal-blackrock-overview.jpg" width="220" alt="Crystal Blackrock Cavern bundled map category overview">

**diverse / coast · Shipwreck Beach**<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__coast-shipwreck-beach-sample.jpg" width="320" alt="Tropical Wreck Beach Broken Hull Edge Driftwood Cover representative bundled map"><br>
18 maps · 24x18 @ 64px · representative: Tropical Wreck Beach Broken Hull Edge Driftwood Cover<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__coast-shipwreck-beach-overview.jpg" width="220" alt="Shipwreck Beach bundled map category overview">

**diverse / fey · Fey Clearing**<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__forest-fey-clearing-sample.jpg" width="320" alt="Moonlit Fey Glade Open Mossy Glade Violet Flowers representative bundled map"><br>
14 maps · 24x18 @ 64px · representative: Moonlit Fey Glade Open Mossy Glade Violet Flowers<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__forest-fey-clearing-overview.jpg" width="220" alt="Fey Clearing bundled map category overview">

**diverse / hazards · Lava Bridges**<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__hazard-lava-bridges-sample.jpg" width="320" alt="Black Obsidian Plaza Two Lava Channels Heat Shimmer representative bundled map"><br>
20 maps · 24x18 @ 64px · representative: Black Obsidian Plaza Two Lava Channels Heat Shimmer<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__hazard-lava-bridges-overview.jpg" width="220" alt="Lava Bridges bundled map category overview">

**diverse / interior · Night Tavern**<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__interior-tavern-night-sample.jpg" width="320" alt="Tavern Yard At Night Cleared Central Floor Ale Barrels representative bundled map"><br>
15 maps · 24x18 @ 64px · representative: Tavern Yard At Night Cleared Central Floor Ale Barrels<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__interior-tavern-night-overview.jpg" width="220" alt="Night Tavern bundled map category overview">

**diverse / ruins · Clean Arena**<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__ruins-clean-arena-sample.jpg" width="320" alt="Sand Coliseum Floor Huge Central Sand Floor Sparse Rocks representative bundled map"><br>
17 maps · 32x24 @ 48px · representative: Sand Coliseum Floor Huge Central Sand Floor Sparse Rocks<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__ruins-clean-arena-overview.jpg" width="220" alt="Clean Arena bundled map category overview">

**diverse / underground · Toxic Sewer Canals**<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__underground-toxic-sewer-canals-sample.jpg" width="320" alt="Alchemical Sewer Junction Two Toxic Canals Green Glow representative bundled map"><br>
17 maps · 24x18 @ 64px · representative: Alchemical Sewer Junction Two Toxic Canals Green Glow<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__underground-toxic-sewer-canals-overview.jpg" width="220" alt="Toxic Sewer Canals bundled map category overview">

**diverse / urban · Foggy Rooftops**<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__city-rooftops-fog-sample.jpg" width="320" alt="Slate Roof Terraces Broad Central Roof Deck Low Parapet Cover representative bundled map"><br>
10 maps · 24x18 @ 64px · representative: Slate Roof Terraces Broad Central Roof Deck Low Parapet Cover<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__city-rooftops-fog-overview.jpg" width="220" alt="Foggy Rooftops bundled map category overview">

**diverse / wilderness · Waterfall Cliff Crossing**<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__nature-waterfall-cliff-crossing-sample.jpg" width="320" alt="Cliff Waterfall Trail Waterfall Edge Mist Spray representative bundled map"><br>
19 maps · 24x18 @ 64px · representative: Cliff Waterfall Trail Waterfall Edge Mist Spray<br>
<img src="docs/screenshots/bundled-map-library/categories/diverse__nature-waterfall-cliff-crossing-overview.jpg" width="220" alt="Waterfall Cliff Crossing bundled map category overview">

**weird / abyss · Bone Cathedral**<br>
<img src="docs/screenshots/bundled-map-library/categories/weird__abyss-bone-cathedral-sample.jpg" width="320" alt="Bone Cathedral Nave Long Open Central Aisle Emerald Ghostfire representative bundled map"><br>
12 maps · 24x18 @ 64px · representative: Bone Cathedral Nave Long Open Central Aisle Emerald Ghostfire<br>
<img src="docs/screenshots/bundled-map-library/categories/weird__abyss-bone-cathedral-overview.jpg" width="220" alt="Bone Cathedral bundled map category overview">

**weird / celestial · Starforge Sanctum**<br>
<img src="docs/screenshots/bundled-map-library/categories/weird__celestial-starforge-sanctum-sample.jpg" width="320" alt="Starforge Sanctum Huge Open Radiant Floor White Gold Light representative bundled map"><br>
19 maps · 24x18 @ 64px · representative: Starforge Sanctum Huge Open Radiant Floor White Gold Light<br>
<img src="docs/screenshots/bundled-map-library/categories/weird__celestial-starforge-sanctum-overview.jpg" width="220" alt="Starforge Sanctum bundled map category overview">

**weird / elemental · Storm Glass Citadel**<br>
<img src="docs/screenshots/bundled-map-library/categories/weird__elemental-storm-glass-citadel-sample.jpg" width="320" alt="Storm Glass Plaza Broad Glass Central Floor Cyan Lightning representative bundled map"><br>
20 maps · 24x18 @ 64px · representative: Storm Glass Plaza Broad Glass Central Floor Cyan Lightning<br>
<img src="docs/screenshots/bundled-map-library/categories/weird__elemental-storm-glass-citadel-overview.jpg" width="220" alt="Storm Glass Citadel bundled map category overview">

**weird / fey · Giant Flower Court**<br>
<img src="docs/screenshots/bundled-map-library/categories/weird__fey-giant-flower-court-sample.jpg" width="320" alt="Giant Flower Court Large Central Petal Meadow Pink Petals representative bundled map"><br>
20 maps · 24x18 @ 64px · representative: Giant Flower Court Large Central Petal Meadow Pink Petals<br>
<img src="docs/screenshots/bundled-map-library/categories/weird__fey-giant-flower-court-overview.jpg" width="220" alt="Giant Flower Court bundled map category overview">

**weird / void · Astral Orrery**<br>
<img src="docs/screenshots/bundled-map-library/categories/weird__void-astral-orrery-sample.jpg" width="320" alt="Astral Orrery Bridge Large Central Round Platform Violet Nebula Glow representative bundled map"><br>
9 maps · 24x18 @ 64px · representative: Astral Orrery Bridge Large Central Round Platform Violet Nebula Glow<br>
<img src="docs/screenshots/bundled-map-library/categories/weird__void-astral-orrery-overview.jpg" width="220" alt="Astral Orrery bundled map category overview">

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
