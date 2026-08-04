---
id: SPEC-040
title: Analysis of Competing Hypotheses stage
phase: 8
status: draft
depends_on: [SPEC-038]
parallel_with: []
north_star_refs: ["5.3", "6.3", "9", "10", "18"]
last_updated: 2026-08-04
---

# SPEC-040 — Analysis of Competing Hypotheses stage

## Summary

Adds a structured disconfirmation pass between the assumption ledger and the preliminary
recommendation. Each material evidence record is scored against every alternative, the orchestrator
computes each record's **diagnosticity** deterministically, and alternatives are ranked by weighted
disconfirming evidence rather than by supporting evidence. The Director then forms its
recommendation with the matrix in context and must address it.

## Motivation

The pipeline's adversarial machinery is good but all of it operates on a thesis that already exists:
the Challenger attacks a stated recommendation, the pre-mortem attacks its future, dual-track
compares two conclusions. None of them ask which alternative the evidence *fails to rule out*.
North star Section 5.3 asks for controlled disagreement and Section 18 makes adversarial robustness
a success criterion; ACH is the standard technique for exactly this, and its core insight — that
evidence consistent with every hypothesis carries no information, and the best hypothesis is the
least disconfirmed rather than the best supported — is the direct structural antidote to
confirmation bias.

Every prerequisite already exists: a broadened alternative set, an evidence ledger with
`independence_group`, materiality on assumptions, and the evidence critique's authority scores.

## Scope

- `orchestrator/artifacts/ach.py`:
  - `ACHConsistency` — `strongly_inconsistent`, `inconsistent`, `neutral`, `consistent`,
    `strongly_consistent`.
  - `ACHCell` — `evidence_id`, `alternative`, `consistency`, `note`.
  - `ACHMatrix` — `alternatives`, `evidence_ids`, `cells`, `excluded_evidence_ids` with reasons,
    plus validators for full coverage (one cell per evidence × alternative pair), no duplicate
    cells, and alternatives matching the decision spec.
- `cursor/roles/ach.{md,yaml}` and `TaskRole.ACH_ANALYST`.
- `CaseStage.COMPETING_HYPOTHESES`, placed between `ASSUMPTION_LEDGER` and
  `PRELIMINARY_RECOMMENDATION`, with the transition set and flow plan in
  `orchestrator/state_machine.py`.
- `orchestrator/stages.py::handle_competing_hypotheses`.
- `orchestrator/ach.py` — deterministic scoring: `diagnosticity`, `weighted_inconsistency`,
  `rank_by_disconfirmation`, `zero_diagnosticity_records`.
- `orchestrator/projection.py` — include key `ach_matrix`, wired into the director, director-b,
  challenger and synthesizer projections.
- `orchestrator/gates.py` — `ach.alternative_mismatch` and `ach.thin_matrix` checks.
- `orchestrator/render.py` — an ACH exhibit in the final report.
- `orchestrator/service/caseview.py` and the Options room — the matrix as an inspectable exhibit.
- `orchestrator/stub_backend.py` — `_make_ach_matrix` fixture.
- `orchestrator/service/lexicon_data.yaml` — narration entries.

## Out of scope

- Bayesian weighting of cells, or probability updating from the matrix. Diagnosticity is computed
  from score dispersion, not from likelihood ratios.
- Automatic re-ranking of the recommendation from the matrix. The matrix informs the Director; it
  does not override it, for the same reason SPEC-038's rank divergence is a finding rather than an
  override.
- Scoring low-materiality evidence. See the cap below.

## Design

**Matrix size is capped, deliberately.** Filling an N×M consistency matrix is a harder
structured-output task than anything currently asked of any role, and this repo's history shows
structured-output failures are where invocations die. The matrix therefore covers at most the 20
highest-authority evidence records among those the evidence critique scored `high` or `medium`,
against the decision spec's alternatives. Excluded records are listed in `excluded_evidence_ids`
with a reason, so the exclusion is auditable rather than invisible.

**Diagnosticity is deterministic.** For evidence record `e`, diagnosticity is the dispersion of its
consistency scores across alternatives, mapped to `[0, 1]`: a record scored identically against
every alternative has diagnosticity 0 and contributes nothing. Records with zero diagnosticity are
reported explicitly — that list is often the most useful output of the technique, because it names
the evidence the case collected that could never have changed the answer.

**Ranking.** `weighted_inconsistency(a) = Σ over e of diagnosticity(e) × inconsistency(e, a)`, where
inconsistency maps `strongly_inconsistent → 1.0` down to `strongly_consistent → 0.0`. Alternatives
rank ascending by that score — least disconfirmed first.

**Placement.** After the assumption ledger so the matrix can reference assumptions, and before the
preliminary recommendation so the Director confronts it rather than rationalizing around it. The
`ach_matrix` projection key reaches the Challenger too, which lets the Challenger attack the
scoring rather than only the conclusion.

**Cost.** One additional medium-tier invocation per case, with a large structured output. Expect
coercion activity; the retry-then-escalate ladder applies unchanged. Measure the failure rate in
SPEC-044 and reduce the cap if it is material.

## Deliverables

- [ ] `orchestrator/artifacts/ach.py` with validators
- [ ] `orchestrator/ach.py` deterministic scoring module
- [ ] `cursor/roles/ach.{md,yaml}`, `TaskRole.ACH_ANALYST`, model table entries
- [ ] `CaseStage.COMPETING_HYPOTHESES` and its stage handler
- [ ] `ach_matrix` projection key and role wiring
- [ ] Two gate checks
- [ ] Renderer exhibit and Options-room panel
- [ ] `orchestrator/stub_backend.py` fixture
- [ ] `tests/test_ach.py`
- [ ] Regenerated `schemas/` and `frontend/src/generated/`

## Acceptance criteria

- [ ] `make check` and `make frontend-check` are green.
- [ ] `ACHMatrix` rejects an incomplete matrix, a duplicate cell, and an alternative absent from the
      decision spec.
- [ ] A record scored identically across all alternatives has diagnosticity `0.0` and appears in
      `zero_diagnosticity_records`.
- [ ] `rank_by_disconfirmation` unit tests cover a clear winner, a tie, and a case where the
      least-disconfirmed alternative differs from the most-supported one.
- [ ] The matrix never exceeds 20 evidence records; a case with more produces a populated
      `excluded_evidence_ids` with reasons.
- [ ] A stub pipeline run reaches `done` with `COMPETING_HYPOTHESES` in the stage history and an
      `ach_matrix.yaml` on disk.
- [ ] `tests/test_role_contracts.py` passes for `ach.md`.
- [ ] `advisor report` renders the ACH exhibit including the zero-diagnosticity list.

## Verification plan

`make check`, `make frontend-check`, `uv run pytest tests/test_ach.py -v`, a full stub pipeline run,
and one live `--budget-profile small` case inspected for matrix completeness and coercion-report
activity on the `ach` role.

## Verification results

Not yet executed.

## Open questions

- Should the ACH stage run before or after the pre-mortem? Proposal: before the preliminary
  recommendation as specified, leaving the pre-mortem where it is, so the two adversarial passes
  stay separated by the thesis they attack.
