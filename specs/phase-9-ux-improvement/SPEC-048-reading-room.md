---
id: SPEC-048
title: The reading room — shell, persistent chrome, hierarchy, and altitudes
phase: 9
status: draft
depends_on: [SPEC-045, SPEC-047]
parallel_with: []
north_star_refs: ["5", "15"]
last_updated: 2026-08-05
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

- [ ] `frontend/src/screens/shell/AppShell.tsx` + `CaseChrome.tsx`; route consolidation in `App.tsx`
- [ ] `frontend/src/screens/Brief/` document treatment; border discipline across `styles.css`
- [ ] `frontend/src/screens/shared/Skeleton.tsx`, `Toast.tsx`
- [ ] `frontend/src/screens/shared/altitude.ts` + altitude control; rooms in the context panel
- [ ] `frontend/e2e/density.spec.ts` — border budget and answer-dominance assertions
- [ ] Component tests for shell, chrome, altitude and skeletons; updated visual baselines

## Acceptance criteria

- [ ] The page heading equals the case's decision question for every fixture and never matches
      `^case-\d+-`; `view.case_id` appears nowhere as a heading.
- [ ] Zero `.back-link` elements remain in the built app, and every previously valid route —
      including all six room deep links and the inspector — still resolves.
- [ ] The density guard passes: bordered elements per screen are within the documented budget, and
      the computed font size of the recommendation exceeds every metric element on the same screen.
- [ ] Altitude persists across cases and reloads; each of the three altitudes renders its required
      elements and omits the others, asserted per altitude against a completed fixture case.
- [ ] Opening a citation or a room from the content column preserves the content column's scroll
      position, and closing the panel returns focus to the element that opened it.
- [ ] Every screen shows a content-shaped skeleton while loading, and no screen renders the string
      "Loading…"; each control action produces a toast naming what happened.
- [ ] Axe clean on every route in both themes, visual baselines reviewed and updated, terminology
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

Not yet executed.

## Open questions

- The border budget's numeric value. It should be set from the redesigned screens once they exist
  rather than guessed here, and recorded in the spec before status moves to `implemented`.
- Whether this sheet splits. Decide at implementation start, not at approval; the split boundary is
  documented above so it costs nothing to take.
