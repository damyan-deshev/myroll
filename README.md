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
