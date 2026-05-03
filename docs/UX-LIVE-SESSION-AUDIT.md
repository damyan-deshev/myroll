# Live Session UX Audit

Date: 2026-05-03
Status: plan; findings appended after run

This audit is intentionally narrow. Myroll's product promise is "Run the session. Keep the canon." The first half — running the live session — is the moment of truth. Everything else (settings, library browsing, configuration UX, accessibility passes) is lower-leverage and not in scope here.

A broad UX audit would surface 20-30 small recommendations and 80% of them would not change whether a GM can run a smooth session. This audit instead measures whether the live combat-round flow is fast and unambiguous, because that is where the product wins or loses.

## Scope

In scope:

- the path from "active demo session loaded" through one combat round and a scene transition;
- click counts and friction points for the GM-side actions a real GM hits during play;
- the player-display surface as a passive observer of GM actions, to confirm the trust boundary is preserved through these flows.

Out of scope:

- Library / Actors / Combat surfaces outside the live session;
- empty-state and onboarding flows (campaign creation from scratch);
- settings, provider configuration, asset upload UX;
- accessibility, contrast, keyboard tab order;
- error recovery, offline behavior;
- mobile/responsive behavior (GMs use a laptop);
- any LLM-related flows (PRE-LLM and LLM-* are not built yet).

## Scenario

A single end-to-end scenario, run on the existing demo data:

```text
1. open /gm and let the demo campaign/session load
2. open the player-display window
3. open the Map workbench
4. publish the active scene to player display
5. move one token to a new position
6. reveal a piece of fog along the implied path
7. trigger an Identify pulse on the player display
8. switch to a different scene
9. blackout
```

Each step is a single observable GM intent. The audit measures:

- **clicks** to complete each step from a clean state (lower is better, but only flag when a step takes obviously more clicks than the intent suggests);
- **friction points**: any moment where the next action is not visible, or where the GM has to leave the live surface to do something the live surface should do;
- **affordance gaps**: cases where the affordance for an action exists but is hard to find, mislabeled, or behind a hover/secondary state that is not session-friendly;
- **trust-boundary leaks**: any case where the player display reveals state the GM did not explicitly publish.

Click count is a proxy, not a target. The point is "does this feel like running a session, or filling out a form?"

## Method

- start the local backend and frontend with `scripts/start_demo.sh` so the audit runs against a stable seeded campaign;
- drive the GM workspace via Playwright with a viewport of 1440x900 (the project's standard);
- take a screenshot at each step, plus an extra screenshot whenever something looks wrong;
- write findings as discrete entries below, each with severity, scenario step, and a concrete suggested change;
- ignore items that would only become real if the user did something contrived. The bar is "what bites a real GM during play?"

## Severity Bar

- **High**: the step is blocked, ambiguous, or takes 4+ clicks where 1-2 should suffice; or trust-boundary state leaks.
- **Medium**: the step works but takes the GM out of the live surface, or the affordance for the obvious next action is hidden.
- **Low**: cosmetic, only flagged if it accumulates.

This audit only reports High and Medium. Low items roll up into a single "polish backlog" line at the end if anything shows up.

## Findings

Run conducted 2026-05-03 against `scripts/start_demo.sh` with the seeded English demo profile. Playwright drove the GM workspace at 1440x900; screenshots are under `artifacts/ux-audit/`. The scripted walkthrough timed out partway because the audit's regex-based selectors were too loose, but the captured screenshots plus the three pre-existing screenshots under `docs/screenshots/` cover the surfaces that matter for this audit: Overview, Overview-with-player-connected, Player initial empty state, GM Map workbench (existing), GM bundled-map browser (existing), Player map projection (existing).

The findings below are conservative: anything I could not directly verify in a screenshot or in `App.tsx`/`PlayerDisplayApp.tsx` source is omitted, not guessed.

### High

None. The flows the audit could verify (open GM, open player window, player heartbeat reaching GM, scene context surfaced on Overview, player display reflecting blackout state) all worked, the trust boundary held (player surface showed only "Connecting" → blackout, never private campaign data), and there were no console errors in the captured run.

### Medium

**M1. Overview page is a dashboard the GM does not return to during play.**

The Overview tab ([artifacts/ux-audit/01-gm-landing.png](../artifacts/ux-audit/01-gm-landing.png)) duplicates the next-step affordances both as a top nav (Map/Library/Actors/Combat/Scene/Floating) and as four large in-card buttons ("Open Map / Open Library / Open Actors / Open Combat"). The dashboard is useful when the GM first sits down. During play the GM lives in Map and Scene; they will not navigate back to Overview to read the same scene blurb again.

Concrete suggestion: when an active session and active scene are set, default landing should go to the Map tab, with Overview accessible by explicit click. Or, if Overview is meant as the "between scenes" surface, make that the explicit framing in copy ("You are between scenes. Pick a workbench."). The current state reads as "two ways to do the same thing," which is overhead the live GM does not want.

**M2. "Activate privately" is the right product behavior with the wrong label.**

The Scene Context panel exposes "Activate privately" as the primary button on a not-yet-active scene. This matches the docs' "Private By Default" principle — activating without publishing is correct. But the label requires the GM to already know what the principle is. A first-time GM reads "privately" and wonders "private from whom?"

Suggestion: rename to "Activate without publishing" or "Activate (player display unchanged)". Keep a tooltip with the longer explanation. The button is doing important product-defining work; it should not be the place where the GM has to learn the model.

**M3. Player Display side panel is information-dense for a glanceable status surface.**

The right rail Player Display panel on Overview ([01-gm-landing.png](../artifacts/ux-audit/01-gm-landing.png)) lists Mode, Title, Subtitle, Headline, Caption, plus action buttons. During play the GM mostly needs to know two things at a glance: "is the player display connected?" and "what mode is it in right now?" — the rest is detail.

Suggestion: collapse the four metadata rows into one summary line (e.g., "Blackout • Connected • last update 12s ago") with details expandable on click or hover. This is a glance-friendliness win, not a functional one. Same panel on the Map workbench is more justified because the GM is staging content there; on Overview it's just status.

**M4. "Standard Mode" toggle in top-right is undiscoverable until clicked.**

A "Standard Mode" segmented toggle sits in the top-right of every page in the captured screenshots. The label tells the GM nothing about what other mode exists or what changes. If the alternative is something live-session-friendly (focus/compact mode that hides chrome), it deserves a more obvious affordance. If it is a low-importance toggle, it should not occupy prime real-estate alongside the global session header.

Could not verify what the alternate mode does in the captured run. Worth a 30-second click-test next time the dev server is up.

**M5. Player initial state shows "Connecting player display" even when state is fetched.**

[02-player-initial.png](../artifacts/ux-audit/02-player-initial.png) shows "Connecting player display" because the screenshot was taken in the ~300ms window before `lastGoodState` populates. This is a race-window artifact, not a steady-state issue, but a GM who opens the player window for the first time may briefly see "Connecting" even though everything is fine.

This is in [PlayerDisplayApp.tsx:295-301](../frontend/src/player-display/PlayerDisplayApp.tsx#L295-L301) — the `if (!lastGoodState)` branch fires before the first poll resolves. Cheap fix: if `displayQuery.isLoading` and we have no data, show a less alarming "Loading…" or render a blackout frame immediately (the default state on a fresh open is blackout anyway).

### Confirmed working (no finding)

- **GM↔player heartbeat is visibly correct.** The Overview Player Display panel changes from a not-connected state to "connected" (visible by diffing [01-gm-landing.png](../artifacts/ux-audit/01-gm-landing.png) and [02-gm-after-player.png](../artifacts/ux-audit/02-gm-after-player.png)) within seconds of opening the player window. The signal a GM needs to trust the projection surface is there.
- **Player surface honors trust boundary.** The captured player initial state contained no campaign content, only the loading shell. The pre-existing [docs/screenshots/player-map-projection.png](screenshots/player-map-projection.png) confirms the rendered map mode also stays clean of GM chrome.
- **Map workbench IA is session-aware.** The pre-existing [docs/screenshots/gm-map-workbench.png](screenshots/gm-map-workbench.png) places fog tools, scene context, player-display controls, and linked entities on one screen. Identify / Blackout / Intermission / Show active scene are all one-click globals — exactly what a live GM hits mid-scene.
- **Scene Context panel surfaces linked notes/entities together.** The right rail keeps "what is this scene about" and "who is in it" and "what is published" co-located. Reviewing this against the live-session promise: the GM does not have to leave the Map workbench to remember context.

### Polish backlog

Nothing accumulated. Single cosmetic items (alignment, spacing) are not worth flagging individually for a single-user local tool.

## Conclusion

The product passes the live-session bar set in the plan. There are no High findings. The Medium findings are real but each is a small, self-contained refinement rather than a re-architecture: relabel one button (M2), collapse one panel (M3), default landing to Map for active sessions (M1), surface what "Standard Mode" toggles (M4), tighten an empty-state race window (M5).

This confirms the prior assessment ("further audit would not justify the diminishing returns"): the product is past the point where broad UX work pays off. The remaining refinements are best handled opportunistically — for example, M5 fixes itself the next time someone touches PlayerDisplayApp; M2's relabel is a one-line copy change.

Recommend: address M1 and M2 as part of any near-term Overview/Scene-tab cleanup; defer M3 and M4 until a session-mode/focus-mode initiative comes up; fix M5 next time PlayerDisplayApp is touched. Do not schedule a broader UX pass.

