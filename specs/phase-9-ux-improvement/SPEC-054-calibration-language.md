---
id: SPEC-054
title: The calibration language — one uncertainty vocabulary at every altitude
phase: 9
status: draft
depends_on: [SPEC-045, SPEC-048]
parallel_with: [SPEC-049]
north_star_refs: ["9", "15", "16"]
last_updated: 2026-08-05
---

# SPEC-054 — The calibration language: one uncertainty vocabulary at every altitude

## Summary

The product's differentiator is that it keeps four kinds of uncertainty separate and refuses to
collapse them into one number. That commitment currently reaches the screen as four unrelated
widgets in a grid on one route, built from five components that share no visual grammar — and
nowhere else. This spec makes uncertainty a single visual language used at every altitude, from the
answer headline down to a single evidence chip: bands rather than bars, dots you can count, an
explicit *Not assessed* stamp, and an expand-in-place gesture that shows what supports any claim
without navigating away from it.

## Motivation

North star Section 9 (probability and confidence policy) requires probability, recommendation
confidence, evidence confidence and model stability to stay distinct, with point-versus-interval
preserved and sentinels explicit; Section 16 requires the recommendation package to carry them.
Section 15 requires the interface to distinguish sourced facts from interpretation from assumptions.
Today `ProbabilityBand`, `ConfidenceBands`, `SourceStrengthGrade`, `StabilityDots` and
`NotAssessedWidget` each solve their own corner with their own idiom, appear only on Delivery, and
share nothing — so a user learns four encodings once and then never sees them again. This is the one
place the phase should spend its design budget, because it is the only visual problem in the product
that no competitor has.

## Scope

- `frontend/src/uncertainty/language.ts` — the grammar, as data:
  - **bands, not bars**, wherever a value has an interval; a point estimate renders visibly
    differently from an interval, per Section 9's point-XOR-interval rule;
  - **countable marks** for anything derived from a run count (`AssessedStability.runs_supporting`
    of `runs_total`) — dots a user can literally count rather than a percentage;
  - **grades** for ordinal judgements, never numbers dressed as measurements;
  - **an explicit `Not assessed` stamp** carrying its reason, never an empty state, never a zero.
- Three scales of the same encodings, all driven from that grammar:
  - *inline* — a chip beside a claim or an evidence citation;
  - *summary* — the compact form in the answer headline and on library cards;
  - *full* — the existing Delivery widgets, rebuilt on the shared grammar.
- `frontend/src/uncertainty/Why.tsx` — **expand-in-place**: a disclosure on any claim, assumption,
  option or number that reveals what supports it — citations, the assumption it rests on, the
  adjustment history from `ProbabilityView.adjustments` — inline, without leaving the argument.
- Application across altitudes: the Answer altitude carries summary encodings; Reasoning carries
  inline encodings against claims; Method carries the full widgets. One vocabulary, three densities.
- Rebuild of `ProbabilityBand`, `ConfidenceBands`, `SourceStrengthGrade`, `StabilityDots` and
  `NotAssessedWidget` onto the shared grammar and SPEC-045's tokens, preserving their current
  semantics exactly.
- `frontend/src/copy/uncertainty.ts` — the words: verbal probability phrases mapped to ranges, held
  in the terminology lexicon so they cannot drift between screens.

## Out of scope

- Any change to how uncertainty is computed, assessed, or stored. `stability.py`, `calibration.py`
  and the artifact schemas are untouched; this spec is presentation only.
- Combining or deriving a fifth summary number from the four measures. Explicitly forbidden below.
- The cross-case calibration screen (SPEC-051), which reports the system's track record rather than
  one case's uncertainty.

## Design

The grammar is data rather than five components' worth of CSS because the property that matters —
that the same thing always looks the same — is only enforceable if there is one place the mapping
lives. A verbal probability phrase, a band, a countable dot and a *Not assessed* stamp each have
exactly one rendering, chosen by the kind of value, at three scales.

The hardest rule is the one the product already holds in its data model and has never held in its
pixels: **no single "confidence" is ever synthesised.** Four measures that disagree are the honest
output, and a UI that averages them into one dial would destroy the property `NotAssessed` and
`AssessedStability` were designed to protect. That is written here as a test, not a convention.

Expand-in-place is the engagement answer at claim level. The review's finding was that depth by
navigation costs the reader their place; the inspector already proves the panel pattern for
records, and this is the same gesture at the granularity of a sentence.

## Deliverables

- [ ] `frontend/src/uncertainty/language.ts` — the encoding grammar, three scales
- [ ] `frontend/src/uncertainty/Why.tsx` — expand-in-place support disclosure
- [ ] The five existing uncertainty components rebuilt on the shared grammar and tokens
- [ ] `frontend/src/copy/uncertainty.ts` — verbal phrase ↔ range mapping in the lexicon
- [ ] Application across all three altitudes: summary, inline, full
- [ ] Tests: `language.test.ts`, `Why.test.tsx`, component tests for the five rebuilds

## Acceptance criteria

- [ ] **No synthesised summary**: no screen renders a single combined confidence, average or overall
      score derived from more than one of the four measures — asserted across every route.
- [ ] A point estimate and an interval estimate render visibly differently, and an interval never
      renders as a point; `ProbabilityView` with `point` set and with `interval_low`/`interval_high`
      set produce distinguishable DOM.
- [ ] `AssessedStability` renders `runs_supporting` of `runs_total` as that many countable marks,
      matching the numbers exactly for every fixture.
- [ ] `NotAssessed` renders the explicit stamp with its `reason` and is never shown as zero, empty,
      absent, or a low value.
- [ ] The same measure renders in the same visual idiom at all three scales; a snapshot test
      enumerates each measure × scale and fails when one diverges from the grammar.
- [ ] `Why` expands inline on a claim, assumption, option and probability without navigating, shows
      the supporting citations and any `adjustments`, and returns focus on collapse.
- [ ] Verbal probability phrases come from the lexicon only, with no phrase hardcoded in a component;
      axe, visual-regression and terminology-guard passes hold across all three altitudes.

## Verification plan

```
cd frontend && npm test -- uncertainty language Why
make frontend-check && make frontend-build
E2E_MODE=fixture npx playwright test --config=e2e/playwright.config.ts
E2E_MODE=fixture npx playwright test --config=e2e/playwright.config.ts visual.spec.ts
make e2e-frontend
```

## Verification results

Not yet executed.

## Open questions

- Whether the answer headline's one honest sentence in SPEC-050 counts as a synthesised summary. It
  composes four measures into prose without producing a combined number; the test above must be
  written to permit the sentence and forbid the dial, and the boundary should be settled with
  SPEC-050 before either is approved.
