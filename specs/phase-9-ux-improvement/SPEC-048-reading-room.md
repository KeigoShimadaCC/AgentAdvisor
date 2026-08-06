---
id: SPEC-048
title: The reading room — shell, persistent chrome, hierarchy, and altitudes
phase: 9
status: implemented
depends_on: [SPEC-045, SPEC-047]
parallel_with: []
north_star_refs: ["5", "15"]
last_updated: 2026-08-06
---

# SPEC-048 — The reading room: shell, persistent chrome, hierarchy, and altitudes

## Summary

The visual restructure, and the largest sheet in the phase. Replaces the single stacked column with
a three-region shell, puts the decision question into persistent chrome — the page heading is
currently `view.case_id`, so users read a slug like `case-014-should-i-take-the-ser` — ranks the
brief into three levels of weight instead of one, and adds the Answer / Reasoning / Method altitude
control that serves the ask-and-answer audience and the in-it audience from one surface. The
direction is a reading room rather than a dashboard: the output is an argument, so the reference is
a well-set document with an apparatus around it, not a grid of cards.

## Motivation

North star Section 15: commissioning a consulting engagement, not operating an agent framework;
"the user should not need to manage seven agents manually." Today the case surface opens with a
definition list whose rows are Phase, Stage, Status and `Terminal: no`, there are two competing case
screens both rendering `brief_sections`, five rooms are five full-page navigations that lose your
place in the argument, and ten `← back` links do the work persistent chrome should do. Section 5's
design principles are unreachable while every element renders at the same weight: 50 bordered-box
selectors and a recommendation set at 18 px while a source-strength letter grade is set at 24 px in
the accent colour.

## Scope

- `frontend/src/screens/shell/AppShell.tsx` — three regions: a case rail, a content column of fixed
  measure, and a context panel that slides in without navigating.
- `frontend/src/screens/shell/CaseChrome.tsx` — persistent per-case chrome carrying the decision
  question (from `IntakeRecord.decision_question`, never `case_id`), the current phase from
  SPEC-047's map in compact form, live spend from `EffortView`, the altitude control, and the theme
  control whose mechanism SPEC-045 shipped.
- Route consolidation: `CaseDetail` and `Brief` collapse into one case surface. Existing
  `/cases/:id/brief` and `/cases/:id` both resolve there; room routes are preserved as deep links
  that open the context panel rather than a page.
- `frontend/src/screens/Brief/` — document treatment:
  - sections rendered as prose with hanging labels, not a bordered card per section;
  - the recommendation at display scale from SPEC-045's type scale;
  - **border discipline**: a border means exactly one of two things — this needs your action, or
    this is uncertain. Every other bordered container loses its border.
- `frontend/src/screens/shared/Skeleton.tsx` — content-shaped loading states replacing
  `<p>Loading…</p>` on every screen.
- `frontend/src/screens/shared/Toast.tsx` — a toast surface for control actions (approve, pause,
  resume, send back), which today either silently swap the screen or render a red paragraph.
- `frontend/src/screens/shared/altitude.ts` + control — Answer / Reasoning / Method, persisted per
  user in `localStorage` rather than per case; Answer shows the recommendation, one uncertainty
  sentence, key reasons and tripwires; Reasoning adds the full brief with provenance and citations;
  Method adds rooms, gates, spend and raw artifacts.
- Rooms rendered into the context panel via `RoomShell`, with the inspector's existing panel
  pattern extended rather than duplicated.
- Removals: `.back-link` and its ten usages; `RoomTabs` as a second nav bar.

## Out of scope

- Agent attribution, margin objections and dissent (SPEC-049) — this spec provides the margin
  column those render into.
- Commissioning and the two checkpoint sheets (SPEC-050).
- Notifications, digest, reactions (SPEC-051); export and mobile (SPEC-052).
- Rendering phase 8's artifacts (SPEC-053); this spec leaves the delivery and scope surfaces with
  documented extension slots so SPEC-053 fills them without a second restructure.

## Design

Hierarchy is enforced as a testable budget rather than a review opinion. Two assertions do the work:
bordered elements per screen must not exceed a documented budget, and the computed font size of the
recommendation must exceed every metric element on the same screen. The second permanently prevents
the current inversion, and both are cheap to evaluate from the DOM in the existing Playwright suite.

Altitude is stored per user, not per case, because the two audiences the product serves are two
people, not two decisions — someone who wants the answer wants it on every case. Rooms move into the
context panel rather than being deleted so no information is lost and every deep link keeps working;
the inspector already proves the pattern.

This is the sheet most likely to exceed one focused session. If it does, the pre-agreed split is
shell plus chrome (regions, case identity, route consolidation) as one sheet and document plus
altitude (hierarchy, border discipline, skeletons, toasts, altitude control) as another, per
`specs/README.md`'s rule that the spec is updated first when implementation shows it was wrong.

## Deliverables

- [x] `frontend/src/screens/shell/AppShell.tsx` + `CaseChrome.tsx`; route consolidation in `App.tsx`
- [x] Document treatment in `frontend/src/pages/CaseDetail.tsx`; border discipline across `styles.css`
- [x] `frontend/src/screens/shared/Skeleton.tsx`, `Toast.tsx`
- [x] `frontend/src/screens/shell/altitude.ts` + altitude control; rooms in the context panel
- [x] `frontend/e2e/density.spec.ts` — border budget and answer-dominance assertions
- [x] Component tests for shell, chrome, altitude and skeletons; updated visual baselines

Deviations from the Scope section, all deliberate:

- `altitude.ts` lives in `screens/shell/` rather than `screens/shared/`; it is shell state, and
  every consumer is in `shell/`.
- The document treatment landed in `pages/CaseDetail.tsx` rather than `screens/Brief/`, because
  consolidation meant deleting `Brief.tsx` rather than editing it. `MarginNarration`,
  `SealedAnswerCard` and `WorkingViewCard` survive in `screens/Brief/` and are rendered by the
  case surface.
- Rooms render through the existing `RoomShell` reading a new `CaseDataContext`, rather than a new
  `RoomShell`. This removed six duplicate SSE connections: each room page used to mount its own
  `useCaseView` against the same case.
- `RoomTabs` is deleted rather than kept; `screens/shell/RoomRail.tsx` carries the same six
  destinations in the rail at Method altitude.

## Acceptance criteria

- [x] The page heading equals the case's decision question for every fixture and never matches
      `^case-\d+-`; `view.case_id` appears nowhere as a heading.
- [x] Zero `.back-link` elements remain in the built app, and every previously valid route —
      including all six room deep links and the inspector — still resolves.
- [x] The density guard passes: bordered elements per screen are within the documented budget, and
      the computed font size of the recommendation exceeds every metric element on the same screen.
- [x] Altitude persists across cases and reloads; each of the three altitudes renders its required
      elements and omits the others, asserted per altitude against a completed fixture case.
- [x] Opening a citation or a room from the content column preserves the content column's scroll
      position, and closing the panel returns focus to the element that opened it.
- [x] Every screen shows a content-shaped skeleton while loading, and no screen renders the string
      "Loading…"; each control action produces a toast naming what happened.
- [x] Axe clean on every route in both themes, visual baselines reviewed and updated, terminology
      guard extended to the new surfaces, `make frontend-check` and `make e2e-frontend` green.

## Verification plan

```
cd frontend && npm test
make frontend-check && make frontend-build
E2E_MODE=fixture npx playwright test --config=e2e/playwright.config.ts density.spec.ts
E2E_MODE=fixture npx playwright test --config=e2e/playwright.config.ts visual.spec.ts
E2E_MODE=fixture npx playwright test --config=e2e/playwright.config.ts
make e2e-frontend
make check
```

## Verification results

| Command | Result |
| --- | --- |
| `cd frontend && npm test` | 18 files, **170 passed** (was 142; +28 for shell, chrome, altitude, toasts, skeletons, and the rewritten case surface) |
| `make frontend-check` | green — token guard clean, typecheck clean, 170 tests |
| `make frontend-build` | green — 56.85 kB CSS, 344.40 kB JS |
| `E2E_MODE=fixture … density.spec.ts` | **14 passed** |
| `E2E_MODE=fixture …` (chromium, chromium-dark, mobile, reduced-motion) | **126 passed** in 3m10s |
| `E2E_MODE=replay …` | **9 passed** |
| `E2E_MODE=stub …` | **5 passed** |
| `make check` | **941 passed**, 18 deselected — the pipeline is unchanged, as `tests/test_pipeline_invariants.py` asserts |

### The border budget, measured

The budget's numeric value was the sheet's open question. It was set by measuring, not by
choosing. Bordered boxes that are neither an action nor an uncertainty, per route:

| Route | Before | After |
| --- | --- | --- |
| case surface | 6 | 0 |
| sources room | 18 | 0 |
| method room | 27 | 0 |
| delivery | 4 | 0 |
| scope sheet | 12 | 0 |
| library | 1 | 0 |

The budget is **2 per route**, not 0, so a screen adding one deliberate container is not blocked on
a guard change while a return to card-per-section trips immediately.

Both guards were checked against a deliberate regression before being trusted, because a guard that
cannot fail is decoration: re-bordering three method-room sections fails the budget with
`method room renders 3 bordered boxes … the budget is 2`, and setting `.source-strength-grade` to
`--text-4xl` fails answer dominance with `source-strength-grade renders at 40px, at or above the
recommendation's 32px — the metric outranks the answer`.

### Two defects the assertions did not catch

Both were found by reading the regenerated screenshot rather than the test output, which is the
argument for keeping visual baselines reviewable rather than auto-accepted.

1. **The transcript in the reading column.** `MarginNarration` rendered all 56 non-technical events
   as a list — "Task T-001 started", "Gate investigation: pass" — directly under the brief. The
   case surface was 5858 px tall and the majority of it was audit log. Moved to Method altitude,
   with the narrator's own collapsed `<details>` transcript at Reasoning. The surface is now
   3513 px, a 40% reduction with no information removed.
2. **The case map clipped in the rail.** The map is a horizontal strip needing ~54 rem; the rail is
   15 rem, so every stage label rendered as "Reading your q…". It lays out as a column in the rail,
   which is also the direction the case runs.

### Not verified here

`--project=webkit` cannot run in this environment: Playwright 1.62 resolves `webkit-2336` and the
image ships no webkit build, so all 45 webkit tests fail at `browserType.launch`. This is
pre-existing and unrelated to this sheet — the same failure predates it. The four Chrome-based
projects cover every assertion in this sheet.

## Open questions

Both resolved during implementation.

- **The border budget's numeric value** — measured rather than guessed, and recorded in the
  Verification results above: every route measures 0 after the border pass, and the guard is set at
  2 per route.
- **Whether this sheet splits** — it did not. The pre-agreed split was shell-plus-chrome against
  document-plus-altitude, and the two turned out to be one change: the altitude control is what
  decides what the shell's rail and panel contain, so building them separately would have meant
  building the rail twice.

One thing this sheet deliberately left for later: the fixture's brief text still renders raw
identifiers in its *content* (`no_critical_evidence_gaps_remain`, `staged_entry`,
`invest_nvda_now`). Those come from the artifacts, not from a screen forgetting to translate, so
they belong to SPEC-054's calibration language rather than here.
