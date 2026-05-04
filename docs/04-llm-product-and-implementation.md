# Myroll LLM Product And Implementation Spec

Date: 2026-05-04
Status: First Scribe spine, branch proposal/planning marker slice, player-safe recap gate, and proposal canonization bridge implemented

This document turns the LLM direction into implementable product slices. It assumes the current Myroll architecture:

```text
SQLite = durable source of truth
FastAPI = local control plane
Filesystem = managed asset blobs
Browser = GM workspace and player display
```

The LLM layer must preserve the core product boundary:

```text
GM Workspace:
  private, complete, operational

Player Display:
  public, curated, safe to project/share

LLM:
  private GM assistant, never durable truth by itself
```

## 0. Implementation Status

Current shipped status:

- `[shipped]` PRE-LLM live capture: campaign/session-scoped `live_dm_note` transcript events, backend timestamps, per-session `orderIndex`, correction events, and compact `/gm` capture surface.
- `[shipped]` LLM-0a provider harness: backend-owned OpenAI-compatible non-streaming provider calls, provider profiles, conformance probe, run history, cancellation state, and no raw key exposure to the browser.
- `[shipped]` LLM-0b context preview: persisted context packages, canonical source hash, explicit review action, rendered prompt/source inspection, and stale-preview blocking.
- `[shipped]` LLM-0c session recap draft: reviewed context -> provider run -> structured `SessionRecapBundle`, one schema-repair attempt, backend validation of memory-candidate evidence refs against the reviewed context package, validation failures, editable reviewed recap save, and export redaction for prompt/response payloads.
- `[shipped]` LLM-0d memory inbox: targetless memory candidates, `Accept into Memory` as one atomic apply transaction, idempotent repeated accept, and rejected/weak candidates excluded from accepted memory.
- `[shipped]` LLM-1 first recall spine: campaign memory entries, reviewed session recaps, live capture search indexing, manual aliases, query expansion, and policy-filtered recall results. This first spine uses basic projection-table search, not the full FTS5 target described later in this document.
- `[shipped]` LLM-2 branch proposals and planning markers: campaign/session/scene branch context preview, structured branch runs, proposal sets/options, degraded normalization warnings, proposal card actions, one-marker-per-source-option adoption, active planning marker context eligibility, and `/gm` proposal cockpit inspection.
- `[shipped]` LLM-3 player-safe recap/snippet drafting and leak warning gate: public-safe source curation, reviewed public-safe context packages, deterministic warning scan, player-safe structured draft runs, LLM-sourced `PublicSnippet` creation with scan/ack gating, dedicated player-display snippet serialization, publication tracking, and default export redaction of LLM snippet provenance/warnings.
- `[shipped]` LLM-4 proposal canonization bridge: `session.build_recap` may link a memory candidate to one active planning marker when later played evidence confirms it; `Accept into Memory` atomically creates accepted memory, canonizes the marker/source option, and keeps future canon context carried by the memory entry rather than marker/proposal text.
- `[shipped]` Real-provider Scribe journey verification: opt-in Playwright runners exercise a LAN/OpenAI-compatible model through live capture, branch proposals, planning-marker adoption, played-event capture, session recap, memory accept, recall, and `/player` payload boundary checks. Reports are written under ignored `artifacts/e2e/*` paths for human review.
- `[deferred]` vectors, streaming, tool calls, audio recording/transcription, autonomous entity mutation, and player-facing LLM flows.

Current implementation entry points are intentionally small:

- `/gm` contains the compact Scribe live surface plus expandable GM-private inspection/review controls.
- Dedicated backend routes live under `/api/*/scribe/*` and `/api/*/llm/*`.
- `/player` remains disconnected from all Scribe/LLM APIs.

Known limitations in the shipped first spine:

- cancellation is a durable soft cancel: Myroll marks the run canceled and discards late provider responses, but the blocking non-streaming upstream HTTP request may continue until the provider returns or times out;
- recall currently scans a `scribe_search_index` projection table over live captures, reviewed recaps, and accepted memory entries; it is not yet SQLite FTS5 and does not yet index every notes/entities/public-snippet source promised by the full recall slice;
- the search projection has upsert behavior for current Scribe writes, but no source-level garbage collection/rebuild command beyond campaign-level cascade cleanup;
- branch proposal canonization is narrow: one active marker can be created per source proposal option, proposed deltas are inspection-only, accepted memory may canonize a linked marker after played evidence exists, but there is still no direct proposal-body canonization/apply endpoint, entity patching, or manual relinking UI;
- public-safe curation is conservative and manual: `public_safe=true` means eligible for public-safe context, not guaranteed safe to publish; deterministic warnings are not proof of safety; manual snippets are GM-approved public artifacts by convention, not Scribe-verified safe text; raw private recaps, private memory, private notes, planning markers, proposal bodies, live captures, and run history are excluded from player-safe context.
- timestamps are now rendered as first-class transcript metadata in recap/branch context, but the human-visible capture surface still benefits from GM-authored campaign-clock wording when the table chronology differs from wall-clock capture time.

## 1. Product Definition

Product name for the capability:

```text
Myroll Scribe
```

Myroll Scribe is a GM-facing campaign scribe and prep co-pilot.

It is not:
- an autonomous AI dungeon master;
- a rules engine;
- a player-facing chatbot;
- a hidden mutator of campaign state;
- a replacement for first-class campaign objects.

It is:
- a private assistant for prep, recall, drafting, and continuity;
- a way to turn played events into clean campaign memory;
- a way to ask for possible directions without polluting canon;
- a drafting surface for notes, recaps, NPC updates, clues, factions, quests, and scene complications;
- a context builder over existing campaign state.

Core promise:

```text
Remember what happened.
Recall what matters.
Prepare what might happen.
Canonize only what the GM accepts.
```

Feature review rule:

```text
The LLM may draft.
The GM operates.
The product preserves table authority.
```

Every LLM feature should preserve GM agency and explicit publish/apply boundaries. If it silently operates the campaign, it does not belong in Myroll Scribe.

Primary user assumption:
- the GM has either a local model or access to an OpenAI-compatible API endpoint;
- first implementation should target OpenAI-compatible chat completion APIs;
- local providers such as KoboldCpp, LM Studio, Ollama-compatible proxies, vLLM, or OpenRouter-style endpoints are acceptable when they expose a compatible endpoint.

## 2. Product Invariants

These are non-negotiable implementation rules.

### 2.1 LLM Output Is Not Memory

```text
LLM outputs are drafts.
GM decisions are memory.
Played events are canon.
```

The model may propose, summarize, rewrite, extract, and prefill. It may not silently create or update durable campaign truth.

### 2.2 Canon And Planning Are Different

Do not collapse "this might happen" into "this happened".

The LLM layer has three lanes:

```text
Canon Lane:
  durable campaign truth

Prep / Planning Lane:
  scoped GM intent for current/next session/scene

Draft / Proposal Lane:
  raw model output and brainstorm history
```

Only the first two are eligible for normal future context, and the planning lane must be clearly labeled as planning context.

### 2.3 Raw Proposals Are Not Re-Injected

Raw proposal branches, rejected options, and speculative drafts are excluded from normal context packages.

Allowed context:
- canon facts;
- approved memory;
- active planning markers;
- accepted memory entries that came from played evidence confirming a planning marker;
- explicit evidence snippets from exact recall.

Excluded by default:
- unselected proposal options;
- rejected proposal options;
- raw brainstorm bodies;
- expired session prep;
- saved-for-later ideas unless the selected task explicitly asks for idea-bank context.

### 2.4 The Model Does Not Publish

`/player` never talks to LLM endpoints and never receives prompt context, raw responses, private notes, proposal bodies, or generated public content.

Generated public text, images, snippets, maps, party cards, and display actions remain drafts until the GM explicitly applies and publishes through existing player-display APIs.

### 2.5 Context Is Previewable

Every LLM run must have a context preview that shows the GM what will be sent.

The preview must include:
- task/template ID;
- provider/model;
- visibility mode;
- source records included;
- source records excluded;
- approximate token estimate;
- rendered prompt payload without API keys.

The trust invariant is preview-before-run, not "force the GM to read a full drawer every time." The UI may use a fast trusted preview mode when:
- the GM has already reviewed a full preview for the same task/source policy;
- the stored `sourceRefHash` still matches;
- the included source classes have not changed.

Fast trusted preview shows a compact summary such as `Context unchanged since last reviewed preview: current scene, active NPC, 3 memory entries, 2 planning markers`, with `Run` and `Expand preview` actions. Any stale hash or changed source class forces full preview again.

### 2.6 Local-First Provider Configuration

API keys are not campaign data.

First implementation should prefer:
- environment variables such as `MYROLL_LLM_API_KEY`;
- provider profiles that reference key source names, not raw key values;
- no API keys in exports, demo data, screenshots, logs, `/health`, `/api/meta`, or frontend responses.

Environment variable key sources are read by the backend process. If the GM changes `MYROLL_LLM_API_KEY`, they should restart the backend before expecting the new value to be used.

### 2.7 Provider Calls Are Backend-Only

The browser never calls an LLM provider directly.

Required trust path:

```text
frontend
  -> FastAPI /api/llm/*
  -> backend provider client
  -> configured provider endpoint
```

Forbidden trust path:

```text
frontend
  -> provider endpoint
```

Rules:
- the API key never leaves the FastAPI process;
- provider base URLs and key source names may be visible in GM-private configuration UI, but raw keys are never sent to the browser;
- all provider HTTP calls are made by backend code;
- frontend code may initiate a run, poll a run, cancel a run, and render persisted run output, but it must not construct provider HTTP requests.

### 2.8 V1 Product Loop Non-Goals

V1 proves the Scribe loop, not every possible assistant workflow.

V1 does not:
- record audio;
- transcribe audio;
- run live summarization during play;
- auto-update entities from transcripts;
- auto-publish public recaps;
- require vector search;
- require streaming responses;
- require tool calls;
- require user-auth/account infrastructure.

### 2.9 Inspection Mode

Every LLM-backed workflow must expose enough intermediate state for the GM/developer to inspect what happened before trusting the result.

Inspection surfaces may include:
- provider request metadata;
- context package source list;
- rendered prompt preview;
- structured parse result;
- parse/repair errors;
- evidence projection;
- memory candidate validation failures;
- public-safety warnings.

Inspection surfaces are GM-private and never available to `/player`.

The shipped `/gm` Scribe panel implements this as expandable inspection areas that show context source refs, source hash/classes, rendered prompt when retained, run status, parse failure details, normalized output JSON, proposal normalization warnings, planning marker provenance, public-safe source curation, and deterministic leak warning results.

### 2.10 Correction Loops

Correction is a first-class review action, not an edit-in-place illusion.

V1 correction loops:
- live capture correction creates a correction transcript event;
- recap draft correction edits the reviewed recap before saving;
- memory candidate correction edits the candidate body before accepting into memory;
- malformed structured output correction uses one schema-repair child run;
- public-safe warning correction edits the draft before `PublicSnippet` creation.

Corrections must preserve original source evidence and audit metadata where relevant.

The shipped loop implements transcript correction, recap draft editing, candidate editing API, one schema-repair child run, and public-safe draft edit/rescan/ack before `PublicSnippet` creation.

### 2.11 No Silent Fallbacks

If a provider cannot satisfy a task requirement, Myroll must fail visibly instead of silently changing task behavior.

Forbidden:
- silently switching provider;
- silently downgrading structured output to prose;
- silently dropping evidence from recap;
- silently using prior recap when source evidence does not fit;
- silently accepting malformed partial output.

Allowed:
- explicit GM-visible retry;
- explicit schema repair child run;
- explicit map-reduce mode with visible budget explanation;
- explicit fallback task selected by the GM.

The shipped recap and branch paths block unverified/low-conformance providers, require reviewed context, reject stale previews, reject malformed structured output after one repair attempt, and never partially apply failed output.

## 3. State Lanes

### 3.1 Canon Lane

Canon Lane is durable campaign truth.

Examples:
- session summaries accepted by the GM;
- NPC facts and relationship changes;
- location/faction state changes;
- party decisions;
- discovered clues;
- resolved and unresolved threads;
- public-known recap items;
- canonized selected proposal outcomes.

Canon Lane is normally eligible for context and retrieval.

Canon writes happen only through explicit GM actions:
- approve memory candidate;
- edit and approve memory candidate;
- create/update entity;
- save private note;
- save session recap;
- canonize selected proposal;
- link fact to scene/session/entity.

### 3.2 Prep / Planning Lane

Prep / Planning Lane is temporary GM working state.

Examples:
- "For tonight, develop the encounter around Direction 2.";
- "Captain Varos should probably try to recruit the party, not attack.";
- "Push toward moral dilemma if the players engage.";
- "The mine scene should expose the missing ledger clue.";
- "Use this NPC voice/mannerism until changed."

Planning is context-eligible only when:
- status is active;
- scope matches the current campaign/session/scene/entity/task;
- the marker has not expired;
- it is rendered as planning context, not fact.

Planning markers must never state unplayed outcomes as if they happened.

Bad planning marker:

```text
Captain Varos betrayed the party and handed them to the cult.
```

Good planning marker:

```text
GM selected the "hidden cult pressure" direction for Captain Varos. Future suggestions may develop Varos as conflicted and cult-compromised, but must not assume betrayal has occurred unless canonized later.
```

### 3.3 Draft / Proposal Lane

Draft / Proposal Lane stores model outputs and GM brainstorm history.

Examples:
- 5 possible scene directions;
- rejected NPC secrets;
- unused clue variants;
- draft prose;
- raw LLM response text;
- saved-for-later ideas;
- public snippet drafts not yet created as `PublicSnippet`;
- entity patch drafts not yet applied.

Draft/proposal state is useful for UI, audit, and explicit recall, but it is not campaign truth.

Default context builder rule:

```text
Context = Canon Lane + active Planning Markers + current selected objects + explicit recall evidence.
Never include raw proposals unless the task explicitly asks for proposal history.
```

## 4. Core Workflows

### 4.1 Branch Proposals During Play

User story:

```text
The party meets a new or existing NPC.
The GM wants several plausible directions.
The GM chooses one direction and plays from there.
Only played/accepted facts become canon.
```

Flow:

```text
GM selects scene/NPC/current notes
  -> clicks Develop Encounter
  -> context preview
  -> run LLM task scene.branch_directions
  -> receive 3-5 proposal cards
  -> choose Adopt Direction 2
  -> create active planning marker
  -> exclude all raw proposal cards from future normal context
  -> after play, GM opens Canonize Scene
  -> model extracts canon candidates from GM notes/transcript
  -> GM approves/edits/rejects
  -> approved facts enter Canon Lane
```

Important:
- adopting a direction does not mean events happened;
- adopting a direction can influence future suggestions as planning context;
- canonization happens after the GM says what was played or approves extracted facts.

### 4.2 Prep Next Session

User story:

```text
After previous sessions, the GM wants help preparing the next one from canon notes and active unresolved threads.
```

Flow:

```text
GM selects campaign/session
  -> task session.prep_next
  -> context includes canon memory, unresolved threads, current party state, recent sessions, active planning markers
  -> output is a prep packet draft
  -> GM can save selected sections as private note or planning markers
```

Output sections:
- likely next scenes;
- unresolved threads;
- NPC/faction agendas;
- clues to surface;
- complications;
- player-facing recap candidate;
- prep questions for the GM.

### 4.3 Session Scribe And Canonization

User story:

```text
The GM gives Myroll rough notes after or during play and wants clean campaign memory.
```

Flow:

```text
GM enters rough session notes or selects current notes/transcript
  -> task session.extract_canon_candidates
  -> model returns memory candidates
  -> memory inbox shows each candidate with source evidence
  -> GM approve/edit/reject/link
  -> approved candidates create durable canon records
```

Candidate types:
- new fact;
- changed fact;
- NPC relationship update;
- faction/location state update;
- resolved thread;
- unresolved thread;
- clue discovered;
- player decision;
- player-safe recap item;
- contradiction warning.

### 4.4 Live DM Capture

User story:

```text
The GM is running the table and wants to capture quick private notes without stopping play.
The GM may type, paste, or use an external OS-level dictation tool.
Each submitted snippet becomes a timestamped private event for later recall and recaps.
```

Current product state:
- Myroll already has a Notes / Public Snippets surface;
- that surface is a full note editor with `created_at` and `updated_at`;
- it is not yet the ideal live-capture surface because repeatedly editing one note collapses many table moments into one mutable blob.

Golden path:

```text
GM opens a small Live Notes capture surface
  -> current campaign/session/scene are preselected
  -> GM types or dictates one short table event
  -> GM presses Save or Cmd/Ctrl+Enter
  -> backend creates an append-only timestamped transcript event
  -> input clears and focus remains in the capture box
  -> after the session, GM runs Build Session Recap
  -> recap/canonization tasks consume the ordered event stream
```

Voice-dictation expectation:
- Myroll does not bundle or depend on speech-to-text software;
- it should work well with external tools that type into the focused text field, such as Speak2 or OS-level dictation;
- product copy may recommend external dictation tools, but the app treats them as ordinary keyboard/text input;
- no microphone permission is required for v1.

Rules:
- live capture entries are GM-private by default;
- each submitted snippet is append-only and independently timestamped;
- edits should create a correction event linked to the original event, not silently rewrite chronology;
- backend timestamp is authoritative, not the browser clock;
- because API timestamps are second-resolution, live capture should also keep a per-session monotonic `orderIndex` for stable ordering when several snippets arrive in the same second;
- captured text is not canon by itself; it is source evidence for later memory candidates and session recaps.

Live play is capture-first, not summarization-first. Myroll should not continuously rebuild the full session summary during active play in v1. The live surface should stay fast, append-only, and low ceremony; the LLM-heavy step is an explicit post-session `session.build_recap` task.

### 4.5 Exact Recall

User story:

```text
The GM asks "what did we decide about this NPC?" or "who promised the party a favor?"
```

Flow:

```text
GM asks recall question
  -> lexical FTS recall over canon notes, session summaries, approved memory, entity notes, and selected run history
  -> status-aware ranking prefers canon/approved over proposals
  -> result shows cited snippets
  -> optional answer generation uses only cited evidence plus current context
```

First implementation uses SQLite FTS. Vector retrieval is deferred until lexical recall is not enough.

### 4.6 Player-Safe Recap Or Snippet

User story:

```text
The GM wants a player-facing recap or read-aloud text that does not reveal hidden facts.
```

Flow:

```text
GM selects public-safe context mode
  -> context builder excludes private notes, hidden entity fields, unrevealed clues, GM-only planning markers
  -> model drafts recap/snippet
  -> output remains draft
  -> GM may create PublicSnippet
  -> GM may publish through existing player-display flow
```

## 5. Data Model

The examples use TypeScript-style types. Backend implementation should map them to SQLAlchemy models and Pydantic response/request models.

This document uses the same `VersionedRecord` convention as `03-low-level-architecture.md`, with an explicit revision for optimistic concurrency:

```ts
type VersionedRecord = {
  id: string;
  revision: number;
  schemaVersion: number;
  createdAt: IsoDateTime;
  updatedAt: IsoDateTime;
};
```

### 5.1 Provider Profiles

```ts
type LlmProviderKind =
  | "openai_compatible";

type LlmProviderVendor =
  | "openai"
  | "ollama"
  | "lmstudio"
  | "kobold"
  | "openrouter"
  | "vllm"
  | "custom";

type LlmKeySource =
  | { type: "env"; name: string }
  | { type: "none" };

type LlmCapabilitySource =
  | "manual"
  | "probe";

type LlmProviderConformanceLevel =
  | "level_0_text_only"
  | "level_1_json_best_effort"
  | "level_2_json_validated"
  | "level_3_tool_capable";

type LlmProviderCapabilities = {
  streaming: boolean;
  jsonMode: boolean;
  toolCalls: boolean;
  embeddings: boolean;
  vision: boolean;
  conformanceLevel: LlmProviderConformanceLevel;
  source: LlmCapabilitySource;
  probedAt?: IsoDateTime;
};

type LlmTokenEstimateStrategy =
  | "tiktoken_openai"
  | "char_div_4_margin_20"
  | "manual";

type LlmProviderProbeResult = {
  modelsEndpointReachable: boolean;
  chatCompletionReachable: boolean;
  jsonModeAccepted: boolean;
  toolCallShapeAccepted: boolean;
  derivedConformanceLevel: LlmProviderConformanceLevel;
  detectedModelIds: string[];
  sanitizedWarnings: string[];
};

type LlmProviderProfile = VersionedRecord & {
  id: string;
  name: string;
  kind: LlmProviderKind;
  vendor: LlmProviderVendor;
  baseUrl: string;
  modelId: string;
  keySource: LlmKeySource;
  capabilities: LlmProviderCapabilities;
  timeoutMs: number;
  maxContextTokens: number;
  maxOutputTokens?: number;
  tokenEstimateStrategy: LlmTokenEstimateStrategy;
  lastProbeResult?: LlmProviderProbeResult;
  lastEstimateDriftPct?: number;
  allowUnverifiedLocalRuns?: boolean;
  enabled: boolean;
};
```

Rules:
- raw API keys are never stored in this record;
- `baseUrl` is private GM configuration and must not be exposed to `/player`;
- `keySource: { type: "none" }` is for unauthenticated local providers such as a default Ollama endpoint on `localhost:11434`;
- provider test results may be stored, but sanitized error messages only;
- `vendor` selects request-shaping defaults for OpenAI-compatible-but-not-identical servers;
- vendor presets cover model-list route assumptions, chat completion URL, system prompt handling, stop sequence shape, JSON-mode request shape, streaming parser, usage-token field parsing, and known error payload shapes;
- the capability flags are derived by probe when possible and may be manually overridden only in GM-private settings;
- conformance levels are derived from probe behavior, not vendor name alone;
- `level_0_text_only` means chat completions are reachable but structured JSON is not reliable;
- `level_1_json_best_effort` means the provider can attempt JSON-shaped output, but normalizer fallbacks and repair may be needed;
- `level_2_json_validated` means a schema-like JSON task succeeded in probe and is suitable for structured tasks by default;
- `level_3_tool_capable` is reserved for providers with validated tool-call shape support;
- changing `baseUrl`, `modelId`, `vendor`, or `keySource` invalidates probed capabilities by clearing `probedAt` and `lastProbeResult`; the next provider test must re-probe before the UI treats capabilities as verified;
- runs against a provider profile with invalidated/unverified capabilities must fail fast with HTTP 412 and `errorCode = "provider_unverified"` until the GM runs provider test again;
- a GM-private developer override may allow unverified runs only for local unauthenticated endpoints on `localhost`, `127.0.0.1`, `::1`, or private LAN ranges; never allow this override for metered or authenticated remote providers such as OpenAI or OpenRouter;
- override UI copy must say: `This provider has not been re-tested after configuration changes. Run anyway is allowed only for local unauthenticated endpoints.`;
- provider test should try `/v1/models` when available, then a minimal chat completion, then a `response_format: {"type":"json_object"}` probe for JSON mode;
- tool-call probing is optional in v1, but if implemented it must be a small explicit probe, not inferred from vendor name;
- the GM UI must warn that provider testing sends a real request to the configured endpoint and may incur a billable request;
- `maxContextTokens` is per provider profile and drives context trimming;
- OpenAI-family token estimates should use `tiktoken` when available;
- non-OpenAI estimates should use `chars / 4` plus a 20% safety margin until provider-specific tokenizers are added;
- every completed run should store actual reported token counts when the provider returns them;
- `lastEstimateDriftPct` should be a rolling average over the last 10 completed runs with actual usage, not the last run only;
- the UI should show estimate drift such as `estimated 4200, actual 5891`, plus the profile-level rolling drift when available.

### 5.2 Prompt Templates

```ts
type LlmTaskKind =
  | "session.prep_next"
  | "session.build_recap"
  | "session.extract_canon_candidates"
  | "session.player_safe_recap"
  | "scene.branch_directions"
  | "scene.develop_direction"
  | "npc.roleplay_cues"
  | "npc.suggest_patch"
  | "faction.suggest_moves"
  | "quest_board.suggest_entries"
  | "character.suggest_hooks"
  | "campaign.exact_recall"
  | "campaign.contradiction_check"
  | "draft.public_snippet"
  | "draft.private_note";

type LlmVisibilityMode =
  | "gm_private"
  | "public_safe"
  | "selected_only"
  | "recall_only";

type LlmOutputKind =
  | "plain_text"
  | "proposal_set"
  | "memory_candidates"
  | "entity_patch"
  | "session_recap_bundle"
  | "public_snippet_draft"
  | "private_note_draft"
  | "recall_answer";

type LlmPromptTemplate = VersionedRecord & {
  id: string;
  taskKind: LlmTaskKind;
  title: string;
  description: string;
  visibilityMode: LlmVisibilityMode;
  outputKind: LlmOutputKind;
  minProviderConformance: LlmProviderConformanceLevel;
  systemText: string;
  userTextTemplate: string;
  outputSchemaJson?: Record<string, unknown>;
  enabled: boolean;
};
```

Prompt templates should be code-defined first, not GM-authored dynamic prompts. User-editable prompt templates can come later.

Task conformance requirements:
- `campaign.exact_recall` may run on `level_0_text_only` when it returns cited prose without structured apply actions;
- `session.build_recap`, `scene.branch_directions`, `session.extract_canon_candidates`, and public draft tasks require at least `level_1_json_best_effort`;
- `level_2_json_validated` is preferred for all structured tasks and should be the default recommendation in setup UI;
- tasks requiring future tool calls must require `level_3_tool_capable`.

### 5.3 Context Packages

```ts
type LlmContextSourceKind =
  | "campaign"
  | "session"
  | "scene"
  | "entity"
  | "note"
  | "public_snippet"
  | "combat"
  | "proposal_option"
  | "planning_marker"
  | "memory_entry"
  | "memory_candidate"
  | "transcript_event"
  | "manual";

type LlmContextSourceRef = {
  kind: LlmContextSourceKind;
  id: string;
  label: string;
  revision?: number;
  lane: "canon" | "planning" | "draft";
  visibility: "gm_private" | "public_safe";
  included: boolean;
  reason: string;
  tokenEstimate: number;
};

type LlmContextPackage = VersionedRecord & {
  id: string;
  campaignId: CampaignId;
  sessionId?: SessionId;
  sceneId?: SceneId;
  taskKind: LlmTaskKind;
  visibilityMode: LlmVisibilityMode;
  sourceRefs: LlmContextSourceRef[];
  sourceRefHash: string;
  renderedMessages: Array<{ role: "system" | "user" | "assistant"; content: string }>;
  tokenEstimate: number;
  excludedReasonSummary: string[];
  reviewedAt?: IsoDateTime;
  reviewedBy?: "local_gm";
};
```

`renderedMessages` is saved as the exact context snapshot for run history. It must not contain API keys.

`sourceRefHash` is a canonical hash used for stale-preview detection. It is computed from `taskKind`, `visibilityMode`, selected GM instruction text, and included `sourceRefs` sorted by `(kind, id)` with their `revision`, `lane`, and `visibility`. Time-based preview expiry is optional and configurable; source hash drift is authoritative.

`excludedReasonSummary` is an aggregate UI helper, not the source of truth. It should contain unique compact reason codes derived from excluded `sourceRefs`, such as `rejected_proposal`, `expired_marker`, or `public_safe_filter`, so the preview can show "3 sources excluded" badges without parsing every row.

`reviewedAt` and `reviewedBy` are set when the GM explicitly reviews the full preview. Compact trusted previews should reference the reviewed package that made them eligible.

### 5.4 LLM Runs

```ts
type LlmRunStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "canceled";

type LlmRun = VersionedRecord & {
  id: string;
  parentRunId?: string;
  campaignId: CampaignId;
  sessionId?: SessionId;
  sceneId?: SceneId;
  entityId?: EntityId;
  providerProfileId: string;
  modelId: string;
  taskKind: LlmTaskKind;
  promptTemplateId: string;
  contextPackageId: string;
  status: LlmRunStatus;
  requestJson: Record<string, unknown>;
  responseText?: string;
  responseJson?: Record<string, unknown>;
  errorCode?: string;
  errorMessage?: string;
  inputTokens?: number;
  outputTokens?: number;
  estimatedInputTokens?: number;
  estimatedOutputTokens?: number;
  estimateDriftPct?: number;
  cancelRequestedAt?: IsoDateTime;
  durationMs?: number;
};
```

Run history is private GM data.

`queued` is reserved for future asynchronous/background execution. V1 may create runs directly as `running`.

Run cancellation rules:
- `running` runs must be cancellable through the Myroll API;
- v1 timeout handling is mandatory and must always move the run to a terminal state;
- cancellation marks `cancelRequestedAt` and best-effort aborts the backend upstream HTTP request when the HTTP client supports abort/timeout cancellation;
- shipped first-spine behavior is soft cancel with blocking `httpx` provider calls: cancellation updates durable run state immediately, and any provider response that arrives later is discarded instead of being committed as success; the upstream provider may still finish work or bill for the request;
- canceled runs end with `status = "canceled"` and keep partial metadata but no apply actions;
- if `cancelRequestedAt` is set before a provider response is committed, cancellation wins; implement with an atomic SQLite update condition or equivalent transaction check before committing `status = "succeeded"`;
- schema-repair child-run cancellation can be simplified in v1: cancel only the currently visible active run and never apply partial output from a canceled parent/child chain;
- if the backend restarts while runs are `running`, startup cleanup should mark stale runs as `failed` with `errorCode = "backend_restarted"` or `canceled` if a cancel had already been requested.

### 5.5 Proposal Sets And Options

```ts
type ProposalSetStatus =
  | "proposed"
  | "partially_used"
  | "rejected"
  | "superseded";

type ProposalOptionStatus =
  | "proposed"
  | "selected"
  | "rejected"
  | "saved_for_later"
  | "superseded"
  | "canonized";

type ProposalSet = VersionedRecord & {
  id: string;
  campaignId: CampaignId;
  sessionId?: SessionId;
  sceneId?: SceneId;
  llmRunId: string;
  contextPackageId: string;
  taskKind: LlmTaskKind;
  scopeKind: "campaign" | "session" | "scene";
  title: string;
  status: ProposalSetStatus;
  normalizationWarnings: Array<{
    code: string;
    index?: number;
    reason?: string;
    discarded?: boolean;
  }>;
};

type ProposalOption = VersionedRecord & {
  id: string;
  proposalSetId: string;
  stableOptionKey: string;
  title: string;
  summary: string;
  body: string;
  status: ProposalOptionStatus;
  consequences: string;
  reveals: string;
  staysHidden: string;
  proposedDelta: Record<string, unknown>; // inspection-only in v1
  planningMarkerText: string;
  selectedAt?: IsoDateTime;
  canonizedAt?: IsoDateTime;
};
```

Status rules:
- selecting one option does not automatically canonize it;
- selecting one option should automatically mark sibling options in the same proposal set as `superseded`, not `rejected`;
- `superseded` means "another option won"; `rejected` means the GM explicitly said no;
- superseded siblings remain restorable from proposal history;
- multiple selected options in the same proposal set are allowed when the GM explicitly restores/selects a superseded sibling later;
- each selected option can create its own independent planning marker;
- selecting an additional superseded sibling must not demote prior selected options;
- normal context includes selected/canonized summaries only through planning markers or canon records;
- `proposalOption.status` never makes raw `body` text eligible for normal context;
- selected options without planning markers are excluded from normal branch/recap context;
- rejected, superseded, saved-for-later, unselected, and selected option bodies are excluded from normal branch and recap prompts;
- one or two valid options are a degraded success and must surface a visible warning; zero valid options fails with no proposal records;
- malformed option rows may be discarded only when warnings record row/key, reason, and `discarded: true`;
- `stableOptionKey` is for deterministic UI/actions inside a proposal set and for later "regenerate/repair this option" workflows; it is not a cross-run identity guarantee.
- `stableOptionKey` should be generated by the normalizer as a slug of the option title plus a short content hash; when title/body parsing is weak, use a position-based fallback such as `option_1`.

### 5.6 Planning Markers

```ts
type PlanningMarkerStatus =
  | "active"
  | "expired"
  | "superseded"
  | "canonized"
  | "discarded";

type PlanningMarkerScope =
  | { type: "campaign"; campaignId: CampaignId }
  | { type: "session"; campaignId: CampaignId; sessionId: SessionId }
  | { type: "scene"; campaignId: CampaignId; sceneId: SceneId }
  | { type: "entity"; campaignId: CampaignId; entityId: EntityId };

type PlanningMarker = VersionedRecord & {
  id: string;
  campaignId: CampaignId;
  scope: PlanningMarkerScope;
  sourceProposalOptionId?: string;
  status: PlanningMarkerStatus;
  canonizedAt?: IsoDateTime;
  canonMemoryEntryId?: string;
  title: string;
  markerText: string;
  originalMarkerText?: string;
  lintWarnings: string[];
  provenance: {
    proposalSetId?: string;
    proposalOptionId?: string;
    llmRunId?: string;
    contextPackageId?: string;
  };
  editedAt?: IsoDateTime;
  editedFromSource: boolean;
  expiresAt?: IsoDateTime;
};
```

`markerText` must be written as planning intent, not as completed event history.

Shipped LLM-2 marker rules:
- active marker eligibility checks both `status = "active"` and `expiresAt` being absent or later than the backend UTC clock;
- generated and edited marker text both run wording lint;
- lint is a warning/confirmation surface, not a safety proof;
- context rendering always prefixes marker text as GM intent and labels it planning, not canon;
- marker text has a hard max of 1000 characters and a soft UI warning above 500 characters;
- default marker scope is exactly the proposal set scope unless the GM deliberately changes it;
- reject/save-for-later are blocked with `active_marker_exists` while a source option has an active marker;
- v1 enforces one marker per source proposal option for idempotency. Same idea with multiple scopes is deferred;
- `canonized` markers are not active planning context. Their future canon value is carried by the accepted memory entry linked through `canonMemoryEntryId`.

### 5.7 Canon Deltas And Memory Candidates

```ts
type CanonDeltaKind =
  | "session_summary"
  | "new_fact"
  | "changed_fact"
  | "entity_create_draft"
  | "entity_update"
  | "relationship_update"
  | "thread_opened"
  | "thread_resolved"
  | "clue_discovered"
  | "player_decision"
  | "public_recap_item"
  | "contradiction_warning";

type LlmSensitivityReason =
  | "spoiler"
  | "gm_only_motive"
  | "unrevealed_clue"
  | "future_plan"
  | "private_note";

type CanonDelta = {
  items: Array<{
    kind: CanonDeltaKind;
    title: string;
    body: string;
    targetKind?: "campaign" | "session" | "scene" | "entity" | "note";
    targetId?: string;
    publicSafe: boolean;
    sensitivityReason?: LlmSensitivityReason;
    evidenceRefs: Array<{ kind: LlmContextSourceKind; id: string; quote?: string }>;
  }>;
};

type MemoryCandidateStatus =
  | "pending"
  | "approved"
  | "edited"
  | "rejected"
  | "saved_for_later"
  | "accepted"
  | "applied";

type MemoryCandidate = VersionedRecord & {
  id: string;
  campaignId: CampaignId;
  sessionId?: SessionId;
  sceneId?: SceneId;
  sourceLlmRunId?: string;
  sourcePlanningMarkerId?: string;
  sourceProposalOptionId?: string;
  normalizationWarnings: string[];
  kind: CanonDeltaKind;
  title: string;
  body: string;
  claimStrength?: RecapClaimStrength;
  publicSafe: boolean;
  sensitivityReason?: LlmSensitivityReason;
  status: MemoryCandidateStatus;
  targetKind?: string;
  targetId?: string;
  targetRevision?: number;
  evidenceRefs: Array<{ kind: LlmContextSourceKind; id: string; quote?: string }>;
};
```

Memory candidates are the inbox. They are not canon until accepted into memory.

LLM-4 linked marker rules:
- `session.build_recap` may emit `relatedPlanningMarkerId` on a memory candidate draft;
- the backend persists this as `sourcePlanningMarkerId` only when the marker is active, included in the reviewed context package, scope-compatible, and supported by at least one non-planning evidence ref;
- campaign-scoped markers may be confirmed by any session in the same campaign; session markers must match the recap session; scene markers must belong to the recap session or appear in reviewed evidence refs;
- marker/proposal text is provenance and planning context, never evidence;
- invalid marker links with otherwise valid played evidence are dropped and surfaced as `planning_marker_link_ignored` on the candidate card;
- candidates whose body resembles marker text carry `candidate_body_resembles_planning_marker` as a warning so the GM can verify the accepted memory describes played events;
- weak or GM-review-only drafts never become memory candidates automatically, even if they reference a planning marker.

Candidate targeting rules:
- each `MemoryCandidate` targets at most one durable record;
- multi-target effects must be split by the extractor into separate atomic candidates and grouped in the UI by `sourceLlmRunId` and shared evidence;
- v1 extraction should prefer targetless atomic memory entries; entity/note patches are an explicit second action, not the default output for every fact;
- targetless candidates create new memory entries or notes and skip target revision checks;
- when `targetKind` and `targetId` are present, `targetRevision` is the revision of that target as recorded in the `LlmContextPackage.sourceRefs` that fed the LLM run, not the live revision at candidate persist time;
- this makes OCC protect against GM edits that happen between context preview/run start and apply;
- if a targeted candidate cannot be matched to a context source ref with a revision, it must not be auto-applicable; persist it as targetless review material or fail normalization for that candidate;
- the model never supplies `targetRevision`.

Memory inbox UI language should not expose the state machine as the primary user flow. Use actions such as `Accept into Memory`, `Accept and Update NPC`, `Reject`, and `Save for Later`. Internally these may map to approve/apply states, but the GM should not need to reason about `approved` versus `applied` while reviewing session facts.

Apply rules:
- for targetless memory candidates, `Accept into Memory` approves the candidate and creates the `CampaignMemoryEntry` in one transaction, ending with the implementation's terminal accepted state;
- targetless candidates should not remain in an "accepted but not remembered" state;
- for targeted patches, review/approve and apply may remain separate because the target write can fail OCC or need extra GM review;
- `apply` must run target writes and candidate status updates in one database transaction;
- repeated `apply` on an already-applied candidate must be idempotent and return the applied target state without double-writing;
- when `targetRevision` is present, apply must enforce optimistic concurrency and reject with HTTP 409 if the target record revision changed since extraction;
- stale candidates should surface a UI path to review, edit, or regenerate against the newer target.

Linked-marker accept rules:
- for a linked targetless memory candidate, `Accept into Memory` creates the `CampaignMemoryEntry`, sets the candidate terminal state, canonizes the planning marker, canonizes the source proposal option when present, and upserts the memory entry into recall/search in one transaction;
- edited linked candidates require an explicit confirmation flag because accepting them will canonize the linked planning marker;
- repeated accept is idempotent and reconciles missing marker/option/search-index state;
- accepting fails visibly when the linked marker is missing, expired, discarded, or already canonized by another memory entry;
- rejecting a linked candidate does not mutate the marker. The UI may offer a separate expire action.

### 5.8 Campaign Memory Entries

Approved memory should have a durable first-class home instead of living only as note prose.

```ts
type CampaignMemoryEntryStatus =
  | "active"
  | "superseded"
  | "retracted";

type CampaignMemoryEntry = VersionedRecord & {
  id: string;
  campaignId: CampaignId;
  sessionId?: SessionId;
  sceneId?: SceneId;
  entityId?: EntityId;
  sourceMemoryCandidateId?: string;
  sourcePlanningMarkerId?: string;
  sourceProposalOptionId?: string;
  kind: CanonDeltaKind;
  title: string;
  body: string;
  claimStrength?: RecapClaimStrength;
  publicSafe: boolean;
  sensitivityReason?: LlmSensitivityReason;
  status: CampaignMemoryEntryStatus;
  tags: string[];
  evidenceRefs: Array<{ kind: LlmContextSourceKind; id: string; quote?: string }>;
};
```

Rules:
- only approved/applied facts become memory entries;
- memory entries are context-eligible when `status = "active"`;
- superseded/retracted entries remain visible for audit and explicit recall, but are excluded from normal context;
- public-safe recap tasks may use only entries with `publicSafe = true`;
- `sensitivityReason` explains why a fact is hidden or risky and feeds public leak review UI;
- entity-specific memory should link `entityId` when known instead of relying on text search alone.
- linked planning-marker provenance is GM-private audit metadata; normal recall cites the accepted memory entry, not marker/proposal source text.

### 5.9 Transcript Events

```ts
type TranscriptEventKind =
  | "live_dm_note"
  | "gm_note"
  | "scene_activated"
  | "player_display_published"
  | "llm_run"
  | "proposal_option_selected"
  | "planning_marker_created"
  | "memory_candidate_approved"
  | "entity_created"
  | "entity_updated"
  | "combat_event"
  | "manual";

type TranscriptInputMode =
  | "typed"
  | "paste"
  | "dictation_external"
  | "imported"
  | "system";

type SessionTranscriptEvent = VersionedRecord & {
  id: string;
  campaignId: CampaignId;
  sessionId?: SessionId;
  sceneId?: SceneId;
  kind: TranscriptEventKind;
  inputMode: TranscriptInputMode;
  orderIndex: number;
  title: string;
  body: string;
  sourceRef?: { kind: string; id: string };
  correctsEventId?: string;
  publicSafe: boolean;
};
```

Transcript events support exact recall and chronological session reconstruction.

Live DM note event rules:
- `kind = "live_dm_note"` is the preferred storage for quick during-session capture;
- `inputMode = "dictation_external"` records that text arrived through an external dictation tool, but Myroll stores only the resulting text;
- `createdAt` is the backend capture timestamp;
- `orderIndex` is monotonic within a session and breaks ties for multiple events captured in the same second;
- `orderIndex` generation must be race-safe; prefer a `session_order_counter` table with an atomic `UPDATE ... RETURNING`, or use `BEGIN IMMEDIATE` around `MAX(order_index) + 1` plus a unique `(session_id, order_index)` constraint;
- if the implementation relies on a unique constraint for ordering, unique-constraint conflicts must retry the capture transaction with a small bounded retry instead of returning a 500;
- `publicSafe` defaults to `false` for `live_dm_note`; flipping it requires explicit GM action and is not part of the v1 live capture surface;
- for `live_dm_note`, `publicSafe = true` only makes the event eligible for public-safe context after explicit GM review; it never makes the raw dictated event publishable;
- correction events set `correctsEventId` to the original event; the original remains visible in audit history;
- default recap context prefers the correction event and excludes the corrected original from normal ranking, avoiding duplicate or contradictory recap evidence;
- `live_dm_note` transcript events rank in the draft lane for recall, below approved memory but above model-generated proposal history; `orderIndex` recency may boost results within the active session;
- live capture entries are source evidence for LLM recap/canonization, not approved memory by themselves.

For post-session recap assembly, the context builder should normalize the session's mixed source records into a single ordered evidence view:

```ts
type RecapEvidenceProjection = {
  sourceKind: LlmContextSourceKind;
  sourceId: string;
  eventKind?: TranscriptEventKind;
  timestamp: IsoDateTime;
  orderIndex?: number;
  label: string;
  actorName?: string;
  body: string;
  sourceRevision?: number;
  visibility: "gm_private" | "public_safe";
  lane: "canon" | "planning" | "draft";
  includedInRecap: boolean;
  excludedReason?: "corrected" | "shadowed_by_memory" | "prior_recap" | "public_safe_filter" | "manual";
};
```

`RecapEvidenceProjection` is a recap assembly view, not necessarily a separate durable table. Source records remain owned by their domain tables; the evidence view gives `session.build_recap` a stable timestamp/name/source/revision/visibility/lane shape across live notes, linked notes, entity changes, combat events, public-display actions, planning decisions, and approved memory.

If `RecapEvidenceProjection` is cached later, the cache must be derived, discardable, source-hash-bound, and never authoritative. A source correction, memory application, or visibility change must invalidate the projection cache before recap context can be built.

When an evidence item comes from a transcript row, `sourceKind = "transcript_event"` and `eventKind` carries the concrete event type such as `"live_dm_note"` or `"player_display_published"`. When the evidence item references a public snippet directly, use `sourceKind = "public_snippet"`.

When a live note has already produced an applied memory entry and that memory entry cites the live note in `evidenceRefs`, default recap assembly should include the memory entry and mark the source live note as `includedInRecap = false` with `excludedReason = "shadowed_by_memory"`. The live note remains available for audit and explicit recall. The recap prompt should also instruct the model that source streams can repeat the same fact and that it should deduplicate repeated evidence or flag contradictions.

```ts
type SessionRecapBundle = {
  privateRecap: {
    title: string;
    bodyMarkdown: string;
    keyMoments: Array<{
      orderIndex?: number;
      timestamp?: IsoDateTime;
      summary: string;
      claimStrength: RecapClaimStrength;
      evidenceRefs: Array<{ kind: LlmContextSourceKind; id: string; quote?: string }>;
    }>;
  };
  memoryCandidateDrafts: Array<{
    kind: CanonDeltaKind;
    title: string;
    body: string;
    claimStrength: RecapClaimStrength;
    targetKind?: "campaign" | "session" | "scene" | "entity" | "note";
    targetId?: string;
    publicSafe: boolean;
    sensitivityReason?: LlmSensitivityReason;
    evidenceRefs: Array<{ kind: LlmContextSourceKind; id: string; quote?: string }>;
  }>;
  continuityWarnings: Array<{
    title: string;
    body: string;
    evidenceRefs: Array<{ kind: LlmContextSourceKind; id: string; quote?: string }>;
  }>;
  unresolvedThreads: Array<{
    title: string;
    body: string;
    evidenceRefs: Array<{ kind: LlmContextSourceKind; id: string; quote?: string }>;
  }>;
};
```

```ts
type RecapClaimStrength =
  | "directly_evidenced"
  | "strong_inference"
  | "weak_inference"
  | "gm_review_required";
```

`SessionRecapBundle` is the structured output schema for `outputKind = "session_recap_bundle"`. The model returns drafts only: it must not supply `VersionedRecord` fields, `status`, or `targetRevision`. The backend normalizer validates the bundle and persists schema-valid `memoryCandidateDrafts` as pending `MemoryCandidate` rows in the memory inbox.

Memory-candidate `evidenceRefs` are not trusted because the model wrote them. The backend validates each candidate ref against the reviewed `LlmContextPackage.sourceRefs` that fed the run. Unknown `{ kind, id }` refs, fake quotes, and direct-evidence claims without a quote found in the cited source are rejected before a candidate can enter the inbox. This keeps the audit trail tied to what the model actually saw, not to arbitrary IDs it invented.

Rendered source blocks expose canonical evidence-reference fields:

```text
evidenceRefKind: session_transcript_event
evidenceRefId: <source id>
```

The model must use those exact values in `evidenceRefs`. Display metadata such as `eventType = live_dm_note` or `source = dictation` is useful for interpretation, but it is not a valid `evidenceRefs.kind`. This was added after real-provider testing showed that richer transcript metadata can otherwise lead the model to cite `live_dm_note`/`gm_correction` as fake source kinds.

Memory candidates may be created only for `directly_evidenced` and `strong_inference` recap claims. `strong_inference` candidates must be visually marked in the memory inbox. `weak_inference` and `gm_review_required` claims may appear in the recap draft or continuity warnings, but they must not become candidates without explicit GM rewrite.

Direct-evidence candidates may not cite speculative wording as proof. If an exact quote contains planning/conditional language such as `if played`, `possible consequence`, `may`, `could`, `must choose`, or `GM is considering`, the backend rejects the candidate with `speculative_evidence_for_direct_claim`. The model may still mention that material in the recap as uncertainty or GM review context, but it must not become accepted memory without GM rewrite.

Intermediate map-reduce partials should use a stricter shape than prose-only summary:

```ts
type PartialSessionRecap = {
  timelineItems: Array<{ orderIndex?: number; summary: string; evidenceRefs: Array<{ kind: LlmContextSourceKind; id: string; quote?: string }> }>;
  explicitFacts: Array<{ body: string; evidenceRefs: Array<{ kind: LlmContextSourceKind; id: string; quote?: string }> }>;
  inferredLinks: Array<{ body: string; evidenceRefs: Array<{ kind: LlmContextSourceKind; id: string; quote?: string }> }>;
  openQuestions: string[];
  doNotAssume: string[];
};
```

The final consolidation prompt must not convert `inferredLinks` into canon facts. Every recap key moment and every memory candidate draft needs evidence refs; claims without evidence stay as GM review notes, not memory.

## 6. Context Builder

The context builder is the most important backend component.

Suggested backend module:

```text
backend/app/llm/context_builder.py
```

Inputs:
- campaign ID;
- optional session ID;
- optional scene ID;
- optional entity/note/selection references;
- task kind;
- visibility mode;
- provider token budget;
- explicit include/exclude overrides.

Output:
- `LlmContextPackage`;
- rendered preview;
- token estimate;
- excluded-source report.

### 6.1 Source Priority

Default GM-private context order:

```text
1. Task instructions and output schema
2. Current selected object or scene
3. Active planning markers scoped to the current task
4. Exact recall evidence, when triggered or requested
5. Approved canon memory and session summaries
6. Live DM note transcript events for the current session, chronological by `orderIndex`
7. Relevant entities, notes, snippets, combat/session state
8. Recent transcript tail
9. Optional saved-for-later ideas, only for ideation tasks
```

Public-safe context order:

```text
1. Task instructions and output schema
2. Current public display state, if relevant
3. Public snippets
4. Public-known party/entity fields
5. Player-safe recap items
6. Public-known session summary
```

Public-safe generation is two-stage:
1. build context from public-safe sources only;
2. run a public leak review before any generated draft can become a `PublicSnippet`.

`publicSafe = true` is an eligibility flag, not a complete leak guarantee. Combination leaks are still possible when individually safe facts imply a hidden motive, clue, or future plan.

Leak review is a warning system, not proof of safety. Only GM review authorizes public text.

The leak review can be assisted by an LLM, but backend policy and GM review are the authority. Deterministic checks should flag suspicious phrases and references such as `secretly`, `unknown to the party`, `plans to`, `will later`, unrevealed entity names, private-only memory refs, or facts tagged with `sensitivityReason`.

### 6.2 Source Exclusion Rules

Always exclude unless explicitly requested:
- rejected proposal options;
- raw proposal option bodies;
- draft artifacts;
- expired planning markers;
- private notes in public-safe mode;
- `live_dm_note` transcript events with `publicSafe = false` in public-safe mode;
- corrected/superseded live DM note originals in default recap context;
- prior `session.build_recap` outputs for the same session unless `includePriorRecap = true`;
- hidden entity fields in public-safe mode;
- unrevealed clues in public-safe mode;
- hidden tokens and GM-only combat state in public-safe mode;
- API keys, local absolute paths, prompt logs containing secrets.

### 6.3 Token Budget

First implementation may use approximate token estimates, but the estimate must be conservative and provider-scoped.

Budget behavior:
- use the provider profile's `maxContextTokens`, not a global hard maximum;
- reserve output budget before packing context;
- fail closed if preview exceeds the configured provider context budget after trimming;
- otherwise trim in reverse priority order;
- never trim output schema or task safety instructions;
- prefer larger coherent note chunks over tiny fragments when the total corpus is small;
- record which sources were dropped and why;
- store estimated and actual token counts on `LlmRun` when available;
- update/display provider estimate drift so a GM can see when a local model's tokenizer differs materially from Myroll's estimate.

DM notes are usually small enough that whole-note or large-chunk inclusion is acceptable in v1.

`session.build_recap` is the exception where a long session can exceed a small local model's context window. When the assembled `RecapEvidenceProjection[]` cannot fit inside the provider profile's budget, the task may execute as map-reduce:
- split evidence into chronological `orderIndex` windows that each fit the budget;
- run private partial recap child runs for each window, producing `PartialSessionRecap` structured output rather than prose-only summaries;
- run a final consolidation pass over partial timelines, explicit facts, inferred links, continuity warnings, open questions, and `doNotAssume` lists;
- keep partial recap drafts as intermediate run artifacts only, not session summaries and not canon;
- expose only the consolidated `SessionRecapBundle` as the user-visible draft.

Naive single-pass trimming is not acceptable for `session.build_recap` when it would drop the middle of the session without telling the GM. The final pass must preserve causal uncertainty: inferred links can inform prose, but they must not become memory candidates unless backed by direct evidence or explicit GM review.

### 6.4 Retrieval

Full LLM-1 target retrieval:
- SQLite FTS over notes, public snippets, entity names/notes, approved memory, session summaries, transcript events, and proposal metadata;
- lightweight alias expansion before vector retrieval;
- status-aware ranking that prefers canon and approved records;
- `live_dm_note` events rank in the draft lane for recall, below approved memory but above model-generated proposal/prose history;
- active-session `orderIndex` recency can boost within live note results;
- proposal bodies are searchable for explicit recall/history mode only;
- rejected proposal bodies never appear in normal creative context.

```ts
type EntityAlias = VersionedRecord & {
  id: string;
  campaignId: CampaignId;
  entityId?: EntityId;
  aliasText: string;
  language?: string;
  confidence: "gm_confirmed" | "observed" | "generated_pending_approval";
  sourceRef?: { kind: LlmContextSourceKind; id: string };
};
```

Alias expansion is the v1 answer to fantasy names, spelling drift, transliteration, multilingual notes, and dictation mistakes. A query such as `златаря` may expand to approved aliases like `Aureon`, `goldsmith`, `златар`, and `cursed goldsmith` before FTS runs. Generated aliases must remain pending until the GM accepts them. `sourceRef` lets recall/debug UI explain where an observed alias came from, such as a transcript event, note, or manual entity edit.

Retrieval must be a two-stage pipeline:

```text
candidate search
  -> policy eligibility filter
  -> context packing
```

Route handlers must not do `FTS query -> feed to model` directly. The policy filter decides whether a found row is eligible for the selected task and visibility mode.

The shipped first recall spine is intentionally narrower: it uses a durable `scribe_search_index` projection table plus normalized substring matching over live captures, reviewed session recaps, and accepted campaign memory. It is enough to prove `Capture -> Recap -> Memory -> Recall`, but it should be treated as a documented limitation until the full FTS5-backed recall slice lands. Creative LLM tasks must not assume this basic search has complete coverage over notes, entities, public snippets, or proposal metadata.

Retrieval policy matrix:

```text
canon_only:
  approved memory, active canon summaries, public-safe sources when requested

canon_and_planning:
  canon plus active planning marker summaries, never raw proposal bodies

include_proposal_history:
  proposal history allowed, clearly labeled as draft/history

normal creative task:
  no raw proposal bodies ever
```

FTS coherence rules:
- all writes to FTS-indexed domain records must go through backend services that update the FTS index;
- route handlers should not issue raw INSERT/UPDATE/DELETE statements against indexed tables;
- migrations should add FTS5 triggers as a safety net where practical;
- tests must cover create/update/delete drift for at least notes, entities, approved memory entries, and transcript events;
- a repair/rebuild command can be added later, but it must not be the only coherence mechanism.

Future retrieval:
- vector embeddings over notes/memory/entity summaries;
- hybrid lexical + vector ranking;
- per-campaign embedding index;
- provider capability probe for embeddings.

Do not add a vector store until FTS quality or scale proves insufficient.

### 6.5 Structured Response Normalization

Structured tasks are not allowed to rely on magical parsing.

Normalization strategy:
- request provider JSON mode when `capabilities.jsonMode = true`;
- otherwise request plain text with an explicit JSON object and no prose;
- accept fenced JSON fallback by extracting the first valid fenced `json` block or first balanced JSON object;
- tolerate common alias keys only through a narrow mapping table, such as `options` -> `proposalOptions`;
- allow at most one schema-repair retry using the same provider profile and a small "repair this JSON to schema" prompt;
- schema-repair retry is recorded as a new `LlmRun` with `parentRunId` pointing to the original run, so audit history shows both the failed parse and the repair attempt;
- if parsing still fails, set `LlmRun.status = "failed"`, `errorCode = "parse_failed"`, and keep raw `responseText` visible in private run history;
- never apply partial/malformed structured output to proposals, memory candidates, or canon.

Rendered prompt structure should keep instructions and data visually and semantically separate:

```text
SYSTEM:
  task rules, output schema, visibility/canonization boundaries

USER:
  GM instruction for this run

CONTEXT:
  quoted campaign data blocks with source IDs
```

Every structured task prompt must state that text inside campaign/context blocks is source material, not instructions.

Expected parse failure cases:
- JSON wrapped in prose;
- JSON inside a code fence;
- truncated responses;
- trailing commas or comments;
- wrong root property names;
- missing required option IDs or canon delta fields.

## 7. API Surface

Initial API names are intentionally explicit and local.

### 7.1 Provider APIs

```text
GET    /api/llm/provider-profiles
POST   /api/llm/provider-profiles
PATCH  /api/llm/provider-profiles/{profile_id}
POST   /api/llm/provider-profiles/{profile_id}/test
```

Provider test:
- makes a minimal non-streaming request;
- returns provider/model reachability, conformance level, capability warnings, and sanitized errors;
- never returns API key values.

### 7.2 Context Preview And Runs

```text
POST /api/llm/context-preview
POST /api/llm/runs
GET  /api/llm/runs/{run_id}
POST /api/llm/runs/{run_id}/cancel
GET  /api/campaigns/{campaign_id}/llm/runs
```

`POST /api/llm/runs` must require a recent context preview ID. At run time the backend recomputes the canonical `sourceRefHash` from the selected task, visibility mode, GM instruction text, and current included source refs with revisions. If the preview is stale, missing, or the recomputed hash differs from the stored `LlmContextPackage.sourceRefHash`, the backend returns HTTP 409 with `errorCode = "context_preview_stale"` and the UI must force a new preview. Do not silently rebuild and send context the GM did not review.

Before starting the provider request, `POST /api/llm/runs` must verify that the provider profile's conformance level satisfies the selected prompt template's `minProviderConformance`. If not, return HTTP 412 with `errorCode = "provider_conformance_too_low"` and show the task requirement in the UI.

For `session.build_recap`, the context preview request should support explicit evidence include/exclude overrides and `includePriorRecap?: boolean`, defaulting to `false`. The stored context package must show which `RecapEvidenceProjection` rows were included, excluded, or shadowed before the run is allowed.

Context preview responses may include `trustedPreviewMode: "full" | "compact"`, `lastReviewedContextPackageId`, `lastReviewedAt`, and `lastReviewedBy: "local_gm"`. Compact mode is valid only when the backend verifies unchanged source hash and source classes; the frontend must still let the GM expand the full rendered prompt before running. The compact UI should explain why it is trusted, for example: `Full preview was reviewed at 20:14; context hash and source classes are unchanged.`

Cancellation behavior:
- cancel is best-effort but must update durable run state;
- cancel should abort the upstream HTTP request when the run is still active in this backend process;
- canceling a completed run is a no-op response with the current terminal run status;
- frontend refresh or navigation must not leave the backend run permanently stuck as `running`.

### 7.3 Proposal APIs

```text
GET  /api/campaigns/{campaign_id}/proposal-sets
GET  /api/proposal-sets/{proposal_set_id}
POST /api/campaigns/{campaign_id}/llm/branch-directions/build
POST /api/proposal-options/{option_id}/select
POST /api/proposal-options/{option_id}/reject
POST /api/proposal-options/{option_id}/save-for-later
POST /api/proposal-options/{option_id}/create-planning-marker
```

Selecting/adopting and canonizing are separate concerns. LLM-2 ships planning-marker adoption only; proposal canonization is deferred.

`POST /api/proposal-options/{option_id}/select` should, in the same transaction:
- set the selected option to `selected`;
- mark sibling `proposed` options in the same set as `superseded`;
- leave already-selected siblings selected;
- allow a previously `superseded` option to become selected without demoting prior selections;
- not create canon memory by itself.

`POST /api/proposal-options/{option_id}/create-planning-marker` wraps select + marker insert/update in one transaction:
- retry/double click returns the existing marker;
- if marker creation fails, selection state created by that request rolls back;
- active markers are the only normal future-context bridge from proposal options.

### 7.4 Planning Marker APIs

```text
GET    /api/campaigns/{campaign_id}/planning-markers
PATCH  /api/planning-markers/{marker_id}
POST   /api/planning-markers/{marker_id}/expire
POST   /api/planning-markers/{marker_id}/discard
```

### 7.5 Memory Inbox APIs

```text
GET  /api/campaigns/{campaign_id}/memory-candidates
POST /api/memory-candidates/{candidate_id}/approve
POST /api/memory-candidates/{candidate_id}/edit-and-approve
POST /api/memory-candidates/{candidate_id}/reject
POST /api/memory-candidates/{candidate_id}/save-for-later
POST /api/memory-candidates/{candidate_id}/apply

GET  /api/campaigns/{campaign_id}/memory-entries
GET  /api/memory-entries/{memory_entry_id}
PATCH /api/memory-entries/{memory_entry_id}
POST /api/memory-entries/{memory_entry_id}/supersede
POST /api/memory-entries/{memory_entry_id}/retract
```

Backend endpoints keep the explicit approve/apply state machine for audit and idempotency. UI copy should present `Accept into Memory` for targetless candidates and `Accept and Update ...` only when a reviewed target patch will be applied.

Apply behavior:
- execute target writes and candidate status updates inside one `db.begin()` transaction;
- reject stale target writes with HTTP 409 when `targetRevision` no longer matches;
- repeated apply on an already-applied candidate must not duplicate notes, memory entries, entity patches, or transcript events.

### 7.6 Recall APIs

```text
POST /api/llm/recall
```

Recall request:

```ts
type LlmRecallRequest = {
  campaignId: CampaignId;
  sessionId?: SessionId;
  sceneId?: SceneId;
  query: string;
  mode: "canon_only" | "canon_and_planning" | "include_proposal_history";
  limit?: number;
};
```

Recall response:

```ts
type LlmRecallResponse = {
  results: Array<{
    sourceKind: LlmContextSourceKind;
    sourceId: string;
    title: string;
    snippet: string;
    lane: "canon" | "planning" | "draft";
    score: number;
  }>;
};
```

## 8. GM UI

Primary surface:

```text
/gm assistant panel
```

The first UI should be practical, not chat-first. It must also avoid becoming a second cockpit on top of the GM workspace.

First shippable UI:
- live capture;
- Build Session Recap;
- Memory Inbox.

Provider status, run history, branch proposals, planning markers, and full context preview can exist behind drawers or later tabs, but they should not dominate the first view.

Required panels:
- provider status;
- task picker;
- live notes capture;
- build session recap action;
- context preview drawer;
- run output;
- proposal cards;
- memory inbox;
- planning markers;
- run history.

Task timing guidance:
- during play: live capture, exact recall, compact NPC cue glance, emergency short complication;
- before/after play: Build Session Recap, Memory Inbox review, branch directions, prep packets, player-safe recap;
- branch proposals are primarily prep/review tools, not the default live-table interaction.

Entry points:
- GM overview assistant panel;
- persistent compact live notes surface in `/gm`;
- session surface "Build Session Recap" button after play;
- scene/session surfaces "Capture note" affordance;
- scene surface "Develop Scene" / "Prep Next" buttons;
- entity/NPC card "Roleplay cues" / "Suggest update";
- notes selection "Summarize" / "Canonize" / "Player-safe recap";
- command palette.

### 8.1 Live Notes Capture

The live notes capture surface is intentionally smaller than the full Notes / Public Snippets editor.

UI requirements:
- single focused text area or compact input panel;
- active campaign/session/scene badges;
- Save button and explicit keyboard shortcut: Cmd+Enter on macOS, Ctrl+Enter elsewhere;
- inline empty-state/help text such as `Cmd/Ctrl+Enter to save - Enter for newline`;
- plain Enter inserts a newline by default, because dictation tools commonly emit newlines while the GM is still speaking;
- optional "save on Enter, newline with Shift+Enter" mode may exist later, but must be opt-in and not the live-note default;
- input clears after save and keeps focus;
- recent captured snippets list with timestamps;
- source mode indicator such as typed/pasted/dictated when known;
- no player-display actions;
- no public snippet creation from this surface in v1.

Speak2 and similar tools:
- the input should accept text generated by external dictation tools as normal keyboard input;
- no browser speech API integration is required;
- onboarding/help copy may say "Works well with external push-to-talk dictation tools such as Speak2.";
- onboarding/help copy should also say that the explicit Save shortcut avoids accidental saves from dictated newlines;
- v2 may inhibit saves after rapid Enter sequences, but v1 should rely on explicit Save/Cmd+Enter/Ctrl+Enter.

### 8.2 Proposal Cards

Proposal card content:
- title;
- short summary;
- consequences;
- what this reveals;
- what stays hidden;
- proposed canon delta;
- action buttons.

Actions:
- Adopt as planning direction;
- Edit and adopt;
- Save for later;
- Reject;
- Create canonization draft.

### 8.3 Memory Inbox

Memory inbox card content:
- candidate type;
- proposed canon text;
- target object;
- source evidence;
- public/private badge;
- actions.

Actions:
- Accept into Memory;
- Edit and Accept;
- Accept and Update NPC/entity when a target patch is available;
- Reject;
- Save for later;
- Link to entity/scene/session;
- Apply target change only after explicit GM review.

### 8.4 Build Session Recap

The Build Session Recap surface is a post-session review workflow, not a live-play panel.

UI requirements:
- entry point on the session/GM surface after play;
- evidence preview listing the `RecapEvidenceProjection[]` that will be sent, with timestamp/order, label, lane, visibility, and exclusion reason;
- toggles for explicit includes/excludes and an explicit `include prior recap` option, off by default;
- visible context-budget state, including whether the run will use single-pass or chunked map-reduce;
- Run button that creates a context preview before provider execution;
- recap draft editor for the returned private markdown recap;
- memory candidate review area linked to the Memory Inbox;
- Save Recap action that stores the reviewed private recap as the session summary/private note;
- separate action to run `session.player_safe_recap` after the private recap is accepted.

Default flow:

```text
GM opens ended or active session
  -> clicks Build Session Recap
  -> reviews ordered evidence and exclusions
  -> runs recap
  -> edits private recap draft
  -> reviews proposed memory candidates
  -> saves recap and applies selected candidates
  -> optionally runs Player-Safe Recap as a separate public-safe task
```

## 9. Task Catalog

The first task catalog should be small enough to implement and broad enough to prove the product loop. The order below groups user jobs; it is not the implementation order. Build order is defined in Section 10.

### 9.1 `scene.branch_directions`

Job:
- generate several plausible directions for the current scene/NPC encounter.

Inputs:
- active campaign/session/scene;
- selected NPC/entity optional;
- active planning markers;
- relevant canon facts;
- GM instruction.

Output:
- `ProposalSet` with 3-5 `ProposalOption` records;
- each option includes `proposedCanonDelta`.

Apply:
- adopt option as planning marker;
- later canonize only played events.

### 9.2 `session.prep_next`

Job:
- prepare a next-session packet from prior canon.

Inputs:
- campaign memory;
- last session summary;
- unresolved threads;
- party state;
- active planning markers.

Output:
- private prep draft;
- optional proposal set for possible scene directions;
- optional planning marker drafts.

Apply:
- save private note;
- create planning markers;
- create player-safe recap draft.

### 9.3 `session.extract_canon_candidates`

Job:
- turn a selected note/transcript fragment into memory candidates.

Scope:
- targeted extraction tool for selected text only;
- not the primary full-session recap workflow;
- useful when the GM wants to canonize one note, one transcript excerpt, or one correction without rebuilding the whole session recap.

Inputs:
- selected note/transcript text;
- live DM note transcript events from the active session, in `orderIndex` order;
- current session/scene;
- existing canon memory for contradiction checks.

Output:
- `MemoryCandidate[]`;
- contradiction warnings.

Apply:
- approve/edit/reject;
- write approved candidates into notes/entities/session memory.

### 9.4 `session.build_recap`

Job:
- build an authoritative private session recap after play, from the evidence accumulated during the session.

Scope:
- primary post-session workflow for session notes;
- returns recap plus memory candidate drafts;
- should be the default action when the GM asks Myroll to process a whole session.

Inputs:
- `RecapEvidenceProjection[]` assembled for the session, sorted by timestamp and `orderIndex`;
- live DM note transcript events from the active session;
- notes linked to the session/scene;
- NPC/entity changes and notable interactions during the session;
- combat/session state events;
- public-display publish events;
- selected planning markers and canon decisions;
- existing canon memory for continuity checks.

Output:
- structured `session_recap_bundle` with a private session recap draft;
- proposed memory candidate drafts for canon facts discovered during recap;
- continuity warnings and unresolved threads.

Apply:
- save the private recap as a session summary/private note after GM review;
- place canon candidates in the memory inbox;
- optionally run `session.player_safe_recap` afterward as a separate public-safe task.

Rules:
- this is a post-session button, not a live continuous summarizer;
- corrected live capture events replace their originals in default recap context;
- live capture source blocks render `orderIndex`, `capturedAt`, `eventType`, `source`, and `correctsEventId` as metadata before the body text, so chronology does not depend on prose alone;
- recap prompts instruct the model to use `orderIndex`/`capturedAt` for chronology and to use `evidenceRefKind`/`evidenceRefId` for structured citations;
- prior `session.build_recap` outputs for the same session are excluded by default, including saved session summaries produced by earlier recap runs;
- the GM may explicitly enable `include prior recap` for revision/diff workflows, but the default is fresh re-derivation from source evidence;
- when evidence exceeds the provider context budget, use chronological map-reduce rather than silently dropping the middle of the session;
- conditional/planning phrasing must not be converted into facts. Text like `if played`, `possible consequence`, `must choose`, or `GM is considering` remains uncertainty unless a later played-event capture confirms what happened;
- draft/planning evidence may inform the recap, but only GM-approved apply actions create canon.

### 9.5 `campaign.exact_recall`

Job:
- answer a factual recall question with cited evidence.

Inputs:
- recall query;
- FTS evidence;
- optional current scene/entity.

Output:
- cited answer;
- source snippets.

Apply:
- none by default;
- optional save answer as private note.

### 9.6 `session.player_safe_recap`

Job:
- draft a player-facing recap without hidden GM facts.

Inputs:
- public-safe context only;
- player-safe memory items;
- public snippets;
- public-known entities;
- optional reviewed private recap as a source only after public-safe filtering.

Output:
- public snippet draft;
- leak review warnings.

Apply:
- create `PublicSnippet` only after GM review;
- publish only through existing display action.

### 9.7 `npc.roleplay_cues`

Job:
- help the GM run an NPC consistently.

Inputs:
- selected NPC entity;
- recent interactions;
- active planning markers;
- exact recall evidence when needed.

Output:
- voice/mannerism reminders;
- likely motives;
- 3-5 possible responses;
- no canon write by default.

Apply:
- create proposal/planning marker;
- create entity patch draft if GM requests.

### 9.8 `npc.suggest_patch`

Job:
- propose updates to an NPC after play.

Inputs:
- NPC entity;
- selected session notes;
- recall evidence.

Output:
- entity patch draft;
- memory candidates.

Apply:
- update entity after GM review.

### 9.9 `campaign.contradiction_check`

Job:
- find likely continuity conflicts.

Inputs:
- selected notes/entity/scene;
- relevant canon memory;
- exact recall evidence.

Output:
- warnings with cited sources;
- suggested fixes as drafts.

Apply:
- none automatically.

## 10. Implementation Slices

The LLM work should not land as one huge slice. Build it in narrow, verifiable steps.

### PRE-LLM: Timestamped Live DM Capture

Goal:
- create the small private capture surface that feeds future LLM recap and canonization workflows.

Build:
- `session_transcript_events` or equivalent durable table if not already added by the LLM data migration;
- create/list APIs for live DM notes scoped to campaign/session/scene;
- backend-generated `createdAt` timestamp and race-safe per-session monotonic `orderIndex`;
- correction API/action that creates a new event with `correctsEventId` instead of mutating the original event body;
- compact `/gm` live notes capture panel;
- explicit Save/Cmd+Enter/Ctrl+Enter submission; plain Enter inserts newline by default;
- recent captured snippets list in chronological order;
- input mode metadata for typed, paste, and external dictation;
- no provider calls and no LLM dependency.

Tests:
- each capture creates a separate append-only event;
- events captured in the same second remain stably ordered by `orderIndex`;
- concurrent captures cannot receive the same `orderIndex`;
- unique-order conflicts retry instead of surfacing a 500;
- active session/scene are attached by default when present;
- editing one full note does not rewrite live capture chronology;
- correcting an event keeps the original in audit history but only the corrected version reaches default recap context;
- `/player` receives no live capture text.

Acceptance:

```text
open /gm during active session
  -> focus Live Notes input
  -> dictate or type one sentence
  -> press Cmd/Ctrl+Enter or click Save
  -> input clears and stays focused
  -> event appears with backend timestamp and order index
  -> repeat 50 times during a session
  -> session recap task can see the ordered private event stream
```

### LLM-0a: Minimal Provider Harness And Run History

Goal:
- make one backend-owned model call safely, with durable metadata and no campaign mutation.

Build:
- provider profiles and `llm_runs` tables only;
- static task registry with a minimal `draft.private_note` or provider smoke task;
- code-defined prompt templates;
- OpenAI-compatible client wrapper;
- provider test endpoint;
- vendor presets and conformance probing for OpenAI, Ollama, LM Studio, KoboldCpp, OpenRouter, vLLM, and custom endpoints;
- non-streaming run endpoint;
- timeout and best-effort cancellation;
- token estimate and actual token drift tracking;
- storage/export and retention settings for LLM history;
- no proposals, no memory candidates, no context packages beyond a minimal smoke-run payload.

Tests:
- provider profile does not store raw key value;
- mocked provider success;
- mocked timeout and best-effort cancellation;
- mocked 401/500 sanitized errors;
- mocked JSON-mode and conformance probe accepted/rejected;
- changing provider `baseUrl`, `modelId`, `vendor`, or `keySource` invalidates probed capabilities;
- remote/metered invalidated providers return HTTP 412 `provider_unverified`;
- local unauthenticated override is allowed only for localhost/private LAN endpoints;
- API key never appears in response/log-shaped payloads.

Acceptance:

```text
configure provider from env key
  -> UI warns provider test may make a billable request
  -> test provider
  -> probe assigns conformance level
  -> run minimal backend-owned prompt
  -> inspect run metadata
  -> export with "include LLM history" off omits request/response payloads
  -> key is absent from DB responses and logs
```

### LLM-0b: Context Packages And Trusted Preview

Goal:
- build previewable, hash-checked context packages without yet implementing every downstream task.

Build:
- `llm_context_packages` table;
- context builder;
- context preview API;
- compact trusted preview state;
- source revisions and canonical `sourceRefHash`;
- public-safe and GM-private context modes;
- policy eligibility filter before context packing.

Tests:
- public-safe mode excludes private notes/entity fields;
- public-safe mode excludes `live_dm_note` transcript events unless explicitly marked `publicSafe = true`;
- normal mode excludes raw proposals and rejected options;
- default recap context excludes corrected live-note originals when a correction event exists;
- active planning markers are included as planning text;
- expired markers are excluded;
- context preview stores source revisions and a canonical sourceRefHash;
- source revision/hash drift returns HTTP 409 instead of silently rebuilding context;
- fast trusted preview is available only when source hash and source classes match the last reviewed preview.
- compact trusted preview includes `lastReviewedContextPackageId`, `lastReviewedAt`, and `lastReviewedBy`.

Acceptance:

```text
select session and recap task
  -> full preview shows included/excluded sources
  -> rerun with unchanged source policy shows compact trusted preview
  -> changing source set forces full preview again
```

### LLM-0c: Session Build Recap Draft

Goal:
- prove the first useful Scribe loop: captured session evidence becomes a reviewed private recap draft.

Build:
- `session.build_recap` task;
- `RecapEvidenceProjection` assembly;
- `SessionRecapBundle` response schema;
- structured response normalization for recap bundle;
- long-session chronological map-reduce;
- Save Recap action to store reviewed private recap/session summary;
- no entity patching and no branch proposals yet.

Tests:
- build recap assembles live notes, linked notes, entity/session events, planning markers, and approved memory into ordered evidence;
- build recap uses live DM notes in `orderIndex` order;
- rendered recap context exposes transcript `capturedAt` and `orderIndex` as first-class metadata;
- memory-candidate evidence refs use canonical source kind/id fields and do not use display metadata such as `live_dm_note` as a source kind;
- direct-evidence memory candidates are rejected when their only exact quote is speculative/planning language;
- corrected live-note events replace originals in recap context while preserving audit history;
- applied memory entries shadow their source live notes in default recap context;
- regenerating recap excludes prior recap output from default context;
- long-session recap uses map-reduce when source evidence exceeds provider context budget;
- partial recap outputs preserve explicit facts, inferred links, open questions, and `doNotAssume`;
- memory candidate drafts require evidence refs and claim strength.

Acceptance:

```text
capture notes during a session
  -> click Build Session Recap after play
  -> review evidence preview
  -> run recap
  -> edit private recap draft
  -> save reviewed recap
  -> future context can include the saved recap
```

Real-provider discipline check:

```text
capture staged session notes
  -> correct one dictated mistake
  -> ask for three branch directions
  -> select option 2
  -> adopt only its planning marker
  -> record a later played-event capture for what actually happened
  -> build recap
  -> accept memory
  -> recall accepted memory
  -> assert /player payload unchanged
```

The real-provider journey is intentionally not only a pass/fail smoke test. It writes a markdown/JSON report comparing model output against expected anchors and boundary checks. The first run surfaced two useful issues:

- proposal consequence wording can become evidence if the DM copies it into a played capture; the journey now records a separate played fact instead of pasting proposal consequences;
- adding transcript metadata caused the model to cite `live_dm_note`/`gm_correction` as evidence kinds; the prompt now exposes `evidenceRefKind`/`evidenceRefId` and forbids using display metadata as citation identity.

After those changes, the measured real-provider run consistently preserves proposal-body exclusion, planning-only marker rendering, correction projection, speculative-phrase avoidance, and `/player` boundary checks. The LLM-4 journey now also records model linkage quality separately from backend contract checks: when the model emits a valid `relatedPlanningMarkerId`, accepting the linked memory candidate canonizes the marker/source option and future context carries the accepted memory entry instead of the raw proposal or active marker text.

### LLM-0d: Memory Inbox And Canon Entries

Goal:
- turn reviewed recap facts into explicit campaign memory without forcing entity mutation.

Build:
- memory candidate table/actions;
- campaign memory entries table;
- `session.extract_canon_candidates` task;
- memory candidate list/actions using `Accept into Memory` UI language;
- targetless atomic memory entries as the v1 default;
- optional second action to link candidate to an entity or create an entity patch draft;
- backend target revision capture only for explicit target patches;
- transcript event writes for accepted/rejected/applied memory.

Tests:
- multi-target output is split into atomic candidates;
- targetless candidates skip OCC and create new memory entries/notes;
- targetless `Accept into Memory` approves and applies in one transaction;
- targeted candidates copy target revision from the context package source ref that fed the model;
- candidates whose target was not in the model context are not auto-applicable target patches;
- pending candidates do not appear as canon;
- accepting into memory writes durable memory state;
- target apply is idempotent in one transaction;
- stale target revision returns HTTP 409 instead of clobbering newer GM edits;
- rejected candidates are excluded from normal context.

Acceptance:

```text
open recap memory drafts
  -> accept one fact into Memory
  -> optionally link it to an NPC
  -> future context includes accepted memory
  -> rejected candidate stays out of context
```

### LLM-1: Exact Recall And Alias Layer

Goal:
- retrieve campaign facts reliably enough to answer "what happened?" before adding flashy generation.

Build:
- SQLite FTS indexes for notes/entities/public snippets/session transcript/memory entries/proposal metadata where appropriate;
- FTS update triggers or service-level index writes with trigger safety net;
- `EntityAlias` table and manual alias UI/API;
- alias expansion before FTS;
- recall API;
- retrieval policy matrix.

Tests:
- recall prefers canon/approved records over draft/proposal records;
- alias expansion handles multilingual/fantasy spelling variants;
- alias records can explain their `sourceRef` in recall/debug UI;
- `canon_only` excludes proposals;
- `canon_and_planning` includes planning summaries but excludes raw proposals;
- `include_proposal_history` labels proposal history as draft/history;
- normal creative tasks never receive raw proposal bodies;
- FTS create/update/delete stays coherent for indexed records.

Acceptance:

```text
ask recall question with fuzzy or translated NPC name
  -> alias expansion finds the entity/memory
  -> answer cites source snippets
  -> rejected proposal history stays out unless explicitly requested
```

### LLM-2: Branch Proposals And Planning Markers

Status: `[shipped]`

Goal:
- support the "give me several directions, I choose one" workflow after the Scribe loop works.

Shipped build:
- `scene.branch_directions` template;
- structured response normalization into proposal sets/options;
- proposal card API actions;
- planning marker creation from selected option;
- context builder integration for active planning markers;
- scope-aware campaign/session/scene branch context preview;
- proposal cockpit in `/gm` with preview/review/run, degraded warnings, cards, history, active marker manager, and diagnostics.

Tests:
- structured response creates proposal set/options;
- fenced JSON and one schema-repair retry are handled;
- schema-repair retry creates a child run with `parentRunId`;
- malformed JSON after retry fails with `parse_failed` and no proposal records;
- one/two valid options persist as degraded success with visible warnings;
- selecting option does not canonize;
- selecting option supersedes sibling options;
- selecting a superseded sibling later allows multiple selected options and does not demote the first selected option;
- selected option without marker does not enter future context;
- planning marker includes selected direction without unplayed events;
- future normal context includes marker but excludes raw proposal bodies;
- expired markers are excluded using backend UTC time;
- recap context renders planning markers under `GM PLANNING CONTEXT, NOT PLAYED EVENTS`;
- planning-only evidence cannot become an automatic memory candidate;
- `/player` payload is unchanged after proposal generation, selection, marker adoption, expiry, and discard.

Acceptance:

```text
run branch directions for a scene during prep
  -> receive 3-5 proposal options
  -> adopt option 2
  -> sibling options are marked superseded
  -> active planning marker is created
  -> next context preview includes planning marker
  -> next context preview excludes other proposal bodies
```

Shipped v1 limitations:
- one planning marker per source proposal option;
- proposed deltas are inspection-only and labeled as possible consequences if played;
- no direct proposal-body canonization/apply endpoint;
- full FTS5 proposal-history recall remains future work;
- provider calls remain non-streaming with the same soft-cancel behavior as the recap path.

### LLM-3: Player-Safe Recaps And Snippet Drafting

Status: `[shipped]`

Goal:
- produce public-safe drafts that still require leak review and explicit publish.

Shipped build:
- `session.player_safe_recap` task with `visibility_mode = public_safe`;
- public-safe source curation for reviewed session recaps and accepted memory entries;
- marking a recap or memory entry public-safe runs the deterministic warning scan server-side; warning-bearing text requires exact-content acknowledgment before it becomes eligible;
- shown public snippets included by default, with unshown/manual snippets excluded unless explicitly included;
- public-known entity shell projection only, using display name when available and kind;
- reviewed context preview with hash-bound include/exclude choices;
- public-safe context preview reports source-class overflow when only the newest capped sources are included;
- deterministic leak warning pass over title/body, including English and Bulgarian spoiler/future-plan phrase starters plus explicit private-reference checks;
- `PublicSnippet` creation from reviewed LLM draft only when the submitted title/body match the backend warning-scan hash;
- medium/high warnings, or 3+ low warnings, require exact-content acknowledgment;
- LLM snippet provenance and warning metadata remain GM-private and are stripped from default export and all `/player` payloads;
- `last_published_at` and `publication_count` track text shown on the player display, not confirmed player knowledge.

Tests:
- public-safe context excludes private notes, private recaps/memory, live captures, planning markers, proposal bodies, entity notes/tags/custom fields, and LLM run output;
- toggling public-safe state or source include/exclude choices stales reviewed previews;
- risky recap/memory text cannot be marked public-safe without warning acknowledgment;
- leak warning flags suspicious phrases and private-only references;
- draft creation does not create a snippet or mutate player display;
- LLM-sourced snippet creation requires same-campaign source run, current warning scan, and acknowledgment when needed;
- player display serialization strips provenance/warnings and sanitizes Markdown;
- publish still goes through existing `show-snippet`/scene publish APIs and updates publication tracking.

Acceptance:

```text
run player-safe recap
  -> preview contains public-safe sources only
  -> draft is created with leak warnings where relevant
  -> GM creates PublicSnippet
  -> /player changes only after explicit publish
```

Shipped v1 limitations:
- no LLM-assisted leak review;
- no public draft table, so edited draft state is held in the browser until snippet creation;
- no raw private recap filtering shortcut;
- no raw live capture inclusion in public-safe recap;
- full edit diff/provenance is deferred; v1 stores `source_llm_run_id`, `source_draft_hash`, and final snippet text only;
- deterministic warning phrase lists are intentionally easy to extend and should not be treated as exhaustive.

### LLM-4: Proposal Canonization Bridge

Status: `[shipped]`

Goal:
- connect planning markers to later played evidence without ever canonizing raw proposal text.

Shipped build:
- `session.build_recap` memory candidate drafts may include `relatedPlanningMarkerId`;
- active planning markers are rendered with machine-copy marker IDs in recap context;
- backend validation accepts a marker link only when played non-planning evidence supports the candidate;
- invalid marker links are dropped into unlinked candidates with visible normalization warnings when the candidate is otherwise valid;
- `Accept into Memory` canonizes the linked marker and source option atomically with the accepted memory entry;
- canonized markers leave active planning context, while accepted memory carries the future canon fact;
- normal recall cites accepted memory entries, not marker/proposal provenance.

Tests:
- recap draft with marker ID plus transcript evidence creates a linked memory candidate;
- marker-only evidence is rejected;
- invalid marker IDs with valid played evidence become unlinked candidates with `planning_marker_link_ignored`;
- edited linked candidates require explicit confirmation before accept;
- expired/discarded/canonized-by-other markers block accept;
- linked accept is idempotent, repairs missing search-index state, and atomically canonizes marker/option;
- canonized marker text leaves future active planning context;
- accepted memory appears in recall and future context;
- proposal cards never expose a direct canonize/apply action.

Acceptance:

```text
GM adopts a planning marker
  -> table later records played evidence
  -> recap proposes a memory candidate with relatedPlanningMarkerId
  -> GM reviews marker plus played evidence side by side
  -> Accept into Memory creates canon memory
  -> marker/option show Canonized via memory
  -> future context uses accepted memory, not raw marker/proposal text
```

Shipped v1 limitations:
- one memory candidate links to at most one planning marker;
- one marker can be canonized by at most one memory entry;
- manual relinking is deferred;
- entity patching and proposal-body canonization remain deferred;
- hard delete may sever marker/option provenance because new provenance FKs use `ON DELETE SET NULL`.

### LLM-5: Vector Retrieval And Embeddings

Status:
- deferred.

Add only after FTS recall proves insufficient.

Build later:
- embedding provider capability;
- per-campaign embedding index;
- background reindex;
- hybrid retrieval;
- chunk strategy.

Do not block PRE-LLM through LLM-4 on this.

## 11. Backend Placement

Suggested modules:

```text
backend/app/llm/
  __init__.py
  provider_profiles.py
  client.py
  conformance.py
  context_builder.py
  recall.py
  aliases.py
  task_registry.py
  response_normalizer.py
  recap.py
  proposals.py
  planning_markers.py
  memory_inbox.py
  public_safety.py
```

LLM routes should start in a separate route module:

```text
backend/app/api/routes_llm.py
```

`backend/app/api/routes.py` is already large enough that adding the LLM API surface there would make future review harder. Route handlers should call domain services rather than embedding prompt/context logic in route functions.

Database models can initially live in `backend/app/db/models.py` to match the current codebase. Split later only if the file becomes unmanageable.

Frontend can initially use existing flat structure:

```text
frontend/src/llm/
  AssistantPanel.tsx
  ContextPreviewDrawer.tsx
  ProposalCards.tsx
  MemoryInbox.tsx
  PlanningMarkers.tsx
```

If the frontend stays flat for now, keep components small and API calls centralized in `frontend/src/api.ts`.

## 12. Test Plan

Backend unit/API tests:
- provider profile validation;
- provider test success/failure with mocked HTTP;
- provider conformance level gating by task;
- context builder public/private filtering;
- retrieval policy matrix;
- alias expansion;
- recap evidence projection assembly;
- public-safe leak review warnings;
- proposal lifecycle transitions;
- planning marker context eligibility;
- memory candidate approve/apply/reject transitions;
- recall ranking and status filtering;
- retention payload purge keeps metadata and removes prompt/response bodies;
- API key redaction.

Frontend tests:
- task picker renders task registry;
- compact trusted preview expands to full preview;
- context preview shows included/excluded sources;
- Build Session Recap evidence review flow;
- proposal card actions call correct APIs;
- memory inbox action flow;
- public-safe leak warnings are visible before snippet creation;
- no player-display publish after LLM draft generation.

E2E tests:
- live capture to recap to accepted memory;
- exact recall with alias expansion;
- mocked provider branch proposal/adopt flow;
- opt-in real provider campaign journey: live captures, correction, branch proposals, selected option without marker exclusion, marker adoption, later played-event capture, recap, memory accept, recall, and `/player` unchanged assertion;
- mocked provider canonization flow;
- public-safe recap draft to public snippet;
- `/player` unchanged until explicit publish.

## 13. Security And Privacy Checklist

Before accepting any LLM slice:
- provider HTTP calls happen only from the FastAPI backend process;
- the browser never receives raw API keys and never calls the provider directly;
- no raw API keys in DB, API responses, logs, screenshots, or exports;
- no LLM endpoints consumed by `/player`;
- no prompt payloads sent over display transport;
- no private context in public-safe mode;
- public-safe drafts pass leak review before snippet creation;
- no model output applied without explicit GM action;
- no generated public content published automatically;
- no rejected/raw proposals in normal context;
- retrieval results pass policy filtering before context packing;
- sanitized error envelope for provider errors;
- all run history is campaign-scoped private GM data.

Prompt-injection expectation:
- GM-written and pasted campaign text is not isolated from model instructions once included in context;
- JSON mode, strict schemas, output validation, and draft/apply review are mitigations, not a firewall;
- never rely on the model to enforce private/public visibility or canonization rules.

Export behavior:
- storage export should expose an "include LLM history" option;
- default should be off;
- when off, exports keep metadata such as run ID, task kind, provider profile label, model ID, timestamps, status, token counts, and duration, but omit or redact `requestJson`, rendered prompt messages, `responseText`, and `responseJson`;
- when on, the UI must warn that LLM history can contain inline private notes, entity secrets, GM prompts, and provider responses.
- campaign export may include provider profile labels, vendor names, and model IDs referenced by historical runs;
- importing a campaign must not activate runnable provider profiles from the export automatically;
- after import, the GM must explicitly map historical provider references to local provider profiles before new runs can use them.

Retention controls:
- default should keep run metadata even when full payload retention is disabled;
- GM setting: `Keep full prompt/response payloads` off by default for new campaigns after the first LLM slice unless the GM opts in;
- optional retention window: delete full payloads older than 30 days, 90 days, or never;
- manual purge action: delete prompt/response bodies for a campaign while keeping audit metadata;
- purge/export redaction must preserve enough metadata for debugging task kind, status, provider profile label, model ID, timing, token counts, and error code.

## 14. Open Decisions

1. Should provider profiles be global local settings or campaign-scoped records?
   - Recommended v1: global local settings with run history campaign-scoped.

2. Should streaming be supported in the first provider harness?
   - Recommended v1: non-streaming first; add streaming only after run persistence and cancellation semantics are clean.

3. Should memory candidates apply into a new dedicated `campaign_memory_entries` table or into notes/entities first?
   - Recommended v1: use a dedicated memory table for approved atomic facts, plus optional target patches for entities/notes.

4. Should prompt templates be editable by the GM?
   - Recommended v1: built-in templates only, with a freeform GM instruction field per run.

5. Should selected proposal options automatically reject siblings?
   - Decision for v1: selecting one option auto-supersedes sibling proposed options. It does not mark them rejected, and a restore action remains possible from proposal history.

6. Should Quick NPC promotion integrate with LLM immediately?
   - Recommended v1: no. Quick NPC stays static/local. LLM may later help expand a promoted NPC after it is a campaign entity.

## 15. First Build Recommendation

Build the smallest useful vertical path:

```text
PRE-LLM live capture
  -> LLM-0a minimal provider harness
  -> LLM-0b context preview
  -> LLM-0c Build Session Recap
  -> LLM-0d Memory Inbox
  -> LLM-1 Exact Recall
```

This proves the product's differentiating loop:

```text
Capture what happened.
Build a private recap.
Review candidate facts.
Accept memory.
Recall it later with citations.
```

Then add creative planning:

```text
LLM-2 branch proposals and planning markers
  -> ask for several possible directions
  -> choose one
  -> carry only that selected planning direction forward
  -> do not pollute canon or future context with rejected branches
```

Do not let `LLM-2` branch proposals leapfrog `LLM-0c` and `LLM-0d`. The first useful product proof is memory, then recall; creative branching comes after the Scribe spine works.
