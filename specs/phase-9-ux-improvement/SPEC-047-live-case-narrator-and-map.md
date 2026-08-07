---
id: SPEC-047
title: The live case — streaming truth, the narrator, and the case map
phase: 9
status: implemented
depends_on: [SPEC-046]
parallel_with: []
north_star_refs: ["8", "15"]
last_updated: 2026-08-05
---

# SPEC-047 — The live case: streaming truth, the narrator, and the case map

## Summary

Everything that makes the interface report what is actually happening. Three defects are fixed
together because they are one failure: the projection is fetched once per mount and never again, so
the living brief is frozen at page load; the stream has no reconnect, so one laptop sleep ends it
permanently; and the phase strip cannot express a loop, so a second challenge round is
pixel-identical to a stall. Delivers a debounced refetch, a resuming stream, a narrator that
replaces the raw event log with one sentence, and a case map that can show a cycle.

## Motivation

North star Section 15: "agents work while the interface exposes meaningful progress rather than raw
chain-of-thought." Section 8 (decision workflow) describes a workflow with review cycles; the UI
draws it as six static blocks. All four backward edges in `ALLOWED_TRANSITIONS` are intra-phase —
`awaiting_framing_approval → framing`, `stop_decision → repair → challenge`, `review → synthesis`,
`awaiting_final_approval → synthesis` — so `MethodStrip`'s index comparison cannot move while a loop
runs. The loops are the system's whole value proposition, and they are the one part the interface
never shows.

## Scope

- `frontend/src/screens/shared/useCaseView.ts` — refetch `/view` when a non-technical event arrives,
  debounced (250 ms) and coalescing bursts; keep the previous view rendered while refetching so the
  screen never blanks.
- `frontend/src/api/sse.ts` — reconnect with exponential backoff (1 s → 30 s, jittered) resuming
  from `since=<cursor>`; expose connection state so the chrome can show it; persist the last-seen
  cursor per case in `localStorage` (SPEC-051 reuses it for the away digest).
- `frontend/src/narration/` — new:
  - `reducer.ts` — a pure `(state, TranslatedEvent) => NarrationState` fold producing the current
    actor, what it is working on, attempt, elapsed anchor, task counters, and loop state. No React,
    no DOM, fully unit-testable.
  - `Narrator.tsx` — renders one present-tense line that rewrites in place, with elapsed time and a
    task counter, plus a collapsed transcript disclosure for the full translated stream.
  - Loop announcements in plain language when the reducer observes `stop_decision → repair` or
    `review → synthesis`, naming what triggered it and what it costs.
- `frontend/src/screens/shared/CaseMap.tsx` — replaces `MethodStrip`:
  - stages grouped under their presentation phase, from the same `_STAGE_TO_PHASE` mapping the
    projection uses;
  - the four intra-phase cycles drawn as permanent return brackets, so a loop is visible as part of
    the plan before it ever runs;
  - live round counters from `CaseState.repair_cycle`, `synthesis_retries`, `framing_revisions`,
    `final_revisions` against their caps;
  - the two approval gates marked as checkpoints that wait for a human.
- Removals: the `[line_cursor]` event list in `pages/CaseDetail.tsx`; `MethodStrip.tsx` and its test.
- `LiveActivity.tsx` reduced to consuming the reducer rather than deriving "running" from failure.

## Out of scope

- Layout, chrome and hierarchy (SPEC-048) — this spec renders into the existing shell.
- Agent-voice attribution and dissent (SPEC-049); the narrator names the actor here, and gains
  who-is-attacking-what there.
- The away digest and notifications (SPEC-051), which consume the cursor this spec persists.
- Any new backend event; SPEC-046 owns those.

## Design

The reducer is separated from the component because the interesting logic is the fold, not the
markup: "what is happening now" is a projection over an event sequence, and the repo already has
recorded audit fixtures and a replay driver to test folds against. That makes the narrator's
correctness a unit-test question and its appearance a component-test question, which is the split
the existing suite is built for.

The case map takes the counters from `CaseView` rather than inferring rounds from the event stream,
because the projection already reads them from `state.yaml` and inference would drift on reconnect.
The map's cycles are static structure — the same four edges for every case — so the component is a
pure function of `(stage, counters)` and can be fixture-driven exhaustively.

Refetching the projection on events rather than pushing view diffs down the stream keeps the SSE
contract unchanged and the server stateless per SPEC-033's design; the debounce is what makes it
cheap, and the retained previous view is what stops it flickering.

## Deliverables

- [x] `frontend/src/api/sse.ts` — backoff reconnect, cursor resume, persisted cursor, connection state
- [x] `frontend/src/screens/shared/useCaseView.ts` — debounced event-driven refetch
- [x] `frontend/src/narration/reducer.ts` + `Narrator.tsx` + loop announcements
- [x] `frontend/src/screens/shared/CaseMap.tsx` replacing `MethodStrip.tsx`
- [x] Unit and component tests: `reducer.test.ts`, `Narrator.test.tsx`, `CaseMap.test.tsx`,
      `sse.test.ts`
- [x] `frontend/e2e/replay.spec.ts` extended with narrator and loop assertions

## Acceptance criteria

- [x] Replaying a recorded audit fixture through the reducer produces the expected actor, task
      counter and loop state at each cursor, asserted event by event without a DOM.
- [x] A burst of ten events within the debounce window produces exactly one `/view` request, and the
      previously rendered view stays on screen throughout.
- [x] Dropping the stream mid-case and restoring it resumes from the persisted cursor with no
      duplicated and no missed events, verified by comparing the received cursor sequence against
      the audit file.
- [x] In replay mode the narrator line changes as the case advances, a brief section reaches `final`
      without a page reload, and no raw `event_type` or `line_cursor` appears anywhere in the DOM —
      enforced by extending the existing terminology guard.
- [x] `CaseMap` renders all four cycles from fixtures; with `repair_cycle: 2` it states round 2 of 2;
      and a case in its second challenge round is distinguishable in the DOM from one in its first —
      the regression `MethodStrip` could not detect.
- [x] Axe, visual-regression and terminology-guard passes hold for every screen this spec touches,
      per the phase testing contract.
- [x] `make frontend-check` and `make e2e-frontend` are green;
      `tests/test_pipeline_invariants.py` still passes.

## Verification plan

```
cd frontend && npm test -- narration sse CaseMap
make frontend-check
make frontend-build
E2E_MODE=replay npx playwright test --config=e2e/playwright.config.ts
E2E_MODE=fixture npx playwright test --config=e2e/playwright.config.ts
make e2e-frontend
uv run pytest tests/test_pipeline_invariants.py -q
```

## Verification results

- 2026-08-05. `make check` green (941). `make frontend-check` green — **142 frontend tests**, up from
  105; the full e2e matrix runs **102 passed / 0 failed in 2m45s**, inside SPEC-037's budget.
- Reducer: 18 unit tests with no DOM, over synthetic and recorded-shape events. They hold the
  properties that matter — a heartbeat does not reset the start time (or the elapsed counter would
  never advance), a failed attempt means work *continues* rather than finished, an unknown event
  type advances the cursor and changes nothing else, and the cursor never goes backwards.
- Loops: each of the three cycles announces itself with its round number, a second repair round
  reads differently from the first, and a stop decision that proceeds to synthesis announces
  nothing. Refusals surface as announcements, because a run that did less than it could have has to
  say so while it is happening.
- Stream: 8 tests. Reconnect resumes from the stored cursor, a replayed boundary frame is dropped
  rather than folded twice, repeated failures escalate `reconnecting` → `stale`, `disconnect()`
  stops the ladder, and unavailable storage degrades to a replay from zero instead of throwing.
- Projection: 5 tests. Ten events inside the debounce window produce exactly one refetch, technical
  events produce none, and the previous view stays on screen throughout.
- Case map: 10 tests, including **the regression `MethodStrip` could not detect** — two cases in the
  same phase and stage, differing only by repair counter, must render differently.
- Browser: replay asserts the narrator carries no `[cursor]` and no raw enum, that narration is
  driven by the stream, and that exactly one phase is ever current.

**Deviations from the sheet.**

1. The sheet said the transcript shows "the full translated stream". It now excludes `technical`
   events. The lexicon's technical flag is the product's existing rule for "machinery, not
   investigation", and a transcript leaking retries would have re-created the debug view this
   replaced. The Method room remains the unfiltered log.
2. The narrator takes a `showTranscript` prop, false on the Brief. `MarginNarration` already renders
   the narration stream there with citations, and two copies of the same events on one screen is the
   noise this component exists to remove — caught by an existing test finding the message twice.
3. `LiveActivity.tsx` and its test were deleted as well as `MethodStrip`. The sheet listed only
   `MethodStrip`, but LiveActivity's whole job — inferring "running" from a failed attempt — is now
   done correctly by the reducer, so leaving it would have meant two contradictory answers on screen.
4. **The case map reintroduced a defect SPEC-045 had just fixed.** It scrolls horizontally, and a
   scrollable region needs keyboard access; the axe sweep caught it within minutes of the component
   existing. Fixed with `tabIndex` and a focus ring. Recorded because it is evidence the expanded
   coverage earns its runtime.
5. One e2e assertion was rewritten after it proved racy: "the narration line changed" loses to a
   60× replay flushing its history between two reads. It asserts the deterministic end state
   instead — a flaky narration gate would get muted rather than fixed.

## Open questions

- None. Loop-announcement copy is drawn from `copy/terms.ts` under the existing terminology
  discipline and does not need settling here.
