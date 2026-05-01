# Third-Party Code Review Follow-Up

Date: 2026-05-01
Status: implementation follow-up, partially fixed

This document captures the parts of the external review that still matter after checking the actual code. It is intentionally not a rewrite of the review's severity order. The useful unit here is "what should we fix next, and why?".

## Current Status

Fixed:

- Slice 1: local API request boundary now has a trusted Host guard, exact local CORS origins, and an unsafe-method Origin / Fetch Metadata guard.
- Slice 2: public `import-path` endpoints and UI/client controls were removed; uploads remain the supported import path.
- Slice 4: player-display transport now accepts only the exact notification envelope keys.
- Slice 5: asset writes use unconditional atomic replace and reject symlink storage directories.

Still open:

- Spike 3: extract the player-display rendering boundary from `frontend/src/App.tsx`. This remains an architecture slice, not a confirmed exploit.

## Calibration

Myroll is a local-first, single-user GM tool. The relevant adversary is not another account in the product. The relevant risks are:

- a random browser tab reaching the localhost API while Myroll is running;
- DNS rebinding or bad Host handling turning a local service into a same-origin target;
- malicious or overly broad local file import workflows;
- accidental GM-to-player private-state leakage;
- bugs that corrupt the only local campaign database/assets.

I used this validation rubric:

1. Is there a realistic source, control, sink, and impact for this product?
2. Does the issue survive the browser and FastAPI mechanics, not just the bug-class name?
3. Is there existing code that narrows or defeats the claim?
4. Would the fix reduce meaningful risk without changing the product model?
5. Can it be sliced into a small, testable change?

## Work Order

### Slice 1: Local API request boundary

Disposition: fixed, with corrected exploit shape.

The review is right that the FastAPI app has no Host, Origin, or CORS middleware. `backend/app/factory.py` constructs the app directly and includes routes without request-boundary middleware. The local backend also defaults to `127.0.0.1:8000`.

What I verified:

- `Host: evil.test` is currently accepted by `/health`.
- A cross-origin simple form-style POST to `/api/player-display/blackout` is accepted by the server.
- A form-style POST to JSON-only `notes/import-path` is rejected with 422.
- A browser preflight for JSON `notes/import-path` gets 405, so ordinary cross-origin `fetch(..., { method: "POST", headers: { "Content-Type": "application/json" } })` should not reach the JSON endpoint.

The original review overstates the normal-browser CSRF case: cross-origin `DELETE` and JSON POST are preflighted and should be blocked by lack of CORS. The real issue is still meaningful:

- simple POST endpoints with no body can be triggered cross-site;
- future simple/form endpoints would be exposed unless we add a guard now;
- no Host guard leaves DNS rebinding as the serious path to same-origin reads/writes.

Proposed fix:

- Add `TrustedHostMiddleware` for `127.0.0.1`, `localhost`, and the configured local bind host where appropriate.
- Add an unsafe-method guard that rejects cross-site `Origin` / `Sec-Fetch-Site` on `POST`, `PATCH`, `DELETE`, and `PUT`.
- Add CORS only if we intentionally support direct Vite-to-API calls without the Vite proxy; keep allowed origins exact, not wildcard.
- Keep CLI/TestClient compatibility explicit: requests with no browser headers may be allowed.

Acceptance criteria:

- A request with `Host: evil.test` returns 400/403 before route handling.
- `Origin: https://evil.test` plus a simple POST to `/api/player-display/blackout` is rejected.
- Same-origin/proxy development flow still works at `/gm` and `/player`.
- Backend tests cover allowed local host, rejected host, rejected cross-site origin, and no-regression for local TestClient calls.

Implementation:

- `backend/app/factory.py` adds `TrustedHostMiddleware`, exact local CORS origins, and an unsafe-method browser-origin guard.
- `backend/app/settings.py` exposes `MYROLL_ALLOWED_HOSTS` and `MYROLL_ALLOWED_ORIGINS` overrides while keeping local defaults.
- `backend/tests/test_api.py` covers allowed local requests, bad Host rejection, cross-site POST rejection, and no-browser-header local calls.

Primary files:

- `backend/app/factory.py`
- `backend/app/settings.py`
- `backend/tests/test_api.py`

### Slice 2: Remove or hard-bound `import-path`

Disposition: fixed by removing public path import, not by allowlisting.

The API currently accepts local filesystem paths from HTTP payloads:

- `POST /api/campaigns/{campaign_id}/assets/import-path`
- `POST /api/campaigns/{campaign_id}/notes/import-path`

The claim needs narrowing:

- notes import only accepts `.md`, `.markdown`, or `.txt`, must decode as UTF-8, and is capped at 2 MB;
- asset import only persists files that pass image validation;
- the review's `/Users/gm/.ssh/id_rsa` example would not pass the note suffix gate and would not pass image validation.

The essence is still bad for this app: a browser-reachable local API should not accept an arbitrary absolute path string and read it. `Path.exists()`, `Path.is_file()`, `Path.read_bytes()`, and `Path.resolve().open()` all follow symlinks. The frontend also exposes "Import path" fields, so this is a real product path, not just a hidden test helper.

Proposed fix, preferred:

- Remove `import-path` endpoints from the public app and UI.
- Keep `import-upload` only; the OS file picker is the correct user-consent boundary.
- If scripts need fixture imports, use an internal CLI/helper path outside the browser API.

Alternative fix if path import is kept:

- Gate it behind an explicit local-dev setting disabled by default.
- Restrict source paths to configured import roots.
- Reject symlinks and paths outside the resolved import root.
- Do not store absolute source paths.

Acceptance criteria:

- `/gm` no longer exposes "Import path" controls.
- Public API no longer accepts arbitrary `source_path` by default.
- Upload import behavior remains intact for images and notes.
- Tests are updated to prove path import is gone or guarded, and upload import still works.

Implementation:

- Removed public `assets/import-path` and `notes/import-path` route handlers and request models.
- Removed frontend API client methods and `/gm` controls for path import.
- Kept multipart upload imports for assets and notes.
- Tests assert the former path endpoints return 404 and upload imports still work.

Primary files:

- `backend/app/api/routes.py`
- `backend/app/asset_store.py`
- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `backend/tests/test_api.py`
- `frontend/src/api.test.ts`
- `frontend/src/App.test.tsx`

### Spike 3: Player-display boundary extraction

Disposition: still open as an architecture spike, not as an immediate exploit.

`frontend/src/App.tsx` is 4,512 lines and contains the GM workspace, asset library, notes, maps/fog/tokens, party tracker, combat tracker, transport handling, and `/player` rendering path. That is not automatically a security bug, but it does make the most important product boundary too easy to weaken accidentally.

The useful concern is narrow: "what the player sees" should have an explicit typed module boundary. It should not rely on a giant shared file and ad hoc inline payload parsing.

Proposed spike:

- Define a `frontend/src/player-display/` module boundary.
- Move `PlayerDisplayApp`, `PlayerDisplaySurface`, player payload parsers, portraits, frame, and transport hookup out of `App.tsx`.
- Keep the public input type as `PlayerDisplayState`, but parse/normalize mode-specific payloads into narrow render props before rendering.
- Add tests that render each player-display mode from sanitized public payloads only.

Acceptance criteria:

- `/player` rendering is isolated from GM widgets at the module level.
- The GM app can only notify the player surface to refetch; it does not pass display content through the transport channel.
- Tests assert that the player display fetch path remains `GET /api/player-display` plus active public blobs/masks only.
- No broad App.tsx rewrite is required in this spike; extract only the player-display boundary first.

Primary files:

- `frontend/src/App.tsx`
- `frontend/src/playerDisplayTransport.ts`
- `frontend/src/types.ts`
- `frontend/src/App.test.tsx`
- `frontend/e2e/gm.spec.ts`

### Slice 4: Rename and strict-validate display transport envelopes

Disposition: fixed as defense-in-depth.

The review is correct that `FORBIDDEN_CONTENT_KEYS` is misleading. The transport currently carries heartbeat and "display state changed" notifications. Actual display content is fetched by `/player` through `GET /api/player-display`.

So this is not a current content-sanitization bypass. The problem is false confidence: the code and test name imply that content-bearing messages are being sanitized, when the real invariant is "transport messages must never carry content."

Proposed fix:

- Replace `FORBIDDEN_CONTENT_KEYS` with a strict envelope parser that whitelists exactly the allowed keys.
- Rename tests to describe envelope validation, not content sanitization.
- Document that any future content-bearing player message must go through the backend public display serializer, not this transport.

Acceptance criteria:

- Unknown keys are rejected because the envelope schema is exact.
- The code no longer uses "content sanitization" naming for transport messages.
- Existing heartbeat and display-state-changed behavior remains unchanged.

Implementation:

- `frontend/src/playerDisplayTransport.ts` now validates an exact six-key envelope.
- Unknown keys, including content-shaped keys such as `payload`, `asset_url`, and `mask_url`, are rejected because they are outside the envelope schema.
- Tests were renamed around envelope validation rather than content sanitization.

Primary files:

- `frontend/src/playerDisplayTransport.ts`
- `frontend/src/playerDisplayTransport.test.ts`

### Slice 5: Asset-store atomic write and symlink hardening

Disposition: fixed as low-cost hardening.

The external review's data-corruption argument is overstated. Asset filenames are content-addressed by checksum, and if two uploads have the same checksum they are the same bytes. The app also does not appear to depend on blob mtime/permissions for asset identity.

The real hardening point is still valid:

- `final_path.parent.mkdir(parents=True, exist_ok=True)` accepts an existing symlink-to-directory;
- `os.replace(temp_path, final_path)` would then write through that symlink;
- the exists-check before replace is unnecessary and non-atomic.

This is mostly local-filesystem hardening. It becomes more relevant if packaging, restore flows, or external automation ever touch `data/assets`.

Proposed fix:

- Ensure `settings.asset_dir` and the checksum shard directory are resolved under the intended asset root.
- Reject symlink parent directories before writing.
- Drop the `exists()` branch and use atomic `os.replace` unconditionally after validation.
- Keep content-addressing semantics unchanged.

Acceptance criteria:

- Uploading the same image twice still creates valid DB rows pointing at the content-addressed blob.
- A symlink shard directory under `asset_dir` is rejected.
- Asset writes cannot escape `settings.asset_dir`.

Implementation:

- `backend/app/asset_store.py` prepares and validates the asset root, temp directory, and checksum shard directory before writing.
- Symlink storage directories are rejected.
- The pre-write `exists()` branch was removed; validated uploads use unconditional `os.replace`.
- Backend tests cover duplicate content-addressed uploads and symlink shard rejection.

Primary files:

- `backend/app/asset_store.py`
- `backend/tests/test_api.py` or a focused asset-store test

## Not Carried Forward As Written

- "Cross-origin JS can DELETE a campaign through normal CORS failure" is not supported as written. DELETE and JSON POST are preflighted. Keep the Host/Origin fix anyway because simple POST and DNS rebinding are enough reason.
- "Import-path persists arbitrary filesystem content" is too broad. Notes are suffix/UTF-8/size gated; assets are image-validated. The path-reading API shape is still wrong.
- "Transport sanitization prevents content leaks" is not true today because the transport is notification-only. Fix naming/schema to prevent future misuse.
- "Asset upload race corrupts data" is too strong for current content-addressed blobs. The symlink and atomicity cleanup is still worth doing.

## Remaining Sequence

1. Extract the player-display rendering boundary from `frontend/src/App.tsx`.
2. Keep the transport channel notification-only; any future content-bearing player display feature should go through the backend public display serializer.
3. After the extraction, add focused tests around each player-display mode using sanitized public payloads only.
