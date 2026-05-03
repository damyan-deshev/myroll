# Myroll Product Design Document

Date: 2026-05-02
Status: Draft 1

## 1. Product Thesis

Myroll is a local-first browser-based GM cockpit for running tabletop RPG sessions without losing control of the table, the notes, the map, or the player-facing presentation.

The core distinction:

```text
GM Workspace:
  complete truth, private state, prep, notes, controls

Player Display:
  curated fiction, revealed state, public presentation only

Scene Runtime:
  the bridge between the two
```

Myroll is not a full virtual tabletop first. It is not trying to replace Foundry, Roll20, Obsidian, OneNote, Syrinscape, and every campaign manager at once. It is a live-session operating surface for one GM who needs to present the right public state to a physical or online table while keeping the real campaign state private and usable.

The product should win by making the live GM flow safer and faster, not by listing more widgets than competitors.

## 2. Primary Users

Primary user:
- A GM running an in-person or hybrid tabletop RPG session.
- Uses a laptop as the private control surface.
- Often has a second monitor, projector, TV table, or shared online screen.
- Uses external notes, usually markdown/Obsidian, OneNote, Notion, PDFs, or loose files.
- Needs fast mid-session access to maps, NPCs, initiative, party state, clues, and handouts.

Secondary user:
- A GM running online play but not wanting a full multi-user VTT.
- Shares only the player-facing browser window in Discord, Zoom, Meet, OBS, or streaming software.

Non-primary early users:
- Players with accounts.
- Fully remote groups needing synchronized per-player visibility.
- Rules automation-heavy groups expecting Foundry-level system support.
- GMs whose main need is deep worldbuilding rather than session execution.

## 3. Positioning

Short version:

> A local-first GM cockpit that keeps your live session, notes, maps, characters, player display, and campaign continuity connected.

Sharper product promise:

> Run the session. Keep the canon.

Anti-positioning:

> Myroll is not a full VTT. Myroll is a GM cockpit and player-presentation layer for running coherent sessions.

## 4. Design Principles

### 4.1 Private By Default

Everything starts private unless explicitly sent to the player display.

This applies to:
- notes;
- maps;
- unrevealed map regions;
- tokens;
- labels;
- NPCs;
- handouts;
- generated content;
- scene notes;
- clocks;
- initiative details;
- custom fields.

The product should use "show this" semantics rather than "hide everything dangerous" semantics. The former is safer.

### 4.2 Player Display Is Not A Mirror

The player display is a dedicated public presentation surface, not a mirror of the GM workspace.

Physical table:

```text
GM laptop -> second monitor / projector / table TV -> fullscreen Player Display
```

Online play:

```text
GM laptop -> Player Display browser window -> share that window/screen
```

The GM sees the complete working state. Players see only the curated public output.

### 4.3 Presentation Boundary, Not Security Boundary

In MVP, `/player` is a non-adversarial presentation surface running on the GM machine.

It is designed for:
- second monitors;
- projectors;
- table TVs;
- screen sharing the player-facing browser window in online play.

It is designed to prevent accidental reveal through rendering, workflow, and projection controls. It is not designed to secure private campaign data from a user who controls the player browser context, browser devtools, local storage, or the same-origin application runtime.

This is acceptable for the MVP because players normally see the physical projection or shared window, not the browser context itself.

If Myroll later supports remote or untrusted player clients opening their own `/player` URL, that requires a different architecture:
- server-mediated sanitized payloads;
- separate storage access;
- separate origin or process boundary;
- real authentication/authorization;
- no private campaign database available to the player client.

Do not market MVP `/player` as a remote player security model.

### 4.4 Five-Second Table Rule

If a live-session action cannot be completed in under five seconds while the GM is distracted, it is not a Run Mode feature yet.

Critical actions must be one-click or hotkey-driven:
- blackout player display;
- preview player display;
- send current map;
- send selected handout;
- reveal area;
- hide area;
- return to previous player display state;
- toggle initiative projection;
- draw a quick NPC;
- promote a quick NPC to campaign state;
- show NPC portrait;
- show text reveal;
- exit reveal/edit mode.

Asset-heavy prep needs the same standard. A GM with hundreds of maps or token images should be able to batch import, categorize, search, attach, and align assets without turning session prep into file management.

Gridless battle maps are a deliberate asset style. Myroll should treat the source image as stable art and give the GM fast live-grid calibration controls, including grid size changes and four-direction nudges, instead of requiring image edits or baked grid pixels.

### 4.4a Quick NPCs Are Run-Mode Material

Quick NPC is a first-class Myroll primitive for the live-session moment where the GM suddenly needs a believable ordinary person.

The product job is:

```text
The party talks to someone unexpected.
The GM draws or filters one usable minor NPC in seconds.
The GM can run that NPC immediately.
If the NPC matters, the GM promotes the seed into editable campaign canon.
```

Quick NPC must not depend on a runtime LLM call. It is backed by a shipped static seed catalog that works offline, loads quickly, and remains deterministic enough for testing and debugging.

A quick NPC seed contains:
- name;
- broad type;
- race/species;
- gender metadata;
- role;
- origin;
- appearance;
- voice;
- mannerism;
- attitude;
- tiny backstory;
- hook or secret;
- portrait tags;
- usage tags.

The seed is source material, not campaign state. Drawing a seed does not make it canon. "Promote to campaign NPC" copies the selected seed into a GM-owned editable NPC/entity record. After promotion, continuity comes from the campaign record, not from the global bundled seed catalog.

Portraits are optional enrichment. The app must work with only the JSON seed catalog. Generated portrait packs map back to seeds through `sourceSeed.id`, may contain multiple variants per seed, and should pass through manual or VLM-assisted curation before an accepted portrait is offered as the default visual.

### 4.5 Safe Reveal Rule

If a player-facing reveal cannot be safely checked or reversed instantly, it is not safe for Run Mode.

Every display-changing action should support:
- visible target status before action;
- preview when needed;
- undo/restore;
- panic blackout.

### 4.6 Scenes Over Loose Widgets

Widgets are useful, but sessions are run in scenes.

The strongest Myroll workflow is not "open a bunch of tools." It is:

```text
Activate Scene:
  load relevant notes
  show map privately
  stage player display intent
  restore fog state
  pin relevant NPCs
  prepare tokens/combat
  prepare sound/timers
  keep hidden facts private
```

Scenes should become the unit of live-session context.

Current implementation makes this private by default: activating a scene focuses the GM runtime, while the player display remains unchanged until the GM explicitly publishes staged display state.

### 4.7 Browser-Based, Local-First

The first version should run in the browser and store campaign data locally. Browser-based is appropriate because:
- a player-facing output is naturally a separate browser window;
- screen sharing a browser window is easy;
- web UI iteration is fast;
- local-first browser storage can support an installable/PWA path;
- future desktop packaging can wrap the same app.

The design should not depend on cloud accounts, servers, or multi-user sync for MVP.

## 5. Competitive Lessons

Important extracted lessons:
- A dense private GM workspace plus clean player-facing display is the right category.
- Modular canvas tools are compelling, but freeform layouts get messy quickly.
- The player-facing map/table-TV use case is strategically stronger than conventional VTT assumptions.
- Manual fog is the correct early feature for in-person and screen-shared sessions.
- Custom typed fields are a powerful way to stay system-agnostic without building every ruleset.
- Broad tool coverage matters less than connected session flow.

Useful tool primitives:
- party tracker;
- combat tracker;
- map display;
- manual fog;
- Quick NPC picker backed by a static seed catalog;
- NPC library;
- bestiary/entity library;
- session notes viewer;
- weather/time utilities;
- soundboard;
- custom layouts;
- multiple campaigns.

Myroll should not become a generic pile of panels. The differentiator should be stronger public/private display semantics and scene orchestration.

## 6. Core Product Model

### 6.1 GM Workspace

The GM workspace is the private operating surface.

It includes:
- docked overview surface;
- focused workbench surfaces;
- optional freeform floating canvas for advanced layouts;
- notes;
- entities;
- maps;
- hidden tokens;
- GM-only labels and annotations;
- display controls;
- scene controls;
- command palette.

The GM workspace may include a player preview pane, but the preview is a verification surface, not the working map.

### 6.2 Player Display

The player display is a separate browser window.

It must be:
- public only;
- fullscreen friendly;
- safe for projector/TV/table display;
- safe for screen sharing;
- control-free by default;
- blackout-capable;
- reconnectable;
- identifiable.

Player Display modes:

```text
blackout
map
image
handout
text
npc_portrait
party
initiative
timer
scene_title
mood_board
intermission
custom_scene
```

Current implementation supports blackout, intermission, scene title, image, map, text snippet, party card, and initiative modes. Party mode is deliberately cards-only: it is built from an explicit roster and public-visible custom fields, not from raw entity records. Initiative mode is deliberately order/current-turn only: it is built from explicit combatant public visibility and curated public status, not from raw combat records.

### 6.3 Scene Runtime

Scene Runtime links private GM context with public output.

A scene should eventually know:
- title;
- linked map;
- default player display mode;
- default handout/image;
- relevant notes;
- relevant NPCs/entities;
- clocks/timers;
- combat setup;
- fog state;
- token state;
- display presets;
- hidden facts;
- revealed facts.

MVP can start smaller:
- title;
- linked map or image;
- fog mask;
- tokens;
- notes links;
- active encounter;
- linked entities;
- linked public snippets;
- staged player display intent.

Current implementation stores scene context separately from public display state. The Scene Context widget can link entities/snippets, select an active encounter, and stage a public display mode. Publishing staged display is a separate explicit action and uses the same public sanitizers as map, snippet, initiative, intermission, scene title, and blackout commands.

## 7. MVP Scope

### 7.1 MVP Core

MVP should prove this vertical slice:

1. GM creates or opens a campaign.
2. GM creates a scene.
3. GM adds a map/image to the scene.
4. GM opens a dedicated Player Display browser window.
5. Player Display starts as blackout.
6. GM sends scene map to Player Display.
7. GM continues seeing the complete unmasked map privately.
8. GM manually reveals/hides player-visible areas.
9. GM previews exactly what players see.
10. GM can instantly blackout or undo the last display state.
11. GM can add tokens with player-visible or GM-only visibility.
12. GM can show a handout/image/text reveal.

Required MVP features:
- campaigns;
- scenes;
- local asset import for images/maps;
- storage persistence check and visible volatile-storage warning;
- manual export/backup path for campaigns;
- dedicated player display window;
- player display status panel;
- blackout;
- preview;
- send current map/image/handout/text;
- GM full map view;
- player-visible manual fog mask;
- basic reveal/hide tools;
- token visibility states;
- canvas workspace with basic draggable widgets;
- local markdown notes viewer/editor;
- command palette;
- simple party tracker with typed custom fields;
- simple combat tracker;
- dice roller.

### 7.2 MVP+

After the MVP vertical slice works:
- scene-linked display presets;
- initiative projection;
- timer/countdown projection;
- NPC portrait projection;
- selected note snippet projection;
- undo stack for player display state;
- saved canvas layouts;
- focus modes;
- time tracker;
- tension clocks;
- soundboard with scene presets.

### 7.3 Explicit Deferrals

Defer:
- dynamic lighting;
- line of sight;
- walls and doors;
- measurement templates;
- full multi-user VTT networking;
- player accounts;
- deep OneNote/Notion sync;
- full calendar editor;
- shop generator;
- marketplace/plugin API;
- complex bestiary imports;
- rule automation for every system.

Manual fog is not a weaker early feature. It is the correct feature for this product category.

## 8. Player Display UX

### 8.1 Always-Visible Status Panel

The GM must always know what players are seeing.

Example:

```text
Player Display
Status: Map
Source: Ship Ambush
Fog: Enabled
Tokens: 4 public, 3 hidden
Window: Display 2 fullscreen
Last changed: 14s ago

[Preview] [Blackout] [Send Current] [Undo]
```

This status panel is a core product feature, not chrome.

### 8.2 Display Window Controls

GM-side controls:
- Open Player Display;
- Reconnect Display;
- Identify Display;
- Fullscreen instructions/state;
- Preview;
- Send Current;
- Blackout;
- Undo;
- Display Settings.

Browser limitations mean the app cannot reliably choose the physical monitor in every environment. MVP should make this explicit:
- open a separate named window;
- let GM drag it to the projector/monitor;
- support fullscreen;
- show an identify screen with clear text.

Dedicated window title:

```text
Myroll - Player Display
```

### 8.3 Staging Flow

For risky content:

```text
Stage -> Preview -> Publish
```

For safe live actions:

```text
Direct Send -> Undo/Blackout available
```

Suggested usage:
- maps and handouts can direct-send if already public/safe;
- note snippets should stage by default;
- generated NPC text should stage by default;
- blackout is always immediate.

### 8.4 Hotkeys

Suggested hotkeys:

```text
Cmd/Ctrl+Shift+B    Blackout player display
Cmd/Ctrl+Shift+P    Preview player display
Cmd/Ctrl+Shift+M    Send current map
Cmd/Ctrl+Shift+H    Send selected handout
Cmd/Ctrl+Shift+R    Reveal mode
Cmd/Ctrl+Shift+I    Toggle initiative projection
Esc                 Exit reveal/edit mode
```

Hotkeys must avoid browser/system conflicts where possible.

## 9. Map And Fog UX

### 9.1 Three GM Map States

GM map widget states:

1. Full GM View
   - Full map visible.
   - All GM layers available.
   - Hidden regions still visible to GM.
   - Fog mask hidden or lightly indicated.

2. Fog Edit View
   - Full map still visible to GM.
   - Player-visible regions are clearly shown.
   - Hidden-to-player regions are tinted, hatched, or dimmed.
   - Reveal/hide tools are active.

3. Player Preview View
   - Embedded preview of the exact player display.
   - Not the working map.
   - Used to verify before/after publishing.

Never force the GM to run from the same restricted map view as the players.

### 9.2 GM Map Widget Controls

Top bar:
- map name;
- scene name;
- GM View / Fog Edit / Player Preview toggle;
- Send to Player;
- Blackout;
- Display Settings.

Tool strip:
- select;
- pan;
- reveal brush;
- hide brush;
- rectangle reveal;
- polygon reveal;
- token tool;
- label tool.

Property panel:
- layer visibility;
- token visibility;
- fog controls;
- grid settings;
- player display scaling;
- scene preset binding.

Status:
- current display target;
- player view mode;
- fog saved/unsaved state;
- zoom;
- optional coordinates.

### 9.3 Player Map Window

Player-side map output:
- no controls by default;
- black background;
- fullscreen friendly;
- correct fit/fill behavior;
- optional scene title;
- optional initiative/current combatant overlay;
- never show GM controls;
- never show hidden layers;
- never show private notes.

## 10. Entities And Tokens

Entities are campaign-scoped private-by-default records with system-agnostic typed custom fields. They can represent PCs, NPCs, creatures, locations, items, handouts, factions, vehicles, or generic campaign objects.

Party tracker uses an explicit PC roster and selected card fields. Publishing party cards to the player display must pass through the same public/private discipline as maps and notes:
- only roster entities with `public_known` visibility;
- only fields marked public-visible in the party tracker;
- no entity notes;
- no tags;
- no private entities;
- no non-roster entities.

Tokens can link to campaign entities, but visibility is token-level.

An entity can exist privately in the campaign database while its token is hidden from players.

Token visibility:

```text
gm_only
player_visible
hidden_until_revealed
```

Label visibility:

```text
gm_only
player_visible
hidden
```

This prevents accidental reveals.

Example:
- NPC exists in database.
- GM sees hidden token on full map.
- Player display does not show it.
- GM reveals the token when appropriate.
- Label can remain hidden even after token reveal.

## 11. Notes And Public Snippets

Notes are private by default.

A note may include:
- private body;
- explicit public snippets;
- linked handouts;
- linked images;
- linked NPCs;
- linked scenes;
- linked map pins;
- display actions.

Useful action:

```text
Select paragraph/image/clue -> Send to Player Display
```

But the entire note should never become public accidentally.

Recommended conceptual model:

```text
Note
  private_body
  public_snippets[]
  linked_entities[]
  linked_scenes[]
  displayable_assets[]
```

MVP can implement public snippets as explicit extracted blocks rather than parsing arbitrary markdown annotations.

Current implementation:
- notes are private SQLite records with optional session, scene, and asset links;
- markdown upload/path import copies content into SQLite and does not keep a live source file dependency;
- public snippets are snapshot records;
- creating a snippet from selected note text copies that selected text into the snippet body immediately;
- later private note edits do not automatically update public snippets;
- player text display renders only sanitized snippet title/body/format through safe markdown with raw HTML disabled.

## 12. GM Surfaces, Canvas, And Layout UX

The GM UI should use focused surfaces for dense live-session work and keep freeform spatial organization as a power-user mode.

Required:
- docked overview on `/gm`;
- focused routes for map, library, actors, combat, and scene context;
- freeform draggable/resizable canvas preserved at `/gm/floating`;
- saved layouts;
- locked layout mode;
- reset to known-good layout;
- search-to-widget;
- persistent Player Display status.

MVP can keep the floating canvas simple, but it should avoid one-way mess:
- provide layout reset;
- prevent accidental widget drag in Run Mode;
- allow one-click focus on relevant scene widgets.

## 13. Key Flows

### 13.1 Open Physical Player Display

1. GM clicks Open Player Display.
2. Browser opens `/player` in named window.
3. Player window shows blackout/intermission.
4. GM drags window to second monitor/projector/TV.
5. GM enters fullscreen.
6. GM clicks Identify Display if needed.
7. GM status panel confirms connected display.

### 13.2 Online Screen Share

1. GM opens `/player`.
2. GM selects Player Display window/screen in Discord/Zoom/Meet/OBS.
3. GM keeps `/gm` private.
4. Player Display receives only sanitized public state.

### 13.3 Send Scene Map

1. GM activates scene.
2. GM sees full map privately.
3. GM clicks Send Scene Map.
4. Player Display shows map with current fog mask.
5. Status panel updates source, mode, fog, timestamp.

### 13.3a Stage Scene Display

1. GM configures scene context.
2. GM links public snippets, relevant entities, and an active encounter.
3. GM activates the scene privately.
4. `/player` stays unchanged.
5. GM chooses staged display mode.
6. GM clicks Publish Staged Display.
7. Player Display updates through the existing public display path.

### 13.4 Manual Reveal

1. GM enters Fog Edit View.
2. GM chooses reveal brush/rectangle/polygon.
3. GM paints or defines reveal area.
4. Player display updates according to publish mode.
5. GM can preview or undo.

MVP decision needed:
- live reveal as brush changes;
- or stage reveal until Publish.

Recommendation:
- live reveal for map fog edits after scene map is already public;
- staged reveal for notes/handouts/text.

### 13.5 Send Handout

1. GM selects handout/image/public snippet.
2. GM stages it.
3. GM previews player output.
4. GM publishes.
5. GM can return to previous map or blackout.

## 14. Success Criteria

MVP is successful if a GM can run a physical table flow without anxiety:
- the player display opens reliably;
- the GM can always tell what players see;
- private notes never leak;
- blackout is instant;
- manual fog is understandable;
- tokens do not accidentally reveal hidden entities;
- maps and handouts can be shown in seconds;
- online screen sharing works by sharing the player window.

## 15. Product Risks

Risk: Becoming a full VTT too early.
Mitigation: No player accounts, no multi-user sync, no dynamic lighting in MVP.

Risk: Becoming GIMP with fog.
Mitigation: Scenes, entities, tokens, handouts, notes snippets, and display state must be connected primitives.

Risk: Canvas chaos.
Mitigation: locked Run Mode, saved layouts, focus modes, reset layout, command palette.

Risk: Accidental reveal.
Mitigation: private by default, display status panel, preview, staged publish, blackout, undo.

Risk: Treating `/player` as a real security boundary.
Mitigation: document MVP `/player` as a non-adversarial presentation surface on the GM machine. Remote/untrusted player clients require a different architecture with server-mediated sanitized payloads or a separate origin/process/storage boundary.

Risk: Browser display limitations.
Mitigation: explicit separate window flow, identify display, reconnect controls, clear fullscreen instructions.

Risk: Browser storage eviction or quota failure.
Mitigation: call `navigator.storage.persisted()` and `navigator.storage.persist()` during campaign create/open, show a prominent volatile-storage warning if persistence is not granted, wrap storage writes for `QuotaExceededError`, surface storage usage, and provide campaign export/backup from the start.

Risk: Live fog publishing blocking the main thread.
Mitigation: broadcast vector fog operations during pointer drag, not full raster mask snapshots. Persist and synchronize a raster snapshot only after pointer-up/debounce. Avoid base64/Data URL fog transport in live paths.

Risk: `BroadcastChannel` failing across storage partitions or browser profiles.
Mitigation: treat `BroadcastChannel` as the same-profile happy path, add `window.postMessage()` for opener-managed player windows, detect heartbeat failure, and show clear reconnect/fallback UI. Manual incognito/private windows are not guaranteed to work without a different pairing transport.
