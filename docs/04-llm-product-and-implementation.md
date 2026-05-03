# Myroll LLM Product And Implementation Spec

Date: 2026-05-03
Status: Draft for review

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
- selected/canonized proposal outcomes;
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

### 4.4 Exact Recall

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

### 4.5 Player-Safe Recap Or Snippet

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

type LlmProviderCapabilities = {
  streaming: boolean;
  jsonMode: boolean;
  toolCalls: boolean;
  embeddings: boolean;
  vision: boolean;
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
- changing `baseUrl`, `modelId`, `vendor`, or `keySource` invalidates probed capabilities by clearing `probedAt` and `lastProbeResult`; the next provider test must re-probe before the UI treats capabilities as verified;
- runs against a provider profile with invalidated/unverified capabilities must fail fast with HTTP 412 and `errorCode = "provider_unverified"` until the GM runs provider test again;
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
  systemText: string;
  userTextTemplate: string;
  outputSchemaJson?: Record<string, unknown>;
  enabled: boolean;
};
```

Prompt templates should be code-defined first, not GM-authored dynamic prompts. User-editable prompt templates can come later.

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
};
```

`renderedMessages` is saved as the exact context snapshot for run history. It must not contain API keys.

`sourceRefHash` is a canonical hash used for stale-preview detection. It is computed from `taskKind`, `visibilityMode`, selected GM instruction text, and included `sourceRefs` sorted by `(kind, id)` with their `revision`, `lane`, and `visibility`. Time-based preview expiry is optional and configurable; source hash drift is authoritative.

`excludedReasonSummary` is an aggregate UI helper, not the source of truth. It should contain unique compact reason codes derived from excluded `sourceRefs`, such as `rejected_proposal`, `expired_marker`, or `public_safe_filter`, so the preview can show "3 sources excluded" badges without parsing every row.

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
- cancellation aborts the backend upstream HTTP request when the HTTP client supports abort/timeout cancellation;
- canceled runs end with `status = "canceled"` and keep partial metadata but no apply actions;
- if `cancelRequestedAt` is set before the provider response is committed, cancellation wins; discard the successful provider response and finalize the run as `canceled`;
- the transaction that finalizes a successful provider response must re-read `cancelRequestedAt` inside the transaction, using a row lock or equivalent atomic update condition, before committing `status = "succeeded"`;
- cancellation of a schema-repair flow targets the currently active child run; canceling the parent after the child is running should surface or redirect to the child run status;
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
  entityId?: EntityId;
  llmRunId: string;
  taskKind: LlmTaskKind;
  title: string;
  status: ProposalSetStatus;
};

type ProposalOption = VersionedRecord & {
  id: string;
  proposalSetId: string;
  stableOptionKey: string;
  title: string;
  summary: string;
  body: string;
  status: ProposalOptionStatus;
  proposedCanonDelta: CanonDelta;
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
- raw `body` text remains excluded by default;
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
  title: string;
  markerText: string;
  expiresAt?: IsoDateTime;
};
```

`markerText` must be written as planning intent, not as completed event history.

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

type CanonDelta = {
  items: Array<{
    kind: CanonDeltaKind;
    title: string;
    body: string;
    targetKind?: "campaign" | "session" | "scene" | "entity" | "note";
    targetId?: string;
    publicSafe: boolean;
    evidenceRefs: Array<{ kind: LlmContextSourceKind; id: string; quote?: string }>;
  }>;
};

type MemoryCandidateStatus =
  | "pending"
  | "approved"
  | "edited"
  | "rejected"
  | "saved_for_later"
  | "applied";

type MemoryCandidate = VersionedRecord & {
  id: string;
  campaignId: CampaignId;
  sessionId?: SessionId;
  sceneId?: SceneId;
  sourceLlmRunId?: string;
  sourceProposalOptionId?: string;
  kind: CanonDeltaKind;
  title: string;
  body: string;
  publicSafe: boolean;
  status: MemoryCandidateStatus;
  targetKind?: string;
  targetId?: string;
  targetRevision?: number;
  evidenceRefs: Array<{ kind: LlmContextSourceKind; id: string; quote?: string }>;
};
```

Memory candidates are the inbox. They are not canon until approved/applied.

Candidate targeting rules:
- each `MemoryCandidate` targets at most one durable record;
- multi-target effects must be split by the extractor into separate atomic candidates and grouped in the UI by `sourceLlmRunId` and shared evidence;
- targetless candidates create new memory entries or notes and skip target revision checks;
- when `targetKind` and `targetId` are present, `targetRevision` is the revision of that target as recorded in the `LlmContextPackage.sourceRefs` that fed the LLM run, not the live revision at candidate persist time;
- this makes OCC protect against GM edits that happen between context preview/run start and apply;
- if a targeted candidate cannot be matched to a context source ref with a revision, it must not be auto-applicable; persist it as targetless review material or fail normalization for that candidate;
- the model never supplies `targetRevision`.

Apply rules:
- `apply` must run target writes and candidate status updates in one database transaction;
- repeated `apply` on an already-applied candidate must be idempotent and return the applied target state without double-writing;
- when `targetRevision` is present, apply must enforce optimistic concurrency and reject with HTTP 409 if the target record revision changed since extraction;
- stale candidates should surface a UI path to review, edit, or regenerate against the newer target.

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
  kind: CanonDeltaKind;
  title: string;
  body: string;
  publicSafe: boolean;
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
- entity-specific memory should link `entityId` when known instead of relying on text search alone.

### 5.9 Transcript Events

```ts
type TranscriptEventKind =
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

type SessionTranscriptEvent = VersionedRecord & {
  id: string;
  campaignId: CampaignId;
  sessionId?: SessionId;
  sceneId?: SceneId;
  kind: TranscriptEventKind;
  title: string;
  body: string;
  sourceRef?: { kind: string; id: string };
  publicSafe: boolean;
};
```

Transcript events support exact recall and chronological session reconstruction.

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
6. Relevant entities, notes, snippets, combat/session state
7. Recent transcript tail
8. Optional saved-for-later ideas, only for ideation tasks
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

### 6.2 Source Exclusion Rules

Always exclude unless explicitly requested:
- rejected proposal options;
- raw proposal option bodies;
- draft artifacts;
- expired planning markers;
- private notes in public-safe mode;
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

### 6.4 Retrieval

V1 retrieval:
- SQLite FTS over notes, public snippets, entity names/notes, approved memory, session summaries, transcript events, and proposal metadata;
- status-aware ranking that prefers canon and approved records;
- proposal bodies are searchable for explicit recall/history mode only;
- rejected proposal bodies never appear in normal creative context.

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
- returns provider/model reachability and sanitized errors;
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

Cancellation behavior:
- cancel is best-effort but must update durable run state;
- cancel should abort the upstream HTTP request when the run is still active in this backend process;
- canceling a completed run is a no-op response with the current terminal run status;
- frontend refresh or navigation must not leave the backend run permanently stuck as `running`.

### 7.3 Proposal APIs

```text
GET  /api/campaigns/{campaign_id}/proposal-sets
GET  /api/proposal-sets/{proposal_set_id}
POST /api/proposal-options/{option_id}/select
POST /api/proposal-options/{option_id}/reject
POST /api/proposal-options/{option_id}/save-for-later
POST /api/proposal-options/{option_id}/create-planning-marker
POST /api/proposal-options/{option_id}/create-canonization-draft
```

Selecting and canonizing are separate endpoints.

`POST /api/proposal-options/{option_id}/select` should, in the same transaction:
- set the selected option to `selected`;
- mark sibling `proposed` options in the same set as `superseded`;
- leave already-selected siblings selected;
- allow a previously `superseded` option to become selected without demoting prior selections;
- create a transcript event for the selection;
- not create canon memory by itself.

### 7.4 Planning Marker APIs

```text
GET    /api/campaigns/{campaign_id}/planning-markers
POST   /api/campaigns/{campaign_id}/planning-markers
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

Approve can mark the candidate as approved. Apply performs the durable campaign write. Combining approve and apply is allowed as a UI shortcut, but the backend should keep the state transition explicit.

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

The first UI should be practical, not chat-first.

Required panels:
- provider status;
- task picker;
- context preview drawer;
- run output;
- proposal cards;
- memory inbox;
- planning markers;
- run history.

Entry points:
- GM overview assistant panel;
- scene surface "Develop Scene" / "Prep Next" buttons;
- entity/NPC card "Roleplay cues" / "Suggest update";
- notes selection "Summarize" / "Canonize" / "Player-safe recap";
- command palette.

### 8.1 Proposal Cards

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

### 8.2 Memory Inbox

Memory inbox card content:
- candidate type;
- proposed canon text;
- target object;
- source evidence;
- public/private badge;
- actions.

Actions:
- Approve;
- Edit and approve;
- Reject;
- Save for later;
- Link to entity/scene/session;
- Apply now.

## 9. Task Catalog

The first task catalog should be small enough to implement and broad enough to prove the product loop.

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
- turn rough GM notes/transcript into memory candidates.

Inputs:
- selected note/transcript text;
- current session/scene;
- existing canon memory for contradiction checks.

Output:
- `MemoryCandidate[]`;
- contradiction warnings.

Apply:
- approve/edit/reject;
- write approved candidates into notes/entities/session memory.

### 9.4 `campaign.exact_recall`

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

### 9.5 `session.player_safe_recap`

Job:
- draft a player-facing recap without hidden GM facts.

Inputs:
- public-safe context only;
- player-safe memory items;
- public snippets;
- public-known entities.

Output:
- public snippet draft.

Apply:
- create `PublicSnippet`;
- publish only through existing display action.

### 9.6 `npc.roleplay_cues`

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

### 9.7 `npc.suggest_patch`

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

### 9.8 `campaign.contradiction_check`

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

### LLM-0: Data Foundations And Static Task Registry

Goal:
- create the durable tables and static task definitions without making external model calls yet.

Build:
- Alembic migration for provider profiles, prompt templates, context packages, LLM runs, proposal sets/options, planning markers, memory candidates, campaign memory entries, and transcript events;
- static task registry in backend code;
- Pydantic request/response models;
- seed default prompt templates or load them from code;
- basic list/read APIs for task registry.

Tests:
- migration creates tables and constraints;
- provider profile does not store raw key value;
- proposal statuses validate;
- planning markers require scope;
- memory candidates stay pending until explicit action.

Acceptance:

```text
fresh dev DB migrates
  -> task registry lists built-in tasks
  -> provider profile can be saved with env key reference
  -> proposal/memory/planning records can be created in tests
  -> no provider call is made
```

### LLM-1: Provider Profiles And Run Harness

Goal:
- run a minimal OpenAI-compatible request and persist safe run history.

Build:
- OpenAI-compatible client wrapper;
- provider test endpoint;
- vendor presets and capability probing for OpenAI, Ollama, LM Studio, KoboldCpp, OpenRouter, vLLM, and custom endpoints;
- non-streaming run endpoint;
- cancel endpoint with upstream HTTP abort where supported;
- request timeout and sanitized error mapping;
- run history persistence;
- token estimate and actual token drift tracking;
- storage/export setting for LLM history inclusion;
- no draft apply behavior yet.

Tests:
- mocked provider success;
- mocked timeout;
- mocked cancellation;
- cancel-vs-completion race finalizes as canceled when cancel was requested before response commit;
- mocked 401/500 sanitized errors;
- mocked JSON-mode capability probe accepted/rejected;
- changing provider `baseUrl`, `modelId`, `vendor`, or `keySource` invalidates probed capabilities;
- runs against invalidated provider capabilities return HTTP 412 `provider_unverified`;
- API key never appears in response/log-shaped payloads.

Acceptance:

```text
configure provider from env key
  -> UI warns provider test may make a billable request
  -> test provider
  -> probe detects available model list and JSON mode support where available
  -> change model ID
  -> capabilities are marked unverified until provider test runs again
  -> running before re-test returns provider_unverified
  -> run minimal prompt
  -> cancel a long mocked run
  -> inspect run history
  -> inspect estimated vs actual token count when provider reports usage
  -> export with "include LLM history" off omits request/response payloads
  -> key is absent from DB responses and logs
```

### LLM-2: Context Preview And FTS Recall

Goal:
- build previewable, scoped context packages before generation.

Build:
- context builder;
- context preview API;
- SQLite FTS indexes for notes/entities/public snippets/session transcript/memory candidates where appropriate;
- FTS update triggers or service-level index writes with trigger safety net;
- recall API;
- token estimate utility;
- public-safe and GM-private context modes.

Tests:
- public-safe mode excludes private notes/entity fields;
- normal mode excludes raw proposals and rejected options;
- active planning markers are included as planning text;
- expired markers are excluded;
- context preview stores source revisions and a canonical sourceRefHash;
- source revision/hash drift returns HTTP 409 instead of silently rebuilding context;
- recall prefers canon/approved records over draft/proposal records;
- FTS create/update/delete stays coherent for indexed records.

Acceptance:

```text
select scene and task
  -> preview shows included/excluded sources
  -> public-safe preview excludes GM-only data
  -> recall question returns cited snippets
  -> rejected proposal is absent unless include_proposal_history mode is selected
```

### LLM-3: Branch Proposals And Planning Markers

Goal:
- support the "give me several directions, I choose one" workflow.

Build:
- `scene.branch_directions` template;
- structured response normalization into proposal sets/options;
- proposal card API actions;
- planning marker creation from selected option;
- context builder integration for active planning markers.

Tests:
- structured response creates proposal set/options;
- fenced JSON and one schema-repair retry are handled;
- schema-repair retry creates a child run with `parentRunId`;
- malformed JSON after retry fails with `parse_failed` and no proposal records;
- selecting option does not canonize;
- selecting option supersedes sibling options;
- selecting a superseded sibling later allows multiple selected options and does not demote the first selected option;
- planning marker includes selected direction without unplayed events;
- future normal context includes marker but excludes raw proposal bodies.

Acceptance:

```text
run branch directions for a scene
  -> receive 3-5 proposal options
  -> adopt option 2
  -> sibling options are marked superseded
  -> active planning marker is created
  -> next context preview includes planning marker
  -> next context preview excludes other proposal bodies
```

### LLM-4: Memory Inbox And Canonization

Goal:
- turn played events into approved campaign memory.

Build:
- `session.extract_canon_candidates` task;
- memory candidate list/actions;
- backend target revision capture when candidates are persisted;
- apply behavior for session summary/private note/entity patch where minimal target support exists;
- transcript event writes for approvals/applications;
- canonization draft from selected proposal.

Tests:
- multi-target output is split into atomic candidates;
- targetless candidates skip OCC and create new memory entries/notes;
- targeted candidates copy target revision from the context package source ref that fed the model;
- candidates whose target was not in the model context are not auto-applicable target patches;
- pending candidates do not appear as canon;
- approve/apply writes durable target state;
- apply is idempotent in one transaction;
- stale target revision returns HTTP 409 instead of clobbering newer GM edits;
- rejected candidates are excluded from normal context;
- canonized selected proposal appears as canon/approved state.

Acceptance:

```text
submit rough session notes
  -> model returns memory candidates
  -> GM approves one NPC relationship update
  -> entity/note/session memory updates after apply
  -> future context includes approved update
  -> rejected candidate stays out of context
```

### LLM-5: GM Assistant UI

Goal:
- make the workflow usable from `/gm`.

Build:
- assistant panel;
- task picker;
- provider status;
- context preview drawer;
- run button/output viewer;
- proposal cards;
- planning marker list;
- memory inbox;
- run history.

Tests:
- frontend unit tests for API calls and state transitions;
- e2e with mocked provider showing branch proposal/adopt/context-preview flow;
- e2e public-safe recap draft does not publish automatically.

Acceptance:

```text
GM opens assistant panel
  -> sees provider status
  -> previews context
  -> runs branch proposal task
  -> adopts one option
  -> sees planning marker
  -> runs canonization task
  -> approves memory candidate
  -> /player remains unchanged throughout
```

### LLM-6: Player-Safe Recaps And Snippet Drafting

Goal:
- produce public-safe drafts that still require explicit publish.

Build:
- `session.player_safe_recap` task;
- `draft.public_snippet` task;
- public-safe context enforcement;
- create `PublicSnippet` from reviewed draft.

Tests:
- public-safe context excludes private notes and hidden fields;
- draft creation does not mutate player display;
- publish still goes through existing `show-snippet`/scene publish APIs.

Acceptance:

```text
run player-safe recap
  -> preview contains public-safe sources only
  -> draft is created
  -> GM creates PublicSnippet
  -> /player changes only after explicit publish
```

### LLM-7: Vector Retrieval And Embeddings

Status:
- deferred.

Add only after FTS recall proves insufficient.

Build later:
- embedding provider capability;
- per-campaign embedding index;
- background reindex;
- hybrid retrieval;
- chunk strategy.

Do not block LLM-1 through LLM-6 on this.

## 11. Backend Placement

Suggested modules:

```text
backend/app/llm/
  __init__.py
  provider_profiles.py
  client.py
  context_builder.py
  recall.py
  task_registry.py
  response_normalizer.py
  proposals.py
  planning_markers.py
  memory_inbox.py
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
- context builder public/private filtering;
- proposal lifecycle transitions;
- planning marker context eligibility;
- memory candidate approve/apply/reject transitions;
- recall ranking and status filtering;
- API key redaction.

Frontend tests:
- task picker renders task registry;
- context preview shows included/excluded sources;
- proposal card actions call correct APIs;
- memory inbox action flow;
- no player-display publish after LLM draft generation.

E2E tests:
- mocked provider branch proposal/adopt flow;
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
- no model output applied without explicit GM action;
- no generated public content published automatically;
- no rejected/raw proposals in normal context;
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
LLM-0 data foundations
  -> LLM-1 provider harness
  -> LLM-2 context preview for selected scene
  -> LLM-3 branch proposals and planning marker
```

This proves the product's differentiating loop:

```text
Ask for several possible directions.
Choose one.
Carry only that selected planning direction forward.
Do not pollute canon or future context with rejected branches.
```

Then add canonization:

```text
LLM-4 memory inbox
  -> approve played facts
  -> future context uses approved canon
```
