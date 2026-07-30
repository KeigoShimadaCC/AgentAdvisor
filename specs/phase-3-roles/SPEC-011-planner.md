---
id: SPEC-011
title: Planner role
phase: 3
status: draft
depends_on: [SPEC-006]
parallel_with: [SPEC-010, SPEC-012, SPEC-013, SPEC-014, SPEC-015, SPEC-016, SPEC-017]
north_star_refs: ["6.2", "8"]
last_updated: 2026-07-30
---

# SPEC-011 — Planner role

## Summary

The Planner proposes prioritized, dependency-aware investigation tasks; deterministic code (SPEC-009) decides execution. Also covers the Planner's repair-mode variant that commissions only objection-resolving work.

## Motivation

North star 6.2 and Stage 4: every task must state why it matters to the decision and carry the fields the priority formula needs; the Planner recommends, the orchestrator disposes.

## Scope

- `cursor/roles/planner.md`: mandate to decompose the decision into investigation areas and emit `TaskRecord` proposals, each with question, why_it_matters, expected_information_gain, materiality, estimated cost tier, required role, inputs, required_output, completion_criteria, dependencies; hard cap of 10 proposals per invocation; explicit instruction to propose nothing when open tasks already cover the material gaps (Section 5.1 tests).
- Repair mode: same role md, `task.yaml` flag `mode: repair` with the unresolved objections projected; proposals must reference the objection IDs they resolve; cap 4.
- `roles.yaml` entry (efficient model), projection config (decision spec, assumption gaps, open objections, existing task graph summary).
- Golden fixtures: post-framing planning and repair-mode planning; structural assertions.

## Out of scope

Dispatch, budget gating, cycle detection (SPEC-009), stop decision (SPEC-008).

## Design

Planner output is a `TaskProposalBatch` (new small wrapper model listing TaskRecords with proposed dependencies by index, resolved to `T-` IDs by the orchestrator on acceptance). Orchestrator-side acceptance filter (part of this spec, ~30 lines): reject proposals missing priority fields or referencing unknown roles, dedupe near-identical questions by normalized string match; rejections audited.

## Deliverables

- [ ] `cursor/roles/planner.md`
- [ ] `TaskProposalBatch` model + schema export
- [ ] Acceptance filter in `orchestrator/planning.py`
- [ ] `roles.yaml` entry, projection config
- [ ] `tests/test_role_planner.py` + fixtures; live mini-run test

## Acceptance criteria

- [ ] Fixture replay: all proposals schema-valid, ≤10, every task names role + completion criteria + priority fields.
- [ ] Repair fixture: every proposal references ≥1 open objection ID; ≤4 proposals.
- [ ] Acceptance filter rejects a fixture batch containing an unknown role and a near-duplicate, keeping the rest.
- [ ] Live mini-run on the investment fixture yields a valid batch in ≤2 attempts.
- [ ] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_role_planner.py -q
uv run pytest -m live -k planner -q
```

## Verification results

—

## Open questions

- None.
