---
id: SPEC-052
title: Distribution — export, share, replay onboarding, the library workspace, and mobile
phase: 9
status: draft
depends_on: [SPEC-045, SPEC-048, SPEC-049]
parallel_with: [SPEC-051]
north_star_refs: ["15", "16"]
last_updated: 2026-08-05
---

# SPEC-052 — Distribution: export, share, replay onboarding, the library workspace, and mobile

## Summary

Makes the brief an object that can leave the tool, the library a workspace rather than a three-column
table, and the product usable on a phone. Also promotes an existing capability into the product:
replay mode re-emits a recorded case on scaled timing, exists, is used only by tests, and is a
ready-made ninety-second product tour showing a full deliberation with its loops and dissent.
Completes the Markdown export and print stylesheet that SPEC-035 scoped and never built.

## Motivation

North star Section 16 defines the final recommendation format as a package a person receives; a
package that cannot be sent to a boss, a co-founder or a board is not one. Section 15's step 7 — "user
receives the recommendation package" — is unfinished while the only way to receive it is to keep a
browser tab open. The library is the dashboard for a multi-hour engagement and currently shows less
than `advisor status` does in a terminal, and the most likely moment to check a three-hour run is on
a phone, which no Playwright project has ever exercised.

## Scope

- `frontend/src/export/` — the deterministic Markdown download SPEC-035 specified, plus a print
  stylesheet producing a usable PDF via the browser, both preserving citation ids and provenance
  voices from SPEC-049.
- Read-only sharing: a share route rendering a completed case without controls, reusing the
  replay-mode guarantee that control POSTs return 409. Local-first and unauthenticated by design —
  the link is a local URL, not a hosted document.
- `frontend/src/screens/Onboarding/` — first-run tour driven by replay mode over a committed fixture
  case at high speed, showing commissioning, a loop, a dissent and a delivery. Skippable, and
  re-runnable from settings.
- `frontend/src/pages/CaseLibrary.tsx` — a workspace:
  - cards with the decision question, a phase ring, elapsed against the measured estimate from
    SPEC-050, spend against cap, and the current narrator line;
  - grouped by SPEC-046's server-supplied `needs_you` — waiting on you, running, done — which
    **deletes** the duplicated client-side stage-string derivation at `CaseLibrary.tsx:7`;
  - search over case questions, and a command-K palette across cases, evidence and assumptions.
- `frontend/src/screens/Settings/` — the surface the phase's preferences have been accumulating with
  nowhere to live: default effort, output shape and watch-or-notify from SPEC-050, default altitude
  from SPEC-048, theme from SPEC-045, notification permission state from SPEC-051, and re-running
  the onboarding tour. Preferences only; no case data.
- Responsive: SPEC-048's three-region shell collapses to one column with the context panel as a
  sheet; the two checkpoints and the answer are fully usable at 390 px; no horizontal body scroll at
  360 px.

## Out of scope

- Any hosted, authenticated or multi-user sharing. The service binds to `127.0.0.1` and this spec
  does not change that.
- Rendering phase 8's artifacts in the export (SPEC-053 extends the exporter once those exist).
- Mobile-specific interaction patterns beyond making existing surfaces work at small widths.

## Design

Export is deterministic because the brief is already assembled deterministically by the projection:
the exporter walks `CaseView` in canonical section order rather than scraping the DOM, so two exports
of the same case are byte-identical and the citation set is provably complete. That also means the
exporter is testable without a browser.

Sharing reuses replay mode's read-only enforcement rather than adding an authorisation concept. The
service already refuses every control POST in replay mode with a 409; a share route is the same
guarantee applied to a live case directory, which keeps one mechanism instead of two.

Onboarding is replay because building a scripted demo would create a second, drifting description of
how the product behaves. A recorded case is the product behaving, and it stays true automatically as
the pipeline changes — which matters more once phase 8 lands.

The library's grouping is server-driven so the client stops owning a copy of a rule the projection
already implements. Deleting `needsYouFromStage` is an acceptance criterion, not a side effect.

## Deliverables

- [ ] `frontend/src/export/` — deterministic Markdown export and print stylesheet
- [ ] Read-only share route reusing the replay-mode POST guarantee
- [ ] `frontend/src/screens/Onboarding/` — replay-driven first-run tour over a committed fixture
- [ ] `frontend/src/pages/CaseLibrary.tsx` — cards, grouping on server `needs_you`, search, command-K
- [ ] `frontend/src/screens/Settings/` — one home for every preference the phase introduces
- [ ] Responsive collapse of the shell; checkpoints and answer usable at 390 px
- [ ] Tests: `export.test.ts`, library component tests, mobile-viewport e2e

## Acceptance criteria

- [ ] The exported Markdown contains every citation id present in the projection for that case, in
      canonical section order, and two exports of the same case are byte-identical.
- [ ] The print stylesheet produces a paginated document with no clipped content and no interactive
      controls.
- [ ] The share route renders a completed case read-only, and every control POST against it returns
      409 — asserted, not assumed.
- [ ] The onboarding tour runs to completion over the committed fixture, showing at least one loop
      and one dissent, and is skippable and re-runnable.
- [ ] The library groups by the server's `needs_you`; `needsYouFromStage` is deleted from
      `CaseLibrary.tsx` and no client-side stage-string derivation remains.
- [ ] Every preference introduced anywhere in phase 9 is readable and changeable from Settings, and
      changing one takes effect without a reload.
- [ ] At the 390 px viewport both checkpoints and the answer are fully operable, and no page in the
      suite scrolls horizontally at 360 px.
- [ ] Axe clean in both themes at both viewports, visual baselines updated for mobile, terminology
      guard extended; `make frontend-check` and `make e2e-frontend` green.

## Verification plan

```
cd frontend && npm test -- export CaseLibrary
make frontend-check && make frontend-build
E2E_MODE=fixture npx playwright test --config=e2e/playwright.config.ts --project=mobile-light
E2E_MODE=fixture npx playwright test --config=e2e/playwright.config.ts --project=mobile-dark
E2E_MODE=replay npx playwright test --config=e2e/playwright.config.ts   # onboarding tour
make e2e-frontend
make check
```

## Verification results

Not yet executed.

## Open questions

- Whether the share route should be gated behind an explicit "make shareable" action rather than
  existing for every case. Recommend explicit, so that producing a link is a decision the user
  makes rather than a URL that always resolves.
