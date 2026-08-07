---
id: SPEC-055
title: Resilience — degraded states, storage failure, live-region announcement, and budgets
phase: 9
status: implemented
depends_on: [SPEC-046, SPEC-047, SPEC-048]
parallel_with: [SPEC-052]
north_star_refs: ["5", "15"]
last_updated: 2026-08-07
---

# SPEC-055 — Resilience: degraded states, storage failure, live-region announcement, and budgets

## Summary

Phase 9 turns a page-load-and-poll interface into a long-lived streaming one that survives a
three-hour run, and every sheet before this one specifies the happy path. This spec specifies what
happens when it does not hold: the stream is gone, the service is down, browser storage is
unavailable, a worker died at intake, two tabs are open on one case, or the case has produced
thousands of events. It also fixes an accessibility defect the streaming work would otherwise ship —
a live-updating narrator with no announcement policy — and sets the performance and test-suite
budgets the phase has to stay inside.

## Motivation

North star Section 5's design principles and Section 15's promise of meaningful progress both fail
silently under partial failure, and silent failure is worse here than elsewhere: a frozen brief and
a finished brief look identical. Concretely, today the app has zero `localStorage` usage and phase 9
introduces four separate dependencies on it (SPEC-047's cursor, SPEC-048's altitude, SPEC-050's
draft, SPEC-051's reactions); `useCaseView` accumulates events in an unbounded array copied on every
append, which SPEC-046's progress heartbeats will add thousands to; and the only live-region markup
in the entire frontend is a single `role="status"` on the scope sheet, so a narrator that rewrites in
place would be either invisible or maddening to a screen-reader user.

## Scope

- **Connection states.** A single connection model — connected, reconnecting, stale, offline —
  surfaced in SPEC-048's chrome. `stale` is entered when reconnect exhausts its backoff, and the
  brief is explicitly marked as possibly out of date rather than presented as current. Manual retry
  offered; recovery clears the state and refetches the projection.
- **Service unavailable.** A first-class disconnected view for the library and case surfaces
  replacing today's red `<p className="error">`, distinguishing "the service is not running" from
  "this case does not exist" from "this case is locked by a writer", using the existing
  `{error, detail, case_stage}` model and its 404/409/422/500 taxonomy.
- **Storage resilience.** A `safeStorage` wrapper for all four `localStorage` consumers: feature-
  detects availability once, degrades to in-memory for the session when storage is unavailable
  (private mode, disabled, quota exhausted), never throws into a render path, and never blocks a
  feature outright — a lost draft or altitude preference is a downgrade, not a failure.
- **Stalled case detection.** A case created by SPEC-046's `202` whose worker never emits an event
  within a bounded window is surfaced as stalled, with the existing `POST /resume` offered. Covers
  the gap between "created" and "running" that non-blocking creation opens.
- **Multi-tab behaviour.** Storage events reconcile altitude and reactions across tabs on the same
  case; two streams on one case are permitted and must not double-count in the away digest.
- **Live-region announcement policy.** The narrator is `aria-live="polite"` and announces
  transitions, not heartbeats — a new role starting, a loop entered, a gate reached — with the
  per-second elapsed timer excluded from announcement. Gate arrival is `assertive`. Documented once
  and applied wherever content updates without user action.
- **Budgets**, recorded and enforced:
  - client: the event buffer is bounded with the narrator reducer folding older events into state
    rather than retaining them, so memory is O(1) in case length;
  - test suite: the theme × viewport matrix from SPEC-045 must keep `make e2e-frontend` inside
    SPEC-037's 10-minute budget — visual and axe runs are scoped to one representative project per
    dimension rather than the full cross-product;
  - screenshot determinism: animations disabled, fonts pinned, and a documented pixel threshold, so
    visual regression does not become a flaky gate that the phase learns to ignore.

## Out of scope

- Retrying failed control POSTs automatically. Approvals are signed human acts; a failed approval is
  reported and re-offered, never replayed.
- Offline-first or service-worker caching. The service is localhost; "offline" here means the
  service is down, not the network.
- Changing the service's error model or status codes (SPEC-033 owns it); this spec consumes it.

## Design

The connection model is one state machine consumed by the chrome rather than per-screen error
handling, because the failure is global to a case and the user's question is always the same one:
is what I am looking at current? `stale` exists as a distinct state from `reconnecting` precisely
because it is the dangerous one — the screen still shows a plausible brief, and only an explicit
marker distinguishes it from a live one.

The announcement policy is written here rather than in SPEC-047 because it is a cross-cutting rule
with a trap: the obvious implementation puts `aria-live` on the narrator line, which then announces
the elapsed timer every second. Separating transitions from heartbeats is the whole design, and it
applies equally to the away digest, toasts and gate arrival.

The budgets are in scope because two of them are how this phase fails quietly. An unbounded event
buffer is invisible until a 191-minute case, and a visual-regression suite that is slow and flaky
gets skipped rather than fixed — at which point SPEC-045's harness has cost time and bought nothing.
Both are cheap to bound now and expensive to retrofit.

## Deliverables

- [x] Connection state model + chrome indicator (SPEC-047 shipped the model; this consumes it)
- [x] `frontend/src/screens/shared/Failure.tsx` — disconnected / not-found / locked / invalid
- [x] `frontend/src/lib/safeStorage.ts` and migration of all **seven** storage consumers onto it
- [x] Stalled-case detection with the resume affordance
- [x] `frontend/src/lib/announce.ts` — the policy as data, applied across the app
- [x] Budgets: bounded event buffer; e2e matrix scoping; deterministic screenshots

Deviations, all deliberate:

- **Seven storage consumers, not four.** The sheet counted the four that existed when it was
  written; SPEC-050 added the commission draft *and* the presence preference, and SPEC-052 added
  theme and onboarding. Each had written its own try/catch — six chances to get it wrong and no
  shared answer to what should happen when storage is absent.
- **The client could not tell a dead service from a 404 at all.** `fetchJSON` let a rejected
  `fetch` escape as a raw `TypeError`, so "the service is not running" rendered as "Failed to
  fetch". Classification had to be added before any view could consume it.
- **`liveRegionProps` grew a `withRole` option** after axe failed six routes at once — see below.

## Acceptance criteria

- [x] A brief whose stream is refused is explicitly marked as not live rather than presented as
      current; retry recovers without a reload. (`stale` itself arrives after the full ~61s backoff
      ladder and is asserted directly in `sse.test.ts`, not by making an e2e test wait a minute.)
- [x] Service down on first load renders the disconnected view, not a red paragraph; a missing case
      renders not-found; a locked case renders the locked state with its `case_stage`.
- [x] With `localStorage` throwing on read, write and remove, every one of the **seven** consumers
      still functions for the session and no error reaches a render path.
- [x] A case whose worker never starts is surfaced as stalled within the bounded window and offers
      resume; a normally running case is never marked stalled.
- [x] The narrator announces transitions and does **not** announce the elapsed timer; gate arrival is
      assertive and everything else polite — asserted structurally and swept in e2e.
- [x] Replaying a 3,000-event case leaves the retained buffer bounded and the narrator correct.
- [x] The matrix completes in **8m20s** against SPEC-037's 10-minute budget, and the visual suite
      passed **four consecutive full runs** with no pixel diff — flake, not just failure, is the
      gate.

## Verification plan

```
cd frontend && npm test -- safeStorage connection narration
make frontend-check && make frontend-build
E2E_MODE=stub npx playwright test --config=e2e/playwright.config.ts   # kill-worker hook drives stalled + stale
E2E_MODE=replay npx playwright test --config=e2e/playwright.config.ts # 3k-event buffer bound
time make e2e-frontend                                                # budget
E2E_MODE=fixture npx playwright test --config=e2e/playwright.config.ts visual.spec.ts --repeat-each=2
make check
```

## Verification results

| Command | Result |
| --- | --- |
| `cd frontend && npm test` | 33 files, **414 passed** (+25) |
| `make frontend-check` | green |
| `make frontend-build` | green |
| `E2E_MODE=fixture …` (five browser projects) | **189 passed** in **8m20s** |
| visual suite, four consecutive full runs | **39 passed** each, no pixel diff |
| `E2E_MODE=replay …` | **12 passed** |
| `E2E_MODE=stub …` | **6 passed** |
| `make check` | **952 passed**, 18 deselected |

### The flake gate did its job, and cost four wrong hypotheses

The sheet's demand — "the visual suite passes **twice consecutively**, flake not just failure is the
gate" — is the single most valuable line in it. The suite passed once and failed on the second run,
on a different route each time, and each individual route passed twelve times in a row when run
alone. That is what a load-sensitive race looks like, and it is exactly how a visual gate earns a
reputation for being unreliable and gets muted.

Four fixes, three of which were real defects and only the last of which was the actual cause:

1. **The settle wait was the app shell, not content.** The shell paints before the case loads, so
   under load the screenshot caught a skeleton. (Also fixed in `density.spec.ts`, which had the same
   defect and had flaked once.)
2. **`.narrator-elapsed` was never frozen.** The freeze list named `.live-activity-elapsed` and
   `.method-elapsed` — neither of which exists in the app any more — so the one element that ticks
   every second was the one not frozen.
3. **The narrator is not a stable screenshot subject at all.** Its line, counters and announcements
   are a function of stream arrival timing; Playwright's own "two consecutive stable screenshots"
   check said so. It is `display: none` in baselines — not `visibility: hidden`, because its
   *height* grows as announcements accumulate and shifted everything below it.
4. **The actual cause: `position: sticky` with `fullPage`.** Captured by looping until a diff was
   kept, then reading it: content byte-identical, page height 5,022px on the failing run against
   5,017px on the baseline, and the diff was a band at the bottom edge and nothing else. The sticky
   rail and panel are pinned during capture, which also makes the baseline show the whole panel
   rather than whatever fitted in 80vh.

The lesson worth keeping is procedural: the first three were plausible, each shipped, and none of
them fixed it. Reading the diff image took two minutes and answered the question outright.

### Budget

**8m20s** for 189 tests across five browser projects, against SPEC-037's ten minutes. The scoping
that buys it is per-project `grep` (SPEC-045) plus `mobile-dark` restricted to axe (SPEC-052) —
without those the full cross-product is four to six times over. The margin is real but not large;
the next sheet to add routes should re-measure rather than assume.

### `safeStorage` found a real hole

Seven consumers, each with its own try/catch, and none of them agreed on what "unavailable" meant.
The wrapper detects **once** — a try/catch per keystroke on the commission draft is both slow and
pointless, since storage does not come back mid-session — and degrades to an in-memory map for the
session, so every feature keeps working within the tab. Settings says so, rather than letting a user
discover it by losing a setting twice.

### An accessibility regression the policy itself introduced

Applying `liveRegionProps` put `role="status"` on the narrator's `<li>` elements, which replaces
`listitem` and breaks the list — axe failed **six routes at once**. The same class of defect as the
`role="group"` on a `<ul>` in SPEC-045. `liveRegionProps` now takes `withRole: false` for elements
whose implicit role is load-bearing; `aria-live` alone is sufficient, since the role only adds an
implicit politeness that is being set explicitly anyway.

### The event buffer

Retained at 500, and the reducer folds every event regardless — so a 3,000-event case keeps correct
counters while holding 500 objects. The old code was also O(n²): it copied the whole array on every
append. Invisible until exactly the 191-minute case the product is built for.

## Open questions

- **The stalled-case window** — set to **90 seconds**, recorded in `useCaseView.ts` with its
  reasoning. Deriving it from a measured p90 time-to-first-event is the better idea and is not yet
  possible: `GET /api/effort-history` (SPEC-050) measures *total* duration, not time to first event,
  and adding that measurement is a service change this phase's constraint does not allow. Ninety
  seconds is roughly an order of magnitude above the slowest first invocation observed, and the
  asymmetry is deliberate — a false "stalled" on a working case is worse than a late one on a broken
  case, because it teaches people to ignore the signal. Revisit when the history endpoint records
  first-event latency.
