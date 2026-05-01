# myroll

Myroll is a local-first GM workspace for tabletop RPG campaigns, built around private preparation, explicit public publishing, and controlled player-facing display surfaces.

It is a product system for running campaigns without mixing private notes, draft scenes, player-visible state, and exported table artifacts into one unsafe surface.

## What It Does

- keeps campaign preparation private until it is explicitly published
- exposes controlled player-facing scene surfaces
- supports maps, tokens, fog, and scene state
- stores local workspace data in SQLite-backed app state
- exports and restores local campaign data for backup or migration
- separates backend API, frontend workspace UI, and player-display transport

## Quick Start

Backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./scripts/start_backend.sh
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Architecture

- `backend/app/` contains the FastAPI app, local persistence, asset handling, fog state, export logic, and workspace defaults.
- `frontend/src/` contains the GM workspace UI, player display transport, typed API client, and tests.
- `docs/` captures product decisions, architecture notes, backlog, and release constraints.
- `scripts/` contains local development and demo helpers.

## Public Repository Boundary

The public repository includes the application code, docs, tests, development scripts, and public demo fixtures. It does not include private campaign data, local SQLite files, exports, backups, generated runtime artifacts, or research material.

---

Maintained by [Damyan Deshev](https://github.com/damyan-deshev) - local-first software, deterministic data paths, retrieval, evaluation, and practical product systems.
