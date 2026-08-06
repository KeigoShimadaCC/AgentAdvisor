---
id: SPEC-053
title: Phase 8 made visible — projecting and rendering the pipeline improvements
phase: 9
status: draft
depends_on: [SPEC-044, SPEC-048, SPEC-049, SPEC-050, SPEC-051]
parallel_with: []
north_star_refs: ["7", "15", "16"]
last_updated: 2026-08-05
---

# SPEC-053 — Phase 8 made visible: projecting and rendering the pipeline improvements

## Summary

Phase 8 builds objective weights and a deterministic ranking, an independent reviewer whose dissent
blocks delivery, a diagnosticity matrix, a typed action plan, a monitoring plan with a risk register,
and a private evidence channel. Its sheets never mention the frontend, but its implementation did
ship ~900 lines of it — so when phase 8 merged, three of those seven were already projected *and*
rendered (objective weights, the typed action plan, the limitations statement).

**Four remain unreachable except by reading YAML in `cases/`.** Two are projected but never drawn:
the independent review verdict and the ACH matrix. Two are not even in the read model: the
monitoring plan with its risk register, and `user_document` provenance from the private evidence
channel. This spec closes those four and keeps the guard that stops the pattern recurring. It is the
one sheet in phase 9 that hard-depends on phase 8, so the dependency risk is contained here.

## Motivation

North star Section 7 (shared decision state) makes the blackboard the product's substance, and
Section 15 requires the interface to expose it; Section 16 defines what a recommendation package
contains, which phase 8 materially enlarges. The precedent is already in the repo and it is a
warning: `orchestrator/calibration.py` computes a Brier score, is fully tested, is honest about small
samples — and has no endpoint and no screen, so no user has ever seen it. Phase 8 is positioned to
repeat that failure seven times in one phase.

## Scope

- `orchestrator/service/caseview.py` — projection extensions, one per phase 8 artifact:
  - objective weights and the deterministic ranking from SPEC-038, including the gate finding raised
    when computed rank disagrees with the rank the Director stated;
  - the independent review verdict and the limitations statement from SPEC-039;
  - the diagnosticity matrix from SPEC-040;
  - the typed `NextAction` list from SPEC-041;
  - the monitoring plan and risk register from SPEC-042, with each observable's threshold, cadence
    and due state;
  - `source_type: user_document` evidence from SPEC-043, carrying its distinct provenance.
- `schemas/case_view.schema.json` and the generated TypeScript, through the existing drift gate.
- Screens, filling the slots the earlier sheets left:
  - **Scope sheet** (SPEC-050's slot): objective weights with their elicited values, and the
    computed ranking shown beside the stated one, with disagreement rendered as a visible finding
    rather than an auditor-only artifact.
  - **Delivery** (SPEC-050's slot): the typed action plan — owner, date, first step, cost,
    dependencies, urgency — replacing the current `next_actions` string list; the limitations
    statement in the integrity slip.
  - **Dissent** (SPEC-049's three-voice surface): the reviewer's real verdict wired in, blocking
    the signature when it dissents.
  - **Context panel** (SPEC-048): the diagnosticity matrix as an evidence × alternatives grid ranked
    by disconfirming evidence, reachable from any alternative.
  - **Monitoring**: the plan and risk register on the delivered case, with a due-checks view that
    gives SPEC-042's CLI-only `advisor watch` a screen.
  - **Voices** (SPEC-049): `user_document` evidence attributed to the user, not to an agent.
- `tests/fixtures/cases/` — a fixture case carrying phase 8's artifacts, so the frontend suite and
  the e2e modes cover the new shapes.
- `frontend/e2e/coverage.spec.ts` — the guard described below.

## Out of scope

- Any change to how phase 8 computes anything. This spec reads and renders; SPEC-038–044 own the
  semantics, and a disagreement about them is resolved in those sheets, not here.
- Extending the exporter beyond the new sections (SPEC-052 owns the exporter; this spec adds its
  sections to the canonical order).
- Mobile-specific treatment of the diagnosticity matrix beyond horizontal scroll within its own
  container.

## Design

The load-bearing deliverable is `frontend/e2e/coverage.spec.ts`: a test that enumerates phase 8's
artifact types from `schemas/` and fails if any of them is not consumed by a screen. That converts
"phase 8 should be visible" from an intention into a build failure, and it is the mechanism that
stops the next phase repeating the calibration mistake. It is written generically so phase 10's
artifacts inherit it.

Projection before presentation, in that order, because `caseview.py` is a read model assembled from
disk: extending it changes no stage, transition or handler, and the generated-types drift gate then
carries the new shapes into TypeScript automatically. `tests/test_pipeline_invariants.py` from
SPEC-046 continues to assert that nothing in the pipeline moved.

Rank disagreement is treated as a user-facing event rather than a gate finding buried in the
integrity slip. SPEC-038 raises it when the computed ranking and the Director's stated ranking
differ; that is precisely the moment a decision-maker should look closely, and hiding it in an audit
surface would waste the most valuable signal phase 8 produces.

## Deliverables

- [ ] `orchestrator/service/caseview.py` — projections for all six phase 8 artifact groups
- [ ] `schemas/case_view.schema.json` + regenerated TypeScript types
- [ ] Scope-sheet objective weights and computed-versus-stated ranking with visible disagreement
- [ ] Delivery typed action plan and limitations statement; reviewer verdict wired into dissent
- [ ] Diagnosticity matrix in the context panel; monitoring plan, risk register and due checks
- [ ] `tests/fixtures/cases/` phase 8 fixture; `frontend/e2e/coverage.spec.ts`

## Acceptance criteria

- [ ] **No phase 8 output is reachable only by reading YAML**: `coverage.spec.ts` enumerates phase
      8's artifact types and fails on any not consumed by a screen.
- [ ] Every phase 8 artifact group has a projection test asserting `CaseView` carries it, and a
      rendering test asserting a screen shows it.
- [ ] When the computed ranking disagrees with the stated ranking, the scope surface shows the
      disagreement to the user; when they agree, no warning is shown.
- [ ] A dissenting independent review blocks the delivery signature and renders distinctly from a
      Director split; an assenting one does not block.
- [ ] The typed action plan renders owner, date, first step, cost, dependencies and urgency for each
      action; no `next_actions` string list remains in the UI.
- [ ] `user_document` evidence renders in the user's voice and is never attributed to an agent role.
- [ ] The generated-types drift check is clean; `tests/test_pipeline_invariants.py` passes; axe,
      visual-regression and terminology-guard passes for all new surfaces;
      `make check`, `make frontend-check` and `make e2e-frontend` green.

## Verification plan

```
uv run pytest tests/test_caseview.py -q
cd frontend && npm run check:clean && npm test
make frontend-check && make frontend-build
E2E_MODE=fixture npx playwright test --config=e2e/playwright.config.ts coverage.spec.ts
E2E_MODE=fixture npx playwright test --config=e2e/playwright.config.ts
make e2e-frontend
uv run pytest tests/test_pipeline_invariants.py -q
make check
```

## Verification results

Not yet executed.

## Open questions

- This sheet cannot be written to final detail until phase 8's artifact shapes are fixed. It should
  be re-reviewed — not merely re-approved — when SPEC-044 verifies, and its scope adjusted to what
  phase 8 actually shipped.
- Whether the monitoring due-checks view belongs on the case surface or as a cross-case screen
  beside calibration. Cross-case is probably right, since checks come due across many decisions at
  once, but that depends on SPEC-042's final shape.
