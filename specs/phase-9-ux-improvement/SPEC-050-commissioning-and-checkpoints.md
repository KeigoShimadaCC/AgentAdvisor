---
id: SPEC-050
title: Commissioning and checkpoints — the first five minutes and the two signatures
phase: 9
status: implemented
depends_on: [SPEC-046, SPEC-048]
parallel_with: [SPEC-049]
north_star_refs: ["3", "14", "15"]
last_updated: 2026-08-06
---

# SPEC-050 — Commissioning and checkpoints: the first five minutes and the two signatures

## Summary

The three moments a human is actually in the loop: starting a case, signing the scope, and signing
the delivery. Today the first is a disabled button reading "Framing…" for minutes with no case to
look at and no recovery from a reload; the second is a 539-line form-wall with five expanded
sections of equal weight; the third puts four uncertainty instruments between the answer and its
reasons. This spec makes commissioning immediate and recoverable, replaces the promised effort times
with measured ones, leads the scope sheet with one question, and leads delivery with one honest
sentence.

## Motivation

North star Section 14 (human role and approval boundaries) makes these the moments that carry
authority; Section 3 (product promise) is what the effort chips currently break, promising "roughly
10–20 minutes" for a standard case when the first verified real case took 191 minutes and 1.58M
tokens. A product whose pitch is epistemic honesty cannot open with an estimate off by an order of
magnitude. Section 15's step 2 — "platform presents its interpretation, alternatives, and any
critical clarifications" — is well served by the scope sheet's content and poorly served by
presenting all of it at once with nothing ranked.

## Scope

- `frontend/src/screens/NewDecision/NewDecision.tsx`:
  - consume SPEC-046's `202`: route to the case surface immediately and stream from there;
  - draft-persist the prompt and effort selection to `localStorage` on every keystroke, cleared on
    successful creation;
  - narrate intake and framing as the first demonstration of the method, using SPEC-047's narrator;
  - two questions that route the whole experience and nothing else: **what should I hand you** — a
    one-page answer or a full advisory brief, which sets SPEC-048's default altitude — and **watch
    or notify**, sit with the deliberation or be pinged, which SPEC-051 consumes. Both are
    preferences, not case data: neither is written into the case.
- `frontend/src/copy/effort.ts` — effort profiles whose time ranges are computed from recorded
  history via `MemoryStore.prior_cases()` (p50–p90 per profile), served by SPEC-046's
  `GET /api/effort-history`, and labelled as measured. With no history, honest fallback copy
  rather than a fabricated number. Removes the hardcoded ranges from `terms.ts`.
- `frontend/src/screens/ScopeCheckpoint/ScopeCheckpoint.tsx` — progressive disclosure:
  - leads with the restatement as a binary — "Here's the decision I'll actually answer. Is that
    right?" — with sign and adjust as the two actions;
  - options, outline, ground rules and effort collapse under "Adjust scope", each showing a count of
    what it contains;
  - the `NEEDS_YOU` consequence line promoted into the subhead;
  - **an extension slot for phase 8 SPEC-038's objective weights**, documented and empty here, so
    SPEC-053 fills it without a second restructure.
- `frontend/src/screens/Delivery/Delivery.tsx` — answer first:
  - one synthesised honest sentence composed from the four measures, above everything;
  - key reasons and tripwires next; the four uncertainty encodings move one click down under "How
    sure is this?", unchanged in substance;
  - send-back requires confirmation naming what it spends, since `MAX_FINAL_REVISIONS = 1`;
  - **an extension slot for phase 8 SPEC-041's typed action plan**, documented and empty here.

## Out of scope

- Filling either extension slot (SPEC-053, after phase 8 verifies).
- Notifications and the watch-mode experience itself (SPEC-051); this spec only captures the
  preference.
- The uncertainty widgets' internals, which are SPEC-035's and are moved, not rewritten.
- Any change to `FramingApproval` / `FinalApproval` artifact shapes or to the control layer's
  approval semantics.

## Design

The load-bearing property of the scope redesign is that **disclosure must not change the record**.
The signed artifact has to be identical whether a user signs immediately or expands every section,
because otherwise the UI has quietly introduced two classes of approval and the audit trail stops
meaning one thing. The existing stub-mode lifecycle test already asserts disk state at every gate,
so this is verified by driving both paths and comparing the written YAML.

Effort estimates are computed rather than authored because an authored number is exactly what is
wrong today. Deriving p50–p90 from `prior_cases()` makes the estimate self-correcting as real runs
accumulate, and the honest-fallback path means an empty history produces a true statement instead of
a confident one.

The two extension slots exist so this spec can proceed in parallel with phase 8. Both are places
where phase 8 adds content to a surface this spec restructures; declaring the seam now costs one
documented component boundary and avoids restructuring the same two screens twice.

## Deliverables

- [x] `NewDecision.tsx` — immediate routing on 202, draft persistence, intake/framing narration,
      output-shape and watch-or-notify preferences
- [x] `frontend/src/copy/effort.ts` + `GET /api/effort-history`; hardcoded ranges removed from
      `terms.ts`
- [x] `ScopeCheckpoint.tsx` — restatement-first disclosure, consequence subhead, objective weights
- [x] `Delivery.tsx` — answer-first order, uncertainty behind disclosure, send-back confirmation,
      action-plan slot wired
- [x] Component tests for both sheets and the commissioning flow
- [x] `frontend/e2e/stub.spec.ts` extended: fast-sign and full-review paths produce identical
      artifacts

Deviations, all deliberate:

- **Ground rules stay outside the disclosure.** The sheet said options, outline, ground rules and
  effort all collapse. Confirming every ground rule is a precondition of signing (SPEC-034's
  `allGroundRulesConfirmed`), so collapsing them would hide required work behind a control labelled
  "adjust" — a dark pattern, and one that would make a fast sign impossible rather than fast. The
  other three collapse; ground rules sit between the restatement and the signature, which is the
  order the user works in.
- **The clarification interview moved to the scope sheet.** `InterviewCards` used to render inside
  commissioning after the create call returned. With immediate routing there is no such moment. The
  questions belong to scope and the scope sheet already asks them.
- **The objective-weights slot needed no slot.** Phase 8's SPEC-038 merged while this phase was in
  flight, so the section is real rather than reserved. It is inside the disclosure and counted in
  its summary.
- **The action-plan slot revealed a live defect.** `MonitoringPanel` has existed since SPEC-042 —
  written, styled, and never rendered by anything. It is wired here rather than left as a slot,
  because a component that exists and is not reachable is not a seam, it is a missing feature.

## Acceptance criteria

- [x] **Signing fast and signing after expanding every section produce identical
      `framing_approval.yaml`**, asserted in stub mode against disk.
- [x] Reloading mid-commission restores the prompt and effort selection; a successful creation
      clears the draft.
- [x] Choosing "one-page answer" lands the case on the Answer altitude and "full advisory brief" on
      Reasoning; neither preference is written into the case directory.
- [x] After `POST /api/cases` the case surface renders and narrates intake before framing completes;
      no disabled-button wait remains.
- [x] No hardcoded minute range remains in `frontend/src/copy/`; ranges render as measured p50–p90
      from recorded history, and an empty history renders the honest fallback rather than a number.
- [x] The scope sheet shows the restatement and its actions above the fold with the adjustable
      sections collapsed and counted; the consequence line renders in the subhead.
- [x] Delivery renders the honest sentence, then key reasons, then tripwires, with the four
      encodings behind disclosure; send-back requires a confirmation naming the cap and is disabled
      once spent.
- [x] Axe, visual-regression and terminology-guard passes on both sheets and commissioning;
      `make frontend-check`, `make e2e-frontend` and `make check` green.

## Verification plan

```
cd frontend && npm test -- NewDecision ScopeCheckpoint Delivery effort
make frontend-check && make frontend-build
E2E_MODE=stub npx playwright test --config=e2e/playwright.config.ts
E2E_MODE=fixture npx playwright test --config=e2e/playwright.config.ts
make e2e-frontend
make check
```

## Verification results

| Command | Result |
| --- | --- |
| `cd frontend && npm test` | 24 files, **263 passed** (was 231; +32 for effort, the honest sentence, commissioning, the blocked signature) |
| `make frontend-check` | green |
| `make frontend-build` | green — 355.22 kB JS |
| `E2E_MODE=fixture …` (four browser projects) | **130 passed** in 3m18s |
| `E2E_MODE=replay …` | **9 passed** |
| `E2E_MODE=stub …` | **6 passed** — including the disclosure invariant |
| `make check` | **946 passed**, 18 deselected (+5 for `/api/effort-history`) |

### Disclosure must not change the record

The load-bearing property, and the one nobody would catch by reading the code — both paths run the
same handler. `stub.spec.ts` drives the real UI twice against the real orchestrator: once signing
without touching "Adjust scope", once after expanding it and confirming every section is on screen.
It then reads `shared/framing_approval.yaml` off disk for both and compares them with identity and
clock stripped.

The first version of that test passed while being nearly vacuous: `framing_approval.yaml` is a short
record, and normalising away `approved_at`, `case_id` and `schema_version` left 71 characters. The
test now asserts `decision`, `approved_by`, `edits` and `clarification_answers` all survive
normalisation *before* comparing, so a filter that strips the record cannot produce a green run.
It also dropped from 1.1 minutes to 16 seconds by polling for the artifact instead of waiting on a
pipeline stage the stub backend had already run past.

### Effort times are measured, not authored

`GET /api/effort-history` walks completed cases, reads each one's `budget_profile` from
`control_meta.yaml` and its duration from the audit stream, and returns p50/p90 per profile with a
sample count. Design choices worth recording:

- **Only `done` cases count.** A case still running has a duration, but not a duration *of a
  completed case*; quoting it would understate what finishing costs, which is the same failure as
  the authored estimate.
- **Nearest-rank, not interpolating.** With the two or three runs a real history starts with, an
  interpolating percentile invents a number between two observations and reports it with the
  authority of a measurement. Every value returned is a duration some case actually took.
- **Three honesty states in the UI**, not two: enough history → a range labelled measured; one or
  two runs → the range labelled as too few to generalise from; nothing → "not measured yet" and a
  note saying there is nothing honest to promise yet.

`PHASE_TIME_RANGES` was also deleted — six authored per-phase ranges, unreferenced by any screen,
carrying the same false promise ("3–15 minutes" for investigation).

### Three bugs the tests found

1. `formatDuration(30)` returned "1 min", because it rounded to minutes before checking for the
   sub-minute case — a longer claim than the measurement supports. It compares on seconds now.
2. `formatDuration(3600)` returned "60 min" rather than "1h", from a threshold at 90 minutes that
   did not match the intent.
3. The test that asserts no authored minute range survives in `copy/` failed on `terms.ts` and found
   `PHASE_TIME_RANGES`, which nothing had referenced since it was written.

## Open questions

Both resolved during implementation.

- **The honest sentence's precision** — settled by making the composition rule a tested property
  rather than a review note: the sentence contains **no digits at all**, asserted. It names which
  measures were assessed, describes each in coarse words, and names the ones that were not. There is
  no arithmetic, because averaging a source-strength grade with a stability share produces a figure
  with no referent — exactly the false precision the four separate encodings exist to prevent. A
  not-assessed measure is stated as not assessed, which is both the honest reading and the useful
  one: it tells the reader what to go and check.
- **Where measured effort is served from** — a sibling `GET /api/effort-history`, as
  recommended, owned by SPEC-046 (added to its scope on 2026-08-06; the gap was that no sheet had
  owned the read at all).
  Calibration is the system's forecasting track record; folding wall-clock timing into it would make
  a single-purpose contract answer two unrelated questions.
