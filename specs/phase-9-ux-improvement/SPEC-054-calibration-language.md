---
id: SPEC-054
title: The calibration language — one uncertainty vocabulary at every altitude
phase: 9
status: implemented
depends_on: [SPEC-045, SPEC-048]
parallel_with: [SPEC-049]
north_star_refs: ["9", "15", "16"]
last_updated: 2026-08-07
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

- [x] `frontend/src/uncertainty/language.ts` — the encoding grammar, three scales
- [x] `frontend/src/uncertainty/Measure.tsx` — the one renderer every measure goes through
- [x] `frontend/src/uncertainty/Why.tsx` — expand-in-place support disclosure
- [x] The five existing uncertainty components rebuilt on the shared grammar and tokens
- [x] `frontend/src/copy/uncertainty.ts` — verbal phrase ↔ range mapping in the lexicon
- [x] Application across all three altitudes: summary on the answer, inline against claims, full on delivery
- [x] Tests: `language.test.tsx` (37), `e2e/uncertainty.spec.ts` (13)

Deviations, all deliberate:

- **`Measure.tsx` was not in the sheet's deliverables and is the load-bearing piece.** A grammar
  expressed as data still needs one renderer, or five components read the same table and drift in
  how they draw it. Every uncertainty rendering in the app now goes through this component, which is
  what makes "the same measure looks the same everywhere" a fact rather than a convention.
- **One test file, not two.** `Why` and the grammar share fixtures and the same invariant; splitting
  them would have duplicated the encoder setup for no isolation.
- **The five rebuilds keep every threshold and every phrase unchanged.** `copy/uncertainty.ts`
  *moved* the bands from `copy/terms.ts` rather than re-choosing them. Redrawing a band boundary
  would silently change what every historical case is reported to have said, and this spec is
  presentation only.

## Acceptance criteria

- [x] **No synthesised summary**: no screen renders a single combined confidence, average or overall
      score derived from more than one of the four measures — asserted across nine routes.
- [x] A point estimate and an interval estimate render visibly differently, and an interval never
      renders as a point; the two produce distinguishable DOM.
- [x] `AssessedStability` renders `runs_supporting` of `runs_total` as that many countable marks —
      exhaustively in `language.test.tsx`, and swept across every route in e2e (see the note below
      on what the fixtures actually contain).
- [x] `NotAssessed` renders the explicit stamp with its `reason` and is never shown as zero, empty,
      absent, or a low value.
- [x] The same measure renders in the same visual idiom at all three scales; the grammar's kind is
      enumerated for every measure × scale and fails when one diverges.
- [x] `Why` expands inline without navigating, shows supporting citations and any `adjustments`, and
      returns focus on collapse.
- [x] Verbal probability phrases come from the lexicon only, with no phrase hardcoded in a component;
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

| Command | Result |
| --- | --- |
| `cd frontend && npm test` | 32 files, **389 passed** (+37) |
| `make frontend-check` | green |
| `make frontend-build` | green |
| `E2E_MODE=fixture … uncertainty.spec.ts` | **13 passed** |
| `E2E_MODE=fixture …` (five browser projects) | **183 passed** in 7m42s |
| `E2E_MODE=replay …` | **11 passed** |
| `E2E_MODE=stub …` | **6 passed** |
| `make check` | **952 passed**, 18 deselected — presentation only, no engine change |

### The rule, and how it is held

"No single confidence is ever synthesised" is asserted three ways, because it is the property the
whole data model exists to protect and a convention would not survive the first feature request for
a summary dial:

1. **Structurally.** Four measures, four encoding kinds — `band`, `grade`, `countable`, `range` —
   and no encoder takes two values. An encoding that *could* accept two measures is the first step
   to one that averages them.
2. **In the rendered text**, across nine routes: no "overall confidence", "combined score",
   "average confidence", "composite", "aggregate".
3. **Against a deliberate regression.** Adding `Overall confidence: 68%` to the summary component
   fails the sweep with `/cases/… renders a synthesised summary matching /overall confidence/i`.

### The boundary with SPEC-050's honest sentence

The sheet's open question. Settled: the sentence is permitted, a dial is not, and the test encodes
the distinction rather than leaving it to judgement. The sentence composes the four measures into
**prose containing no digits at all** — `honestSentence.test.ts` asserts `not.toMatch(/\d/)` — so
what it produces is arguable ("moderate confidence and thin evidence") where a number is not
("0.68"). The forbidden list matches number-bearing phrasings; it does not match the sentence.

### Why stability is countable and not a percentage

"9 of 10 runs" is a fact about what was done. "90%" is a number, and a number sits next to a
confidence of 0.72 and an evidence score of 0.55 and invites exactly the arithmetic that four
separate encodings exist to prevent. The marks are drawn one per run and the accessible name says
the count in words.

### What the fixtures actually contain

The e2e countable check reports `countable marks validated: 0`, and that is correct rather than a
gap: the completed fixture's `model_stability` is `0 of 1`, which the engine treats as the sentinel,
and `fixture.spec.ts` depends on exactly that to prove a sentinel never renders as a bare number.
Manufacturing an assessed stability to make this route non-empty would mean contradicting a test
that exists for a good reason. The exhaustive count check therefore lives in `language.test.tsx`,
which drives the component over four combinations including the 0-of-5 and 1-of-1 edges; the e2e
sweep validates any mark that appears on any route, and honestly reports when there are none.

### One accessibility defect this found

Composing the `Why` button's accessible name from visible text plus an `sr-only` span produced
`"Why?for this claim"` — JSX trims the leading whitespace in a text node, so a screen reader would
say it as one word. Fixed with an explicit `aria-label`. Worth recording because it was invisible in
the rendered page and visible only in the accessibility tree.

`tsc` also caught an unused `@ts-expect-error` that `npm test` did not, because vitest does not
typecheck — a reminder that `make frontend-check` is not a slower `npm test`.

## Open questions

- **Whether SPEC-050's honest sentence counts as a synthesised summary** — resolved: it does not,
  and the boundary is encoded rather than agreed. A sentence carrying no digits cannot be mistaken
  for a measurement and can be argued with; a number cannot. `honestSentence.test.ts` asserts the
  sentence contains no digit, and `uncertainty.spec.ts` forbids number-bearing summary phrasings
  across every route. The two tests together are the boundary, so neither sheet has to remember it.
