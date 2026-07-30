---
id: SPEC-011
title: Planner role
phase: 3
status: verified
depends_on: [SPEC-006]
parallel_with: [SPEC-010, SPEC-012, SPEC-013, SPEC-014, SPEC-015, SPEC-016, SPEC-017]
north_star_refs: ["6.2", "8"]
last_updated: 2026-07-31
---

# SPEC-011 — Planner role

## Summary

The Planner proposes prioritized, dependency-aware investigation tasks; deterministic code (SPEC-009) decides execution. Also covers the Planner's repair-mode variant that commissions only objection-resolving work.

## Motivation

North star 6.2 and Stage 4: every task must state why it matters to the decision and carry the fields the priority formula needs; the Planner recommends, the orchestrator disposes.

## Scope

- `cursor/roles/planner.md`: mandate to decompose the decision into investigation areas and emit `TaskRecord` proposals, each with question, why_it_matters, expected_information_gain, materiality, estimated cost tier, required role, inputs, required_output, completion_criteria, dependencies; hard cap of 10 proposals per invocation; explicit instruction to propose nothing when open tasks already cover the material gaps (Section 5.1 tests).
- Repair mode: same role md, `task.yaml` flag `mode: repair` with the unresolved objections projected; proposals must reference the objection IDs they resolve; cap 4.
- `cursor/roles/planner.yaml` (efficient model; projection: decision spec, assumption gaps, open objections, existing task graph summary).
- Golden fixtures: post-framing planning and repair-mode planning; structural assertions.

## Out of scope

Dispatch, budget gating, cycle detection (SPEC-009), stop decision (SPEC-008).

## Design

Planner output is a `TaskProposalBatch` (new small wrapper model listing TaskRecords with proposed dependencies by index, resolved to `T-` IDs by the orchestrator on acceptance). Orchestrator-side acceptance filter (part of this spec, ~30 lines): reject proposals missing priority fields or referencing unknown roles, dedupe near-identical questions by normalized string match; rejections audited.

## Deliverables

- [x] `cursor/roles/planner.md`
- [x] `TaskProposalBatch` model + schema export
- [x] Acceptance filter in `orchestrator/planning.py`
- [x] `cursor/roles/planner.yaml`
- [x] `tests/test_role_planner.py` + fixtures; live mini-run test

## Acceptance criteria

- [x] Fixture replay: all proposals schema-valid, ≤10, every task names role + completion criteria + priority fields.
- [x] Repair fixture: every proposal references ≥1 open objection ID; ≤4 proposals.
- [x] Acceptance filter rejects a fixture batch containing an unknown role and a near-duplicate, keeping the rest.
- [x] Live mini-run on the investment fixture yields a valid batch in ≤2 attempts.
- [x] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_role_planner.py -q
uv run pytest -m live -k planner -q
```

## Verification results

**2026-07-31 — PASS.** `cursor/roles/planner.md` states the priority formula (`materiality_weight * probability_of_changing_conclusion / estimated_cost`) and the marginal-value gate explicitly so the agent's numbers are operational, not decorative. `orchestrator/planning.py` implements the acceptance filter: rejects proposals missing priority fields or naming an unknown `TaskRole`, dedupes near-identical questions by NFKC-normalized string match, and audits every rejection with the reason. Repair mode is driven by `mode: repair` in `task.yaml` (added to the invocation kit during Phase 3). Three unit tests plus one live mini-run pass; the live run produced a valid `TaskProposalBatch` in ≤2 attempts using `composer-2.5`.

## Open questions

- None.
