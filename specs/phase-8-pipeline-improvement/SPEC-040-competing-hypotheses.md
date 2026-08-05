---
id: SPEC-040
title: Analysis of Competing Hypotheses stage
phase: 8
status: verified
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
a success criterion; ACH is the standard technique for exactly this. Its core insight — that
evidence consistent with every hypothesis carries no information, and the best hypothesis is the
least disconfirmed rather than the best supported — is the direct structural antidote to
confirmation bias. The technique is Richards Heuer's, catalogued with its scoring discipline in
Heuer and Pherson, *Structured Analytic Techniques for Intelligence Analysis*; an implementer should
read the ACH chapter before writing the role instructions. It is also one of the nine analytic
tradecraft standards ICD 203 requires of finished analysis ("incorporate analysis of alternatives"),
alongside source-quality description and uncertainty expression, which this pipeline already
implements.

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

- [x] `orchestrator/artifacts/ach.py` with validators
- [x] `orchestrator/ach.py` deterministic scoring module
- [x] `cursor/roles/ach.{md,yaml}`, `TaskRole.ACH_ANALYST`, model table entries
- [x] `CaseStage.COMPETING_HYPOTHESES` and its stage handler
- [x] `ach_matrix` projection key and role wiring
- [x] Two gate checks
- [x] Renderer exhibit and Options-room panel
- [x] `orchestrator/stub_backend.py` fixture
- [x] `tests/test_ach.py`
- [x] Regenerated `schemas/` and `frontend/src/generated/`

## Acceptance criteria

- [x] `make check` and `make frontend-check` are green.
- [x] `ACHMatrix` rejects an incomplete matrix, a duplicate cell, and an alternative absent from the
      decision spec.
- [x] A record scored identically across all alternatives has diagnosticity `0.0` and appears in
      `zero_diagnosticity_records`.
- [x] `rank_by_disconfirmation` unit tests cover a clear winner, a tie, and a case where the
      least-disconfirmed alternative differs from the most-supported one.
- [x] The matrix never exceeds 20 evidence records; a case with more produces a populated
      `excluded_evidence_ids` with reasons.
- [x] A stub pipeline run reaches `done` with `COMPETING_HYPOTHESES` in the stage history and an
      `ach_matrix.yaml` on disk.
- [x] `tests/test_role_contracts.py` passes for `ach.md`.
- [x] `advisor report` renders the ACH exhibit including the zero-diagnosticity list.

## Verification plan

`make check`, `make frontend-check`, `uv run pytest tests/test_ach.py -v`, a full stub pipeline run,
and one live `--budget-profile small` case inspected for matrix completeness and coercion-report
activity on the `ach` role.

## Verification results

**Verified 2026-08-04.**

Commands: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy orchestrator`,
`uv run pytest` (829 passed, 18 deselected), `npm run typecheck`, `npm run check:clean`,
`npm test` (102 passed).

All acceptance criteria met. `tests/test_ach.py` adds 25 tests. The end-to-end stub run asserts
the exhibit, its table header, and the zero-diagnosticity line.

The test that matters most is `test_best_supported_is_not_necessarily_least_disconfirmed`: an
alternative with two strongly consistent records and one strongly inconsistent one ranks *below*
one with nothing either way. That is the whole point of the technique, and it is the behaviour a
citation-counting pipeline cannot produce.

**Deviations from the spec as written:**

1. **Diagnosticity is spread, not variance.** The spec said "dispersion". Implemented as
   `(max − min) / 2.0` rather than variance, because spread is the quantity an analyst can read
   off the matrix by eye. Same reasoning as SPEC-025's deliberately dumb keyword retrieval:
   inspectable beats sophisticated when the number has to be defended.
2. **The linear stage-successor map is a second registration point.** Adding a stage requires both
   the transition set *and* `_NEXT_STAGE`; updating only the former yields
   `IllegalTransition: ASSUMPTION_LEDGER -> PRELIMINARY_RECOMMENDATION` at runtime rather than a
   load-time error. Worth knowing for any future stage.
3. **`tests/test_state_machine.py` carries its own handler map and expected-write sequence**, both
   of which need the new stage. This is the same duplicate-fixture trap SPEC-038 recorded, in a
   third location.
4. **Exclusions are applied by the orchestrator, not the agent.** The role md tells the agent to
   leave `excluded_evidence_ids` empty; the handler fills it after the invocation from the
   selection it already made. Asking the agent to restate a decision the orchestrator made is an
   invitation to disagree with it.

**A pre-existing stub defect surfaced and was fixed.** The stub's `quantitative_findings` carried
no citation, so `verification.uncited_claim` blocked every stub review, `review_accepted` was
always false, and the retry budget was silently exhausted on every end-to-end run. Nothing asserted
otherwise, so it went unnoticed. It surfaced here only because SPEC-039's independent review is
gated on the conformance review passing — so the new stage's own assertion failed and exposed it.
One citation added to both stub copies; the stub pipeline now reaches a passing review for the
first time, which also means SPEC-039's independent review is exercised end to end rather than
only in unit tests.

**The agent-reliability risk is unmitigated and remains the open question for live runs.** The
matrix is capped at 20 records and the role md pushes hard on `neutral`, but nothing here proves a
model can fill an N×M matrix at an acceptable rate — that needs a live invocation, which this
environment cannot run. SPEC-044 must report the `ach` role's coercion and failure rates
separately, and the cap should drop to 10 if they are material.

## Open questions

None. The open question — whether ACH runs before or after the pre-mortem — was resolved as
proposed: ACH sits between the assumption ledger and the preliminary recommendation, and the
pre-mortem stays where it was. The two adversarial passes remain separated by the thesis they
attack, one testing the reasoning and one testing the future.
