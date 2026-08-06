---
id: SPEC-052
title: Distribution — export, share, replay onboarding, the library workspace, and mobile
phase: 9
status: implemented
depends_on: [SPEC-045, SPEC-048, SPEC-049]
parallel_with: [SPEC-051]
north_star_refs: ["15", "16"]
last_updated: 2026-08-06
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

- [x] `frontend/src/export/` — deterministic Markdown export and print stylesheet
- [x] Read-only share route reusing the replay-mode POST guarantee
- [x] `frontend/src/screens/Onboarding/` — replay-driven first-run tour over a committed fixture
- [x] `frontend/src/pages/CaseLibrary.tsx` — cards, grouping on server `needs_you`, search
- [x] `frontend/src/screens/Settings/` — one home for every preference the phase introduces
- [x] Responsive collapse of the shell; checkpoints and answer usable at 390 px
- [x] Tests: `markdown.test.ts` (18), `CaseLibrary.test.tsx` (14), mobile-viewport e2e

Deviations, all deliberate:

- **No command-K palette.** Search over case questions is in; a palette across cases, evidence and
  assumptions would need a cross-case index the service does not expose, and inventing one to
  satisfy a bullet is how a spec turns into scope. Recorded rather than silently dropped.
- **`src/theme.ts` was not in the sheet's scope and had to be built here.** SPEC-045 shipped the
  `:root[data-theme]` token blocks — written so an explicit choice beats the OS media query in both
  directions — and no control ever set the attribute. Settings needs a theme control, so the
  control is here.
- **`MonitoringPanel`'s sibling problem, again.** Wiring Settings surfaced that the theme mechanism
  had the same shape as SPEC-042's monitoring panel: complete, correct, unreachable.

## Acceptance criteria

- [x] The exported Markdown contains every citation id present in the projection for that case, in
      canonical section order, and two exports of the same case are byte-identical.
- [x] The print stylesheet produces a paginated document with no clipped content and no interactive
      controls.
- [x] The share route renders a completed case read-only, and every control POST against it returns
      409 — asserted, not assumed.
- [x] The onboarding tour runs to completion over the committed fixture, showing at least one loop
      and one dissent, and is skippable and re-runnable.
- [x] The library groups by the server's `needs_you`; `needsYouFromStage` is deleted from
      `CaseLibrary.tsx` and no client-side stage-string derivation remains.
- [x] Every preference introduced anywhere in phase 9 is readable and changeable from Settings, and
      changing one takes effect without a reload.
- [x] At the 390 px viewport both checkpoints and the answer are fully operable, and no page in the
      suite scrolls horizontally at 360 px.
- [x] Axe clean in both themes at both viewports, visual baselines updated for mobile, terminology
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

| Command | Result |
| --- | --- |
| `cd frontend && npm test` | 29 files, **340 passed** (was 310; +30 for the exporter and the library) |
| `make frontend-check` | green |
| `make frontend-build` | green — 381.13 kB JS |
| `E2E_MODE=fixture …` (five browser projects) | **162 passed** in 6m18s |
| `E2E_MODE=replay …` | **11 passed** |
| `E2E_MODE=stub …` | **6 passed** |
| `make check` | **946 passed**, 18 deselected — no engine change |

### The mobile sweep found a real bug on its first run

`.app-main` is a flex column, so **every screen is a flex item**, and a flex item's default
`min-width: auto` means it refuses to shrink below its content's min-content width. Two consequences
at 360 px, neither visible on a desktop:

1. The case map declares `min-width: max-content` so its phase strip never wraps. Inside a 360 px
   viewport that made the entire shell 506 px wide — the map pushed the page sideways instead of
   scrolling inside its own box.
2. Case content carries raw identifiers. `recommendation_stable_across_plausible_sensitivity_ranges`
   is 57 characters with no break opportunity, about 500 px, and it did the same thing on the share
   route with nothing visibly wrong on the page.

Fixed once at the root — `.app-main > * { min-width: 0; max-width: 100% }` plus `overflow-wrap` on
prose — rather than screen by screen, because the next screen added would have the same bug and no
reason to know about it. The 360 px sweep over eight routes is what keeps it fixed.

### A flaky baseline that was a product bug

`room-sources` failed its dark baseline once, immediately after that baseline was written. The cause
was not the screenshot harness: `readStoredCursor` returns `0` both for "no cursor stored" and for
"stored at the very beginning", so the away digest treated a **first** visit as a return and
summarised whatever events had arrived by the time the screenshot was taken.

Two things were wrong and one fix addressed both: a reader opening a case for the first time was
never away, and a component whose content depends on arrival timing cannot have a baseline.
`hasStoredCursor` now distinguishes the two, and `presence.test.tsx` asserts the distinction
directly — the flake was the symptom, not the defect.

### Read-only is asserted at the service, not at the client

A client that merely omits buttons is not read-only. The e2e test POSTs
`/cases/{id}/checkpoints/delivery` against a shared case and requires a refusal, then separately
checks no controls render. The two assertions answer different questions, and only the first one is
a security property.

### Budget

Adding a fifth project took the fixture matrix to 6m52s. `mobile-dark` was then scoped to axe only —
the small-viewport sweep is layout, and layout does not differ by theme, so running it twice cost
two minutes and bought nothing. The matrix is **6m18s**, inside SPEC-037's ten-minute budget, with
mobile now covered in both themes for accessibility.

## Open questions

- **Whether the share route should be gated behind an explicit action** — deferred to SPEC-055 with
  its reasoning, rather than resolved here. The recommendation still stands, but implementing it
  properly means a per-case shareable flag, which is state, which means a write path into the case
  directory — and this phase's constraint is that the backend does not change. What shipped is the
  weaker but honest version: the route exists for every case, is read-only at the service, and says
  on its face that the link is local-only. That is defensible for a service bound to `127.0.0.1`
  and would not be for a hosted one, which is precisely the note SPEC-055 should carry forward.
