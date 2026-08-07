---
id: SPEC-049
title: The cast — voice attribution, margin objections, and dissent
phase: 9
status: implemented
depends_on: [SPEC-047, SPEC-048]
parallel_with: [SPEC-050, SPEC-054]
north_star_refs: ["5", "6", "15"]
last_updated: 2026-08-06
---

# SPEC-049 — The cast: voice attribution, margin objections, and dissent

## Summary

Makes the deliberation visible. Thirteen agents work a case, two Directors run on deliberately
different model families so that agreement between them carries information, and their disagreement
is reported rather than averaged — yet an agent is named in exactly two places in the whole UI, and
the second opinion is a card in a room most users never open. This spec attaches each objection to
the passage it attacks, promotes dissent to the answer, and gives every claim a voice instead of an
enum. It is the answer to "some users want to be more engaged": engagement is watching an argument,
not reading more prose.

## Motivation

North star Section 15 requires the interface to "distinguish clearly between sourced facts, agent
interpretation, user-supplied information, assumptions, calculations, and recommendations." Today
`BriefBlock.provenance` carries exactly that distinction and is rendered as a grey uppercase enum.
Section 6 (conceptual agent organization) describes the roles as an organization with a purpose;
`tracks.py` states it directly — "One Director on one model is a single point of epistemic failure
… the disagreement is reported, not averaged" — which is better product copy than anything currently
on screen. Phase 8 raises the stakes: SPEC-039 adds an independent reviewer on a third model family
whose dissent *blocks delivery*, and SPEC-043 adds user documents as a distinct provenance.

## Scope

- `frontend/src/copy/voices.ts` — a role/provenance → voice table under the existing terminology
  discipline: every `TaskRole` and every `provenance` value maps to a display voice and a one-line
  description of what that voice is for. Exhaustive by construction so a new value cannot render raw.
- `frontend/src/screens/Brief/MarginNotes.tsx` — objections rendered into SPEC-048's margin column,
  positioned against the section named by `ObjectionView.target_section`, carrying
  `resolution_status` as visual state (open, partially resolved, resolved, dismissed) and
  `materiality`. Open high-materiality objections are visually distinct from settled ones.
- `frontend/src/screens/Brief/Dissent.tsx` — a dissent surface above the answer, built for **three**
  voices, not two:
  - the two Directors' `track_divergence`, shown as two standing positions with the split named and
    never a midpoint;
  - phase 8 SPEC-039's independent reviewer, whose dissent blocks delivery and therefore renders as
    a harder state than a Director split — a blocked signature, not a caveat.
  The component is written to the three-voice shape now; SPEC-053 wires the reviewer's real artifact
  once phase 8 verifies.
- Voice attribution on every brief block, replacing the `provenance-stripe` enum, including
  `user_document` from SPEC-043 rendered as the user's own voice rather than an agent's.
- `frontend/src/narration/reducer.ts` extended: narrator lines name who is speaking and what they
  are contesting, using the same voice table.
- `frontend/src/screens/rooms/Challenges/ChallengesRoom.tsx` — the second-opinion card becomes a
  detail view of the dissent surface rather than the only place it exists.

## Out of scope

- The margin column itself (SPEC-048 owns the layout this renders into).
- Projecting phase 8's reviewer artifact and user-document evidence into `CaseView` (SPEC-053);
  this spec ships the components and their fixtures.
- Reactions on objections (SPEC-051).
- Any change to how divergence is computed. `tracks.py` is untouched.

## Design

The never-averaged rule is treated as a UI invariant with a test, not a convention. A blended
position is a plausible thing for a well-meaning component to render — a single "confidence" bar
across two disagreeing tracks, say — and it would silently destroy the property the dual-track design
exists to create. The test asserts that when `agreement` is false, both positions appear with their
own alternatives and no synthesised third value appears.

Voices are a table rather than a formatter so exhaustiveness is checkable: the test enumerates every
`provenance` value present in the schemas and fails on any without a voice. That is what keeps phase
8's new provenances from regressing the UI into rendering raw enums, which is the failure mode the
existing terminology guard was built to prevent.

Objections position against `target_section` because that field already exists and already carries
the association; nothing needs computing. Where a target section is absent or unknown, the note
falls back to the end of the brief rather than being dropped — an unplaced objection is still an
objection.

## Deliverables

- [x] `frontend/src/copy/voices.ts` — exhaustive role/provenance/source → voice table
- [x] `frontend/src/screens/Brief/MarginNotes.tsx` — objections against their target sections
- [x] `frontend/src/screens/Brief/Dissent.tsx` — three-voice dissent surface with blocking state
- [x] Voice attribution replacing provenance enums across the case surface and delivery
- [x] Narrator lines naming speaker and target, in `narration/reducer.ts`
- [x] Tests: `voices.test.ts`, `MarginNotes.test.tsx`, `Dissent.test.tsx`, e2e cast assertions

Deviations, all deliberate:

- The table covers a third vocabulary the sheet did not name: `SourceType`. `user_document` is a
  source type rather than a block provenance, so mapping only roles and provenances would have left
  the sheet's own `user_document` criterion unreachable.
- SPEC-047's `ROLE_VOICES` lived in `narration/reducer.ts`. It moved into `copy/voices.ts` rather
  than being duplicated, and the reducer re-exports `voiceFor`/`roleVoice` so SPEC-047's callers
  keep one import. Two voice tables would have drifted within a phase.
- Margin notes render into `.brief-passage`'s own margin (absolutely positioned beside the passage
  above 75 rem, inline below it) rather than into a separate margin column. A margin column narrower
  than its content is not a margin, and the association is to the passage, not to the page.

## Acceptance criteria

- [x] An objection whose `target_section` is `X` renders adjacent to section `X`; one with an
      unknown or absent target renders at the end of the brief and is never dropped.
- [x] `track_divergence.agreement: false` renders the dissent surface with both positions and their
      alternatives; `true` renders no dissent surface.
- [x] **Never averaged**: with two disagreeing tracks, no synthesised midpoint, blended confidence
      or single merged position appears in the DOM.
- [x] A blocking reviewer dissent renders distinctly from a Director split and the delivery
      signature is disabled while one is open, asserted against a fixture.
- [x] Every `provenance` value present in `schemas/` maps to a voice; adding an unmapped value fails
      the test rather than rendering a raw enum. `user_document` renders as the user's voice.
- [x] Narrator lines name the acting role and, where the event identifies one, its target.
- [x] Axe, visual-regression and terminology-guard passes for every touched surface;
      `make frontend-check` and `make e2e-frontend` green.

## Verification plan

```
cd frontend && npm test -- voices MarginNotes Dissent narration
make frontend-check && make frontend-build
E2E_MODE=fixture npx playwright test --config=e2e/playwright.config.ts
E2E_MODE=replay npx playwright test --config=e2e/playwright.config.ts
make e2e-frontend
```

## Verification results

| Command | Result |
| --- | --- |
| `cd frontend && npm test` | 21 files, **231 passed** (was 208; +23 for voices, margin notes, dissent, blocked signature) |
| `make frontend-check` | green |
| `make frontend-build` | green — 352.08 kB JS |
| `E2E_MODE=fixture …` (chromium, chromium-dark, mobile, reduced-motion) | **130 passed** in 3m30s |
| `E2E_MODE=replay …` | **9 passed** |
| `E2E_MODE=stub …` | **5 passed** |
| `make check` | **941 passed**, 18 deselected — no engine change, as intended |

### Exhaustiveness is checked against the Python source

`voices.test.ts` reads `TaskRole` and `SourceType` out of `orchestrator/artifacts/common.py` and the
`PROVENANCE_*` constants out of `orchestrator/service/caseview.py`, then asserts a voice for each —
38 assertions generated from the enums rather than from a hand-kept list. A hand-kept list drifts
silently, and the drift's failure mode is the exact one the terminology guard exists to prevent:
`assumption_analyst` rendered at a reader. Adding a role in Python now fails this test until someone
decides what that role's voice is.

The test also asserts the *finder* works — `expect(roles.length).toBeGreaterThanOrEqual(15)` — so a
regex that stops matching produces a failure rather than a vacuous pass over an empty list.

### Never averaged, asserted three ways

The dual-track design exists to make agreement informative, and a single blended confidence bar
would silently destroy that. The test asserts, on two tracks at 71% and 64%: both numbers present,
neither 67% nor 68% present, no `combined|averaged into|merged|midpoint` language, and exactly two
`.dissent-position` elements — never a synthesised third.

### What the fixture exercises

The completed fixture has `agreement: true`, so the case surface renders no dissent surface at all —
asserted, because inventing disagreement is as bad as hiding it. Its single objection targets
`preliminary_recommendation.rationale[0]`, which is *not* a brief-section key, so it exercises the
fallback path: the note renders at the end of the brief under "These objections name a part of the
brief that is not in it. They are shown here rather than dropped."

### Left for SPEC-053, by the sheet's own plan

`IndependentReview` is written by the engine and rendered into the `independent_review` brief
section, but it is not yet a structured field on `CaseView`. `Dissent.tsx` consumes the shape and
`independentReviewFrom(view)` is the single adapter that changes when SPEC-053 lands the projection;
until then it returns `null` and no dissent surface renders. The blocking behaviour — including the
delivery signature being taken away rather than left live beside a dissent — is asserted against
fixtures in `Dissent.test.tsx` and `Delivery.test.tsx`, so SPEC-053 wires a tested component rather
than an untested one.

## Open questions

- **Whether a blocking dissent should hide the recommendation** — resolved as recommended: the
  recommendation stays readable and the block is stated above it, with the conclusion that reviewer
  would reach instead. What is removed is the *signature*, not the reading: `Delivery.tsx` renders
  no Accept button while a dissent stands, and says why. Hiding the conclusion would have made the
  block unarguable, which is the opposite of what a dissent is for — a reader has to be able to see
  both positions to judge the disagreement.
