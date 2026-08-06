---
id: SPEC-044
title: Phase 8 re-evaluation (before/after benchmark comparison)
phase: 8
status: implemented
depends_on: [SPEC-038, SPEC-039, SPEC-040, SPEC-041, SPEC-042, SPEC-043]
parallel_with: []
north_star_refs: ["18", "19"]
last_updated: 2026-08-04
---

# SPEC-044 — Phase 8 re-evaluation

## Summary

Re-runs the five benchmark scenarios against the Phase 8 pipeline and compares them against the
recorded 2026-08-03 Phase 6 baseline (average 1.96/2.0, evidence quality 1.80, 7.8 assumptions per
case, 92% invocation success, 7.1M input tokens, 202 minutes). Follows the SPEC-026 pattern: every
pre-existing criterion is computed identically so the columns are comparable, and cost regressions
are stated explicitly.

## Motivation

Phase 8 adds three agent invocations per case (`reviewer-b`, `ach`, `monitor`), one new stage, and
several deterministic checks. Each of them costs invocations and wall clock. The only honest way to
know whether the pipeline improved is to score the same scenarios with the same rubric and put the
columns side by side — including the possibility that the answer is no.

North star Section 19 requires benchmark cases run through the workflow and its variations;
Section 18 defines the dimensions.

## Scope

- Extend `benchmarks/rubric.yaml` and `scripts/run_e2e_eval.py` with the criteria Phase 8 makes
  measurable:
  - **value-model coherence** — weights present, scores complete, computed rank agrees with stated rank
  - **independent-review outcome** — verdict distribution, and whether any dissent changed the output
  - **ACH quality** — matrix completeness, diagnosticity spread, count of zero-diagnosticity records
  - **action-plan executability** — share of actions with owner, date and a same-day first step
  - **monitoring coverage** — share of pre-mortem indicators and change triggers that became
    tracked indicators with thresholds
  - **private-evidence usage** — for the scenarios where `inputs/` is seeded, whether private figures
    reach the analysis
- Keep every pre-existing criterion computed identically to SPEC-026.
- Seed `inputs/` for at least two scenarios with synthetic private documents, so SPEC-043 is
  exercised rather than assumed.
- Run all five scenarios end to end on the Droid backend, matching the Phase 6 comparison conditions.
- Record per-role coercion activity and invocation success rate, with attention to the `ach` role,
  whose N×M structured output is the largest new failure surface.
- Write `report-and-findings/YYYY-MM-DD-phase-8-before-after.md` with the side-by-side table and an
  honest verdict.

## Out of scope

- Changing the scenarios or the scoring scale.
- The single-strong-agent baseline comparison (SPEC-021/022 territory).
- Tuning models or budgets mid-sweep. Defects found during the sweep are fixed and the affected
  scenario is re-run, as in SPEC-026; parameter tuning to improve scores is not.

## Design

Same shape as SPEC-026. New rubric criteria are additive columns, so the legacy average stays
directly comparable to the 1.96 baseline and is reported alongside the extended average rather than
replacing it.

Cost is reported without softening. Phase 8 is expected to raise invocation count and token spend;
if decision quality does not move enough to justify that, the report must say so and name which
mechanism to cut. SPEC-023–025 achieved a 40% token *reduction* while adding four roles, so a
regression here is not inevitable and should not be excused.

The `high_tier_calls` budget cap (currently 6) may need raising to accommodate `reviewer-b`. Any
budget change is recorded in the report as a condition of the comparison, not treated as a neutral
detail.

## Deliverables

- [ ] Extended `benchmarks/rubric.yaml` with the six new criteria
- [ ] `scripts/run_e2e_eval.py` scoring for each, with legacy scoring preserved
- [ ] Synthetic private documents for at least two scenarios
- [ ] Five completed live scenario runs
- [ ] `report-and-findings/YYYY-MM-DD-phase-8-before-after.md`

## Acceptance criteria

- [ ] All five scenarios reach `done` within budget.
- [ ] The report contains a per-scenario, per-dimension before/after table computed with the
      identical legacy criteria, plus the extended criteria in separate columns.
- [ ] Token cost, wall clock, invocation count and invocation success rate are stated for both
      pipelines.
- [ ] Per-role coercion counts are reported, with the `ach` role called out separately.
- [ ] Any regression — quality, cost or reliability — is stated explicitly rather than omitted.
- [ ] At least two scenarios demonstrate private evidence reaching the analysis.
- [ ] The verdict names which Phase 8 mechanisms earned their cost and which did not.

## Verification plan

`uv run python scripts/run_e2e_eval.py --all` on the Droid backend, then scoring, then the report.
Re-run any scenario affected by a defect fixed mid-sweep before the comparison is treated as honest.

## Verification results

**Status: `implemented`, not `verified` — and it cannot become `verified` in this environment.**

The scoring machinery is built and tested. The five live scenario runs it exists to score are
not, and saying otherwise would be the exact dishonesty this spec is meant to prevent.

**What was completed.**

- `benchmarks/rubric.yaml` gains four Phase 8 dimensions and eight criteria: value-model binding
  (weight elicitation, ranking coherence), independent review (second opinion, limitations),
  disconfirmation (matrix completeness, diagnosticity signal), commitment to action (executability,
  monitoring coverage).
- `scripts/run_e2e_eval.py` gains `_phase8_metrics` — 25 counters mirroring the `_phase6_metrics`
  pattern — and `_score_phase8`, which derives the eight criteria objectively from those counters
  and from gate findings rather than from prose inspection.
- **Every legacy criterion is computed unchanged.** `overall_score` remains the legacy
  five-dimension average so it stays directly comparable to the recorded 1.96 baseline;
  `extended_overall_score` is reported alongside it, never in place of it. Two tests guard this:
  one asserts the legacy dimensions carry no `phase` key, another asserts the Phase 8 dimensions
  all do.
- `tests/test_eval_rubric.py` adds 18 tests over the rubric's shape and every scoring band.

**Verified against a real case, not just unit fixtures.** A full stub pipeline run scored:
legacy 1.30, extended 1.556, with value-model binding 2.0, independent review 2.0,
disconfirmation 1.5 and commitment to action 2.0. Diagnosticity scoring 1.5 rather than 2.0 is
correct — the stub's matrix deliberately contains one zero-diagnosticity record out of two, which
is exactly the mixed case the criterion is meant to discriminate.

**What remains, and why it could not be done here.**

The five live scenario runs require an authenticated Cursor or Droid CLI, several hours of wall
clock, and roughly seven million input tokens. None of that is available in this environment. The
following are outstanding:

- [ ] Five live scenario runs on the Droid backend, matching the Phase 6 comparison conditions.
- [ ] Synthetic private documents seeded for at least two scenarios, so SPEC-043 is exercised
      rather than assumed. The `advisor new --input` path makes this a one-line addition per
      scenario.
- [ ] `report-and-findings/YYYY-MM-DD-phase-8-before-after.md` with the side-by-side table.

**Three things the eventual run must report honestly, all of them known risks rather than
hypotheticals:**

1. **The `ach` role's failure rate, separately.** Its N×M matrix is the largest structured output
   any role produces and this repo's history says structured-output failures are where invocations
   die. `_phase8_metrics` emits `ach_role_failures` and `ach_skipped` for exactly this. **If it is
   material, cut `MAX_ACH_EVIDENCE` from 20 to 10 before drawing any conclusion about ACH's value** —
   a technique that cannot be executed reliably has not been tested.
2. **Invocation count against the cap.** Phase 8 adds three invocations per case (`reviewer-b`,
   `ach`, `monitor`) against a cap of 40; the first real case already used 45. Report counts
   against the cap rather than assuming headroom, and record any cap change as a condition of the
   comparison.
3. **`max_high_tier_calls` is vestigial** (found in SPEC-039, recorded in ROADMAP emergent work).
   No model any role resolves to maps to the high tier, so that cap cannot fire. Do not report it
   as a constraint that held.

## Open questions

- Should scenarios be re-run twice for repeatability, as scenarios 01 and 03 were in SPEC-026?
  Proposal stands: yes for the two scenarios whose scores move most, budget permitting. Deferred
  to whoever runs the live sweep, since it depends on observed variance.
