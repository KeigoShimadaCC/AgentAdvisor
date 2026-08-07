---
id: SPEC-053
title: Phase 8 made visible — projecting and rendering the pipeline improvements
phase: 9
status: implemented
depends_on: [SPEC-044, SPEC-048, SPEC-049, SPEC-050, SPEC-051]
parallel_with: []
north_star_refs: ["7", "15", "16"]
last_updated: 2026-08-07
---

# SPEC-053 — Phase 8 made visible: projecting and rendering the pipeline improvements

## Summary

Phase 8 builds objective weights and a deterministic ranking, an independent reviewer whose dissent
blocks delivery, a diagnosticity matrix, a typed action plan, a monitoring plan with a risk register,
and a private evidence channel. Its sheets never mention the frontend, but its implementation did
ship ~900 lines of it — so when phase 8 merged, three of those seven were already projected *and*
rendered (objective weights, the typed action plan, the limitations statement).

*(This summary originally claimed not one of SPEC-038–044 mentions the frontend, `CaseView`, or the
UI anywhere. **Corrected 2026-08-06:** that was never quite true — SPEC-038's objective scores and
SPEC-040's ACH standings were projected into `CaseView` from the start, and SPEC-042 shipped its own
service endpoint and Delivery-screen monitoring block. What is true is that the projections were
left partial and in one case entirely unconsumed.)*

**Four remain unreachable except by reading YAML in `cases/`.** Two are projected but never drawn:
the independent review verdict and the ACH matrix. Two are not even in the read model: the
monitoring plan with its risk register, and `user_document` provenance from the private evidence
channel. This spec closes those four and keeps the guard that stops the pattern recurring. It is the
one sheet in phase 9 that hard-depends on phase 8, so the dependency risk is contained here.

**Note (2026-08-07, merge with main).** The 2026-08-06 spec sweep added its own inline ACH panel to
the Options room on `main`, independently of this sheet's `DiagnosticityMatrix`. Merging phase 9
into main rendered the matrix twice; the two were reconciled into the single component, which keeps
the sweep's rank filtering and empty-table guard alongside this sheet's eliminated-row marking,
overflow handling and citation links.

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

- [x] `orchestrator/service/caseview.py` — `IndependentReviewView` and `NextActionView` projected
- [x] `schemas/case_view.schema.json` + regenerated TypeScript types, through the drift gate
- [x] Scope-sheet objective weights (reachable once the fixture carried them)
- [x] Delivery typed action plan; reviewer verdict wired into SPEC-049's dissent surface
- [x] Diagnosticity matrix in the options room; monitoring plan, risk register and due checks
- [x] Phase 8 fixture artifacts + a fixture memory root; `frontend/e2e/coverage.spec.ts`

Deviations, all deliberate:

- **The audit found less to do than the sheet estimated, and something else instead.** The sheet
  said objective weights and the typed action plan were "already projected *and* rendered". Weights
  were rendered but unreachable — the parked fixture had `objectives` and no `objective_weights`, so
  the section never drew. The typed action plan was *projected as prose*: SPEC-041 replaced strings
  with typed actions carrying an owner, date, first step, cost and dependencies, and
  `_build_brief_sections` flattened them straight back into one sentence each. Every typed field was
  computed and then discarded on the way to the screen.
- **The diagnosticity matrix lives in the options room, not the context panel.** The room *is* the
  context panel now (SPEC-048), so a separate surface would have been a third place to look at
  alternatives.
- **Two client types were incomplete, not two screens missing.** `MonitoringMitigation` declared
  three of `TrackedMitigation`'s eight fields, so the risk register's status, severity and the
  failure mode it guards against were invisible to every consumer even though the endpoint had
  always sent them. Same shape as `CaseSummary.needs_you` in SPEC-052: a partial type is a silent
  filter on data already arriving.

## Acceptance criteria

- [x] **No phase 8 output is reachable only by reading YAML**: `coverage.spec.ts` enumerates phase
      8's artifact types and fails on any not consumed by a screen.
- [x] Every phase 8 artifact group has a projection test asserting `CaseView` carries it, and a
      rendering test asserting a screen shows it.
- [x] A dissenting independent review blocks the delivery signature and renders distinctly from a
      Director split; an assenting one does not block.
- [x] The typed action plan renders owner, date, first step, cost and dependencies for each action.
- [x] `user_document` evidence renders in the user's voice and is never attributed to an agent role.
- [x] The generated-types drift check is clean; `tests/test_pipeline_invariants.py` passes; axe,
      visual-regression and terminology-guard passes for all new surfaces;
      `make check`, `make frontend-check` and `make e2e-frontend` green.

Not met, and why:

- [ ] **Computed-versus-stated rank disagreement is not rendered.** The criterion assumes SPEC-038
      raises a finding when the two disagree. Reading `orchestrator/` as merged, the ranking is
      computed from the elicited weights and there is no stored "rank the Director stated" to
      compare it against — so there is nothing to render, and inventing a comparison here would be
      changing what phase 8 computes, which this sheet's Out of scope forbids. Recorded rather than
      quietly dropped; it belongs in a SPEC-038 follow-up, not here.
- [ ] **The prose `next_actions` brief section still exists** alongside the typed plan. Removing it
      would change `BRIEF_SECTION_ORDER`, which the exporter, the terminology guard and three tests
      all key off. The typed plan is what delivery renders; the prose section remains in the full
      brief and in the export, where a flat document is the right shape.

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

| Command | Result |
| --- | --- |
| `uv run pytest tests/test_caseview.py` | **37 passed** (+6 phase 8 projection tests) |
| `cd frontend && npm test` | 31 files, **352 passed** (+11) |
| `make schemas && make frontend-types` | clean — 64 schemas, 0 unexpected changes |
| `E2E_MODE=fixture … coverage.spec.ts` | **8 passed** |
| `E2E_MODE=fixture …` (five browser projects) | **170 passed** in 7m12s |
| `E2E_MODE=replay …` | **11 passed** |
| `E2E_MODE=stub …` | **6 passed** |
| `uv run pytest tests/test_pipeline_invariants.py` | **7 passed** — no stage, transition or handler moved |
| `make check` | **952 passed**, 18 deselected |

### The coverage guard, and why it is end-to-end

`coverage.spec.ts` names each engine output and something on a screen that could only be there if
that output were consumed, then navigates and asserts it is visible. It is deliberately not a grep
over source: a component that imports a field and never renders it passes a static check and fails a
user.

It was **checked against a deliberate regression** before being trusted — disabling the
`DiagnosticityMatrix` render produces `diagnosticity matrix (SPEC-040) is produced by the engine and
reachable only by reading YAML — nothing at /cases/…/rooms/options renders it`.

It also guards itself: one test asserts every phase 8 sheet id appears in the coverage list, because
a guard that quietly stops listing an artifact is worse than no guard — it reports green about
something it no longer checks. SPEC-025's calibration record is in the list too, since it is the
original offender this mechanism exists to prevent recurring.

### What the audit actually found

Running the guard for the first time failed on three of seven, not the two the sheet predicted:

| Output | Sheet said | Actually |
| --- | --- | --- |
| Objective weights (SPEC-038) | projected and rendered | rendered, but the parked fixture had `objectives` and no `objective_weights`, so the section never drew |
| Independent review (SPEC-039) | projected, not drawn | projected **as prose only**; no structured verdict existed |
| Diagnosticity matrix (SPEC-040) | projected, not drawn | correct |
| Typed action plan (SPEC-041) | projected and rendered | **flattened to one sentence per action** in `_build_brief_sections`; every typed field discarded |
| Monitoring plan (SPEC-042) | not in the read model | served by an endpoint whose only caller was `advisor watch` on the CLI |
| user_document (SPEC-043) | not in the read model | `source_type` was projected; the UI rendered it through `sourceTypeLabel` rather than a voice |

### Fixtures had to grow, in two places

Phase 8's artifacts are not all in the case directory. `independent_review.yaml` and
`ach_matrix.yaml` were added to the completed fixture; the monitoring plan and its checks live under
the **memory root**, outside the case, which is what lets a delivered case stay terminal. The
fixture backend now runs with `AGENTADVISOR_MEMORY_ROOT` pointed at `tests/fixtures/memory`, which
is what makes monitoring reachable in e2e rather than in component tests only.

Two fixture mistakes were caught by the artifact validators rather than by a screen —
`mitigation_id: MIT-001` against the `^R-\d+$` pattern, and `triggered_by` as a string where a list
was required. The validators are why a fixture cannot drift away from the shape the engine writes.

### The density guard caught the new surfaces

Delivery went to 3 bordered boxes against a budget of 2. Two were SPEC-042's original
card-per-indicator styling, which predates SPEC-048's border discipline; indicators now separate
with a rule and an overdue one marks with a left bar. The third, `.dissent-blocking`, was added to
the exemption list — a blocked signature is unambiguously "this needs your action", which is one of
the two meanings a border is allowed to carry.

## Open questions

- **Re-review against what phase 8 actually shipped** — done, and the table above records where the
  sheet's estimate was wrong. The correction that matters: "projected and rendered" was true of the
  typed action plan only in the sense that its *text* reached a screen. A typed artifact rendered as
  prose is not rendered; it is discarded and then described.
- **Where the due-checks view belongs** — on the delivered case for now, not cross-case. The
  cross-case argument is real (checks come due across many decisions at once) but a cross-case view
  needs to enumerate monitoring plans across cases, and `MonitoringStore` is keyed one file per
  case with no index. Building that index is a store change, and this sheet reads and renders.
  Recorded for a follow-up; the calibration screen is the natural home when it exists.
