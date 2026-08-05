---
id: SPEC-050
title: Commissioning and checkpoints — the first five minutes and the two signatures
phase: 9
status: draft
depends_on: [SPEC-046, SPEC-048]
parallel_with: [SPEC-049]
north_star_refs: ["3", "14", "15"]
last_updated: 2026-08-05
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
  - a watch-or-notify question — sit with the deliberation, or be pinged — stored as the user
    preference SPEC-051 consumes.
- `frontend/src/copy/effort.ts` — effort profiles whose time ranges are computed from recorded
  history via `MemoryStore.prior_cases()` (p50–p90 per profile), served through a small addition to
  the existing calibration read, and labelled as measured. With no history, honest fallback copy
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

- [ ] `NewDecision.tsx` — immediate routing on 202, draft persistence, intake/framing narration,
      watch-or-notify preference
- [ ] `frontend/src/copy/effort.ts` + the history-derived estimate read; hardcoded ranges removed
      from `terms.ts`
- [ ] `ScopeCheckpoint.tsx` — restatement-first disclosure, consequence subhead, objective-weight slot
- [ ] `Delivery.tsx` — answer-first order, uncertainty behind disclosure, send-back confirmation,
      action-plan slot
- [ ] Component tests for both sheets and the commissioning flow
- [ ] `frontend/e2e/stub.spec.ts` extended: fast-sign and full-review paths produce identical artifacts

## Acceptance criteria

- [ ] **Signing fast and signing after expanding every section produce byte-identical
      `framing_approval.yaml` and `final_approval.yaml`**, asserted in stub mode against disk.
- [ ] Reloading mid-commission restores the prompt and effort selection; a successful creation
      clears the draft.
- [ ] After `POST /api/cases` the case surface renders and narrates intake before framing completes;
      no disabled-button wait remains.
- [ ] No hardcoded minute range remains in `frontend/src/copy/`; ranges render as measured p50–p90
      from recorded history, and an empty history renders the honest fallback rather than a number.
- [ ] The scope sheet shows the restatement and its two actions above the fold with the other four
      sections collapsed and counted; the consequence line renders in the subhead.
- [ ] Delivery renders the honest sentence, then key reasons, then tripwires, with the four
      encodings behind disclosure; send-back requires a confirmation naming the cap and is disabled
      once spent.
- [ ] Axe, visual-regression and terminology-guard passes on both sheets and commissioning;
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

Not yet executed.

## Open questions

- The honest sentence on delivery composes four measures into one claim. Its template must not
  imply more precision than the encodings carry, and should be reviewed against north star Section 9
  (probability and confidence policy) before approval.
- Whether measured effort ranges are served from the SPEC-046 calibration endpoint or a sibling
  read. Recommend a sibling `GET /api/effort-history` to keep calibration's contract single-purpose.
