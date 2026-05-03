# Myroll Documentation

Date: 2026-05-04

Start here:

1. `01-product-design.md`
   - Product thesis, user model, MVP scope, player-facing display semantics, core flows, and product risks.

2. `02-high-level-architecture.md`
   - Runtime surfaces, bounded contexts, storage strategy, inter-window communication, rendering architecture, testing strategy, and implementation slices.

3. `03-low-level-architecture.md`
   - TypeScript-style data models, display messages, map/fog/token models, storage schema, command registry, sanitizer rules, and milestone acceptance criteria.

4. `04-llm-product-and-implementation.md`
   - Product definition, lane model, context rules, provider harness, proposal lifecycle, memory inbox, API surface, task catalog, and implementation slices for Myroll Scribe.

Implementation planning:

- `ROADMAP.md`
- `BACKLOG.md`
- `DECISION-REGISTER.md`
- `SECURITY-REVIEW-FOLLOWUP.md`
- `BATTLE-MAP-ASSET-HANDOFF.md`
  - Current curated battle-map production pack location, bundled asset-pack requirement, manifest contract, importer starting point, and gridless-map calibration requirements.

Current implementation pivot:

```text
SQLite:
  durable source of truth

FastAPI:
  local control plane

Filesystem:
  asset blob storage

Browser:
  UI/runtime/cache, not durable campaign storage
```

Backend startup:

```bash
scripts/start_backend.sh
```

The script creates/reuses `.venv`, installs requirements, backs up an existing non-empty SQLite DB, runs Alembic migrations, seeds demo data idempotently, and starts Uvicorn on `127.0.0.1:8000` by default.

Full dev stack:

```bash
scripts/start_dev.sh
```

The dev script starts the backend, waits for `/health`, installs frontend dependencies, and starts Vite on `127.0.0.1:5173` by default. Open `/gm` for the docked GM overview and `/player` for the local public presentation surface.

GM surfaces:

```text
/gm           docked GM overview
/gm/map       focused map/fog/token workbench
/gm/library   assets, notes, and public snippets
/gm/actors    entities and party tracker
/gm/combat    encounters and initiative
/gm/scene     scene orchestration and staged display
/gm/floating  advanced floating widget canvas
```

Demo profile:

```bash
scripts/reset_demo.sh
scripts/start_demo.sh
```

The demo uses isolated data under `data/demo` by default, disables the normal dev seed, and imports the original public `Chronicle of the Lantern Vale` fixture plus generated original demo assets. Local display-name overrides can be placed in ignored `demo/local/name-map.private.json`; the committed `demo/local/name-map.example.json` is public-safe.

Export and restore:

```bash
# Create backups/exports from the GM Storage / Demo widget or API.
scripts/restore_export.sh data/demo/exports/myroll.<timestamp>.export.tar.gz /tmp/myroll-restored-data
```

Exports are `.tar.gz` archives containing a SQLite snapshot, managed assets, and `myroll-export.json`. Restore is offline/script-only and targets a new data dir.

Current implemented slices:

- local backend foundation;
- campaign/session/scene writes and runtime activation;
- persistent GM cockpit workspace;
- local player display service;
- image asset import and public image display;
- scene-linked map display with public `/player` map projection;
- durable manual fog over scene maps with active-only public fog mask serving;
- scene-map tokens with public/private visibility, label filtering, fog reveal rules, and active-only token portrait serving.
- private GM notes, explicit public snippet snapshots, safe markdown preview, and `/player` text display.
- system-agnostic entities, typed custom fields, explicit party roster, and sanitized `/player` party cards.
- manual combat encounters, initiative order, turn state, curated public statuses, and sanitized `/player` initiative projection.
- scene orchestration with private scene activation, linked context, staged public display, and explicit publish.
- local backup/export/restore, Storage / Demo widget, original public demo profile, ignored private local override map, and generated demo asset pack.
- laptop-friendly multi-surface GM shell with the original floating canvas preserved at `/gm/floating`.
- first Myroll Scribe spine: live DM capture, correction events, provider harness, reviewed context preview, session recap draft/save, targetless Memory Inbox accept, aliases, exact recall, and LLM export redaction.

Frontend verification:

```bash
npm --prefix frontend test -- --run
npm --prefix frontend run build
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 MYROLL_E2E_API_BASE=http://127.0.0.1:8000 npm --prefix frontend run test:e2e
```

Playwright screenshots are written to `artifacts/playwright/`, including GM cockpit, player display, image display, map display, fog reveal states, token visibility states, public snippet text reveal states, party card projection states, initiative projection states, and scene context staging/publish states.

Core product invariant:

```text
GM Workspace:
  private, complete, operational

Player Display:
  public, curated, safe to project/share

Scene Runtime:
  connects notes, maps, entities, tools, and staged player-facing output
```

Scene activation is private by default. `/player` changes only after an explicit display command or staged scene display publish.

MVP threat model:

```text
/player is a non-adversarial presentation surface on the GM machine.
It prevents accidental reveal during projection/screen-share.
It is not a remote-player security boundary.
```

Browser infrastructure invariants:

- Browser storage is no longer the source of truth for campaign data. If used later for UI cache/runtime artifacts, persistence status should still be surfaced where relevant.
- Current fog MVP persists and republishes only committed operations. Future live fog reveal should send vector operations during drag; full raster snapshots are only for debounce/pointer-up resync.
- Display communication uses a layered transport: `postMessage` for opener-managed windows, `BroadcastChannel` for same-partition windows, and durable state for reconnect.
