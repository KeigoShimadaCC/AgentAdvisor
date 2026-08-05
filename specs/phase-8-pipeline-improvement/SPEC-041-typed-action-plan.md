---
id: SPEC-041
title: Typed action plan
phase: 8
status: draft
depends_on: [SPEC-039]
parallel_with: [SPEC-043]
north_star_refs: ["3", "14", "16"]
last_updated: 2026-08-04
---

# SPEC-041 — Typed action plan

## Summary

Replaces `FinalRecommendation.next_actions: list[NonEmptyStr]` with a typed `NextAction` carrying
owner, date, first step, cost, dependencies and urgency rationale. This is the smaller half of the
mobilization work; SPEC-042 builds the post-delivery lifecycle on top of it.

`depends_on: [SPEC-039]` is file-level sequencing — SPEC-038, SPEC-039 and this spec all extend
`orchestrator/artifacts/recommendations.py`.

## Motivation

Measured against the Decision Quality chain — appropriate frame, creative alternatives, reliable
information, clear values and tradeoffs, sound reasoning, **commitment to action** — the pipeline
scores well on five elements and has the sixth essentially absent. The chain is only as strong as
its weakest link. North star Section 3 item 11 promises "practical next actions" and Section 16
requires them "ordered by urgency or information value"; a bare list of sentences satisfies neither
ordering nor practicality, and cannot be acted on without the reader supplying everything that makes
an action executable.

This is the one breaking change in Phase 8 with a genuinely contained blast radius: `next_actions`
appears at roughly eight real code sites.

## Scope

- `orchestrator/artifacts/recommendations.py`:
  - `NextAction` — `action`, `owner`, `by_date`, `first_step`, `estimated_cost` (optional),
    `depends_on` (list of other action ids, optional), `why_now`, `action_id` (`N-` prefixed).
  - `FinalRecommendation.next_actions: list[NextAction] = Field(min_length=1)` — **breaking**.
  - Validator: `depends_on` entries must resolve to declared `action_id`s, and the dependency graph
    must be acyclic.
- `orchestrator/artifacts/common.py` — `ActionId` type and the `N-` prefix, alongside `E-`/`A-`/`T-`/`O-`.
- `orchestrator/render.py:237` — render the action table.
- `orchestrator/service/caseview.py:699-704` — `next_actions` blocks carry the structured fields.
- `orchestrator/stub_backend.py:504` — updated fixture.
- `orchestrator/gates.py` — `action_plan.missing_owner`, `action_plan.no_near_term_action`.
- `cursor/roles/synthesizer.md` — contract and a worked example that validates.
- `frontend/src/screens/Delivery/` — render owner and date; update `Delivery.test.tsx`.
- `frontend/src/copy/terms.ts` — terms for the new fields.
- Migration of all affected fixtures: `tests/fixtures/artifacts/final_recommendation.*.yaml` (4),
  `tests/fixtures/roles/synthesis/replay/*.yaml` (2), and the inline constructions in
  `tests/test_memory.py`, `tests/test_verification.py`, `tests/test_projection.py`.

## Out of scope

- The monitoring plan and any post-delivery lifecycle. That is SPEC-042.
- Calendar, task-tracker or notification integrations.
- Owners other than free text. There is no identity model in this system and this spec does not
  introduce one.

## Design

**Owner semantics.** For a single-user personal tool the owner is usually the user, but not always:
"ask your accountant to confirm the treatment" has a different owner, and naming it is the point.
Free text, defaulting to the decision owner from `DecisionSpec`.

**Dates are relative, resolved at synthesis.** The synthesizer emits concrete dates computed from
the case's completion date rather than durations, so the delivered report is unambiguous. The
`by_date` must not precede the case completion date, and should respect
`DecisionSpec.deadline` where one exists — a gate check covers the first, and the second is
reported as a finding rather than enforced, because an action may legitimately fall after the
decision itself.

**`first_step` is the field that makes this useful.** An action a reader cannot start today is not
an action. It must be something completable in a single sitting: a specific call to make, a
document to request, a number to look up.

**Breaking-change procedure.** Change the model, run `make schemas` and `make frontend-types`,
migrate the nine fixture and test sites, update the synthesizer contract, then run
`tests/test_role_contracts.py` — which will fail until the worked example matches, by design.

## Deliverables

- [ ] `NextAction` model with dependency validation, and `ActionId` in `common.py`
- [ ] Renderer action table and caseview blocks
- [ ] Two gate checks
- [ ] `cursor/roles/synthesizer.md` contract and worked example
- [ ] Delivery screen rendering and updated frontend test
- [ ] All nine fixture and test sites migrated
- [ ] Regenerated `schemas/` and `frontend/src/generated/`

## Acceptance criteria

- [ ] `make check` and `make frontend-check` are green.
- [ ] `NextAction` rejects a cyclic `depends_on` graph and an unresolvable `depends_on` id.
- [ ] A `FinalRecommendation` with an action missing an owner produces exactly one
      `action_plan.missing_owner` finding.
- [ ] A plan whose earliest `by_date` is more than 30 days out produces
      `action_plan.no_near_term_action`.
- [ ] A stub pipeline run reaches `done` and `final_recommendation.md` contains an action table with
      owner, date and first step columns.
- [ ] `tests/test_role_contracts.py` passes for `synthesizer.md`.
- [ ] The Delivery screen shows owner and date for each action, asserted in `Delivery.test.tsx`.

## Verification plan

`make check`, `make frontend-check`, a stub pipeline run to `done` with the rendered report
inspected, and one live `--budget-profile small` case confirming the synthesizer produces
schema-valid typed actions without coercion intervention.

## Verification results

Not yet executed.

## Open questions

None.
