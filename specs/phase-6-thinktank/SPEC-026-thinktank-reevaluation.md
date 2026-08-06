---
id: SPEC-026
title: Think-tank architecture re-evaluation (before/after benchmark comparison)
phase: 6
status: verified
depends_on: [SPEC-023, SPEC-024, SPEC-025]
parallel_with: []
north_star_refs: ["19"]
last_updated: 2026-08-06
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

**Verified 2026-08-03.** All five scenarios completed. Comparison report written at
`report-and-findings/2026-08-03-phase-6-before-after.md`.

**2026-08-06 sweep amendment.** The scope's first bullet — "Extend `benchmarks/rubric.yaml`
*and* `scripts/run_e2e_eval.py`" — was only half delivered: the scorer collected the Phase 6
metrics (`_phase6_metrics`) but the rubric held no Phase 6 criteria, despite the report's
caveat section claiming "the rubric was extended for Phase 6". Found in the 2026-08-06 spec
sweep; fixed by adding the six Phase 6 dimensions (assumption ledger coverage, evidence
authority, issue-tree coverage, pre-mortem quality, verification depth, thesis evolution;
`phase: 6`, twelve criteria) to `benchmarks/rubric.yaml` and a matching `_score_phase6` to
`scripts/run_e2e_eval.py`, wired exactly like SPEC-044's Phase 8 extension: legacy average
untouched, new dimensions reported alongside. Bands are asserted in
`tests/test_eval_rubric.py` (35 tests pass). The 2026-08-03 report's numbers are unaffected —
they were computed with the legacy scorer, which is unchanged.

Summary: average score improved 1.89 to 1.96. Evidence quality improved 1.53 to 1.80.
Assumption records went from 0 to 7.8 per case. Invocation success rate went from 52% to 92%.
Token cost dropped 40% despite adding 4 roles and 4 stages. Four defects were found and fixed
during the sweep (budget persistence, optional-list coercion, role contract errors, YAML
quoting). Scenarios 01 and 03 were re-run twice for repeatability; both showed stable scores.
Scenario 02 evidence quality (1.33) is flat and is the next improvement target.

## Open questions

None.
