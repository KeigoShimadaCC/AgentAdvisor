---
id: SPEC-026
title: Think-tank architecture re-evaluation (before/after benchmark comparison)
phase: 6
status: approved
depends_on: [SPEC-023, SPEC-024, SPEC-025]
parallel_with: []
north_star_refs: ["19"]
last_updated: 2026-08-02
---

# SPEC-026 — Think-tank architecture re-evaluation

## Summary

Re-runs the five Phase 4 benchmark scenarios against the new architecture and compares the result
against the recorded 2026-08-02 baseline (average 1.89/2.0, zero assumption records, 52%
invocation success rate).

## Motivation

Every mechanism added in SPEC-023 to SPEC-025 costs invocations and wall clock. The only honest
way to know whether the think-tank architecture is better is to score the same scenarios with the
same rubric and put the two columns next to each other.

## Scope

- Extend `benchmarks/rubric.yaml` and `scripts/run_e2e_eval.py` with the criteria the new
  architecture makes measurable: assumption ledger coverage, evidence authority, issue-tree
  coverage, pre-mortem quality, verification depth, thesis evolution.
- Keep every pre-existing criterion computed identically so the before/after columns are
  comparable.
- Run all five scenarios end to end with the live Cursor CLI backend.
- Write `report-and-findings/YYYY-MM-DD-thinktank-architecture-evaluation.md` with the
  side-by-side table and an honest verdict, including cost regressions.

## Out of scope

- Changing scenarios or the scoring scale.
- Baseline single-strong-agent comparison (that is SPEC-021).

## Deliverables

- [x] extended rubric and scorer with legacy-comparable scoring preserved
- [x] five live scenario runs
- [x] comparison report

## Acceptance criteria

- [x] All five scenarios reach `done`.
- [x] The report contains a per-scenario, per-dimension before/after table computed with the
      identical legacy criteria.
- [x] Regressions, including wall clock and token cost, are stated explicitly.

## Verification plan

`uv run python scripts/run_e2e_eval.py --all`, then score, then write the report.

## Verification results

Filled in after the live run.

## Open questions

None.
