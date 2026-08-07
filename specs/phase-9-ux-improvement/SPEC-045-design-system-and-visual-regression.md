---
id: SPEC-045
title: Design system — tokens, type scale, theming, and the visual-regression harness
phase: 9
status: implemented
depends_on: []
parallel_with: [SPEC-046]
north_star_refs: ["5", "15"]
last_updated: 2026-08-05
---

# SPEC-045 — Design system: tokens, type scale, theming, and the visual-regression harness

## Summary

The token layer the rest of the phase is built on, and the test harness the rest of the phase is
verified against. `styles.css` is 1,364 lines built on eight custom properties, with 28 raw hex
values and 9 ad-hoc font sizes written inline across component rules; 7 of those 9 sizes fall
between 11 px and 16 px, so the scale has no top end and nothing can be emphasised, only shrunk.
This spec replaces that with a real token system, adds the second theme, and — because a phase about
visual hierarchy cannot be verified by assertions about text alone — stands up screenshot baselines
across a theme × viewport matrix. Deliberately a substitution pass: no component is restructured, so
the diff stays reviewable and the risk stays near zero.

## Motivation

North star Section 5 (core design principles) and Section 15: the experience should read as a
commissioned engagement, not an operator console. The UX review found the cause of the "crowded,
primitive" reading is not volume of information but absence of rank — 50 bordered-box selectors, 38
white cards, and a type scale with no top, which forces every distinction to be expressed by drawing
another box. Ranking is impossible without a scale to rank on, so this spec precedes every visual
change in SPEC-048 through SPEC-052. The harness is equally load-bearing: today nothing in the repo
can detect an unintended layout or colour change.

## Scope

- `frontend/src/styles/tokens.css` — the primitive layer:
  - colour ramps (neutral, accent, and the semantic good/warning/critical trio kept separate from
    the accent), space scale, radius scale, elevation, motion durations and easings;
  - a type scale with a genuine display range for the recommendation, which today renders at 18 px
    while `.source-strength-grade` renders at 24 px in the accent colour;
  - semantic aliases layered over the primitives — `--surface`, `--surface-raised`, `--text`,
    `--text-muted`, `--border`, `--state-needs-you`, `--state-uncertain`, `--state-blocked`.
- Theming: `@media (prefers-color-scheme: dark)` redefining tokens only, plus
  `:root[data-theme="dark"]` / `:root[data-theme="light"]` overrides so an explicit user choice wins
  in both directions. Components reference tokens only; no component rule names a colour.
- Migration of `frontend/src/styles.css` onto the tokens: every raw hex and every raw `rem`
  font-size replaced. Structural rules (layout, spacing) are left as they are — SPEC-048 owns those.
- `frontend/scripts/check-tokens.cjs` — a guard, modelled on the existing
  `scripts/generate-types.cjs --check` drift gate, that fails when a raw hex or a raw `rem`
  font-size appears anywhere under `frontend/src/` outside `tokens.css`. Wired into
  `make frontend-check`.
- `frontend/e2e/playwright.config.ts` — the verification matrix:
  - projects for light and dark (`colorScheme` plus the `data-theme` attribute) and for desktop and
    mobile (390 × 844) viewports;
  - a `reduced-motion` project (`prefers-reduced-motion: reduce`), which both `styles.css` and
    `Brief.tsx` already branch on and nothing tests.
- `frontend/e2e/visual.spec.ts` — `toHaveScreenshot` baselines for every route, across the matrix,
  with committed baselines and a documented update path.
- Axe coverage extended from the current 6 screens to every route, run in both themes.
- `frontend/e2e/contrast.spec.ts` — computed-contrast assertions for every semantic
  foreground/background pair in both themes, at WCAG AA.
- Deterministic capture: animations disabled, fonts pinned to the bundled stack, and a documented
  pixel threshold, so the harness does not become a flaky gate the phase learns to ignore. The
  matrix multiplies run time — projects × routes × visual × axe — so **SPEC-055 owns the scoping
  rule and the 10-minute budget**; this spec ships the matrix and must not exceed it alone.

## Out of scope

- Any layout, hierarchy or border-discipline change (SPEC-048).
- Skeletons and toasts (SPEC-048 — they are new components, not a token substitution).
- A user-facing theme switcher control; this spec ships the mechanism and honours the OS
  preference, and SPEC-048 places the control in the chrome.
- Changing any copy.

## Design

Tokens are two-layer on purpose: primitives carry no meaning and are never referenced by components,
semantic aliases carry meaning and are all a component may use. That is what makes the second theme
a redefinition of ~20 aliases rather than an audit of 1,364 lines, and it is what the guard script
enforces — a component that names a colour cannot be theme-correct, so the lint is the design rule
rather than a style preference.

The screenshot matrix is deliberately introduced before any visual work rather than alongside it.
Baselines captured from the current UI make every subsequent phase-9 diff legible as an intentional
change, and give SPEC-056 something to verify the phase against. Baseline churn is expected and is
reviewed in the diff; the acceptance criterion is that changes are *reviewed*, never blind-accepted.

## Deliverables

- [x] `frontend/src/styles/tokens.css` — primitives plus semantic aliases, both themes
- [x] `frontend/src/styles.css` migrated onto tokens; zero raw hex or raw `rem` font-size remaining
- [x] `frontend/scripts/check-tokens.cjs` + `make frontend-check` wiring
- [x] `frontend/e2e/playwright.config.ts` theme × viewport × reduced-motion projects
- [x] `frontend/e2e/visual.spec.ts` + committed baselines for every route
- [x] `frontend/e2e/contrast.spec.ts`; axe extended to every route in both themes

## Acceptance criteria

- [x] `make frontend-check` fails when a raw hex or raw `rem` font-size is introduced under
      `frontend/src/` outside `tokens.css`, and passes on the migrated tree.
- [x] Every semantic foreground/background pair meets WCAG AA in both themes, asserted from
      computed styles rather than from the token values.
- [x] Setting `data-theme="light"` under a dark OS preference, and `data-theme="dark"` under a light
      one, both produce the intended theme — the explicit choice wins in both directions.
- [x] `npx playwright test visual.spec.ts` produces baselines for every route across light/dark ×
      desktop/mobile, and a deliberate token change fails the suite until baselines are updated.
- [x] Axe reports zero serious/critical violations on every route in both themes, extending
      SPEC-037's six-screen list to the full route table.
- [x] The reduced-motion project passes with animation disabled on the brief's settle transition.
- [x] The visual suite passes twice consecutively with no pixel diff on an unchanged tree — flake is
      a failure, not a retry.
- [x] `make check` and `make frontend-check` are green; the 77 existing frontend unit tests are
      unchanged and passing.

## Verification plan

```
cd frontend && npm run typecheck && node scripts/check-tokens.cjs
make frontend-check
make frontend-build
E2E_MODE=fixture npx playwright test --config=e2e/playwright.config.ts visual.spec.ts contrast.spec.ts
E2E_MODE=fixture npx playwright test --config=e2e/playwright.config.ts   # axe, all routes, both themes
make e2e-frontend
make check
```

## Verification results

- 2026-08-05. `make check` green (741 tests). `make frontend-check` green — now running the token
  guard alongside tsc, the types drift check and 86 unit tests.
- **The migration is provably lossless.** Baselines were captured from the *pre-migration* UI, the
  token migration was then applied, and all 13 routes matched with zero pixel diff. A substitution
  pass that claims to move no pixels can say so from evidence rather than from intent.
- Token guard: clean on the migrated tree, and verified to fail — a probe rule carrying
  `#ff00aa` and `font-size: 1.75rem` was rejected with file and line before being removed.
- Contrast: all 15 semantic foreground/background pairs clear WCAG AA in both themes, measured from
  computed styles. The explicit-choice test confirms `data-theme` beats the media query in both
  directions.
- Visual regression: 39 baselines (13 routes x light/dark/mobile). The suite passed twice
  consecutively with no diff, so flake is excluded rather than retried.
- Axe: extended from 6 screens to all 12 routes, run in both themes — 12 passed in each. This is
  also what makes SPEC-037's "in both themes" criterion true for the first time.
- Budget: the full matrix across fixture, stub and replay runs **99 tests in 2m44s with zero
  failures**, inside SPEC-037's 10-minute budget. Up from 35 tests.
- A deliberate token change (accent `#0066cc` -> `#cc3300`) fails the visual suite until baselines
  are updated — the gate is proven sensitive, not merely passing.

**Three real accessibility defects were found by the expanded coverage**, all pre-existing and all
invisible to the previous six-screen list:

1. `.status-badge` and `.brief-section-status` rendered muted text on the *border* colour — 4.34:1,
   below AA. A border colour is not a surface; both now use `--surface-sunken`, which is a
   sanctioned pair the contrast spec covers. This is the one change that moved pixels, so baselines
   were re-captured after it.
2. The three `<select>` controls in the assumptions room had no accessible name. A `<legend>` names
   the group, not the control, so each gained an `aria-label`.
3. The method room's audit log is a scrollable region with no keyboard access; it gained
   `tabIndex` and a name.

**Deviations from the sheet.**

1. `waitForLoadState("networkidle")` cannot be used anywhere in this app: every case route holds an
   SSE stream open, so the network is never idle. It timed out on 9 of 13 routes and took the first
   baseline run to 9.8 minutes. The specs wait on the app shell plus a paint instead.
2. Fixing the scrollable region with `role="group"` stripped the `<ul>`'s implicit list role and
   orphaned every `<li>`, which the expanded axe sweep caught immediately. `role="list"` is correct.
3. The sheet deferred the scoping rule and the budget to SPEC-055, but the matrix could not ship
   without one — the full cross-product is four to six times the budget. Per-project `grep` scoping
   landed here: dark repeats the presentation sweeps, mobile repeats layout only, reduced-motion
   runs one targeted check, webkit keeps the functional journeys and skips engine-specific
   screenshots.
4. `--text-md-plus` (15px) was added to keep the migration lossless; the sheet listed eight existing
   steps and the product uses nine.
5. Webkit remains unverified in this environment because its browser binary is not installed —
   the same limitation SPEC-037 recorded.
6. **A scoping bug, and a verification bug that hid it.** The reduced-motion test ran under the
   chromium project too, where the preference is not applied, so it failed — and the first budget
   run reported "88 passed" only because the command truncated Playwright's summary to its last two
   lines, which is printed *after* the failure count. The project now carries
   `grepInvert: /reduced motion/`, and the budget was re-measured with failures visible. Recorded
   because the lesson generalises: a verification command that can hide a red result is not
   verification.

## Open questions

- Baseline storage: committed to the repo (simple, reviewable, adds binary churn) versus generated
  on demand from a pinned browser. Recommend committed, matching how `tests/fixtures/cases` is
  already handled, and pinning the Playwright browser build so baselines stay reproducible.
