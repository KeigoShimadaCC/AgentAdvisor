---
id: SPEC-055
title: Resilience — degraded states, storage failure, live-region announcement, and budgets
phase: 9
status: draft
depends_on: [SPEC-046, SPEC-047, SPEC-048]
parallel_with: [SPEC-052]
north_star_refs: ["5", "15"]
last_updated: 2026-08-05
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

- [ ] Connection state model + chrome indicator, including the `stale` marker on the brief
- [ ] Disconnected / not-found / locked views over the existing error taxonomy
- [ ] `frontend/src/lib/safeStorage.ts` and migration of all four storage consumers onto it
- [ ] Stalled-case detection with the resume affordance
- [ ] Live-region announcement policy, applied to narrator, digest, toasts and gate arrival
- [ ] Budgets: bounded event buffer; e2e matrix scoping; deterministic screenshot configuration

## Acceptance criteria

- [ ] Killing the service mid-case moves the chrome to `reconnecting`, then `stale` once backoff
      exhausts, and the brief is explicitly marked possibly out of date; restarting the service
      recovers to `connected` and refetches without a reload.
- [ ] Service down on first load renders the disconnected view, not a red paragraph; a missing case
      renders not-found; a locked case renders the locked state with its `case_stage`.
- [ ] With `localStorage` throwing on write and on read, every one of the four consumers still
      functions for the session and no error reaches a render path — asserted by a test that stubs
      storage to throw.
- [ ] A case whose worker never starts is surfaced as stalled within the bounded window and offers
      resume; a normally running case is never marked stalled.
- [ ] With a screen reader, the narrator announces role changes, loop entry and gate arrival and
      does **not** announce the elapsed timer; gate arrival is assertive and everything else polite —
      asserted structurally on `aria-live` attributes and announcement content.
- [ ] Replaying a 3,000-event case leaves the retained event buffer bounded and the narrator correct,
      with no unbounded array retained in `useCaseView`.
- [ ] `make e2e-frontend` completes within SPEC-037's 10-minute budget on the reference machine with
      the full matrix configured, and the visual suite passes twice consecutively with no pixel
      diff — flake, not just failure, is the gate.

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

Not yet executed.

## Open questions

- The stalled-case window. Too short and a slow first invocation is reported as broken; too long and
  the gap SPEC-046 opens stays invisible. Recommend deriving it from the measured p90 time-to-first
  event rather than fixing a constant, and recording the value here before approval.
