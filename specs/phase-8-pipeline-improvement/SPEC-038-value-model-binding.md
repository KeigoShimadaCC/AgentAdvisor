---
id: SPEC-038
title: Objective weights and a bound value model
phase: 8
status: draft
depends_on: []
parallel_with: [SPEC-043]
north_star_refs: ["5.5", "7", "8", "15", "16"]
last_updated: 2026-08-04
---

# SPEC-038 — Objective weights and a bound value model

## Summary

Makes the user's objectives quantitatively bind to the alternative ranking. Today `objectives` is
collected into `DecisionSpec` as a list of strings and never used again: `AlternativeAssessment`
carries `{alternative, rank, rationale}`, so the ranking rests on prose judgment alone. This spec
adds optional objective weights elicited at the scope checkpoint, per-objective scores on each
alternative, a deterministic ranking computed by the orchestrator, and a gate finding when the
computed rank disagrees with the rank the agent stated.

## Motivation

North star Section 8 specifies `EU(a) = Σ P(s | E) × U(a, s)` with an explicit division of labor:
language models supply scenarios, assumptions and value judgments; deterministic code computes
expected values, thresholds and sensitivities. The `U(a, s)` half has no implementation. This is
the widest gap between the north star text and the code, and it breaks the chain the README
advertises — objectives currently do not reach the recommendation by any mechanical path.

It also fixes a blind spot in sensitivity analysis: the analyst varies model parameters, but nothing
varies the user's own weights, which is usually what actually flips a personal decision.

## Scope

- `orchestrator/artifacts/decision.py`: `DecisionSpec.objective_weights: dict[NonEmptyStr, float] | None`,
  defaulting to `None`. Validator: keys must be a subset of `objectives`; values must be positive.
- `orchestrator/artifacts/recommendations.py`: `AlternativeAssessment.objective_scores:
  dict[NonEmptyStr, float] | None`, defaulting to `None`. Validator: values in `[0.0, 1.0]`.
- New `orchestrator/value_model.py`: pure functions `normalize_weights`, `weighted_score`,
  `compute_ranking`, `rank_divergence`, and `weight_sensitivity`.
- `orchestrator/gates.py`: new deterministic check `value_model.rank_divergence`, run at the
  synthesis gate.
- `cursor/roles/director-framing.md`: propose an initial weight allocation over the objectives it
  frames, marked as a proposal for the user to correct.
- `cursor/roles/synthesizer.md`: emit `objective_scores` for every alternative, with a worked
  example that validates against the schema (`tests/test_role_contracts.py` enforces this).
- `orchestrator/service/caseview.py`: `OptionView` carries the per-objective scores and the
  computed weighted total.
- `frontend/src/screens/ScopeCheckpoint/`: a 100-point allocation control over the objectives
  already rendered on that sheet, posting through the existing SPEC-028 `edits` path.
- `orchestrator/projection.py`: include `objective_weights` in the director, analyst and
  synthesizer projections.
- `orchestrator/service/lexicon_data.yaml`: narration for `objective_weights_recorded` and
  `value_model_ranked`, so neither renders through the unknown-event fallback.

## Out of scope

- Formal preference elicitation methods (swing weighting, AHP, MACBETH). A 100-point allocation is
  the v1 instrument.
- Multi-stakeholder or conflicting weight sets.
- Changing the semantics of `ModelStability`. Weight sensitivity is reported as its own figure and
  is not folded into the existing stability measure.
- Making weights mandatory. A case without them must behave exactly as it does today.

## Design

**Additive by construction.** Both new fields are optional with a `None` default, so all 35 artifact
fixtures, every committed case, and the stub pipeline keep validating unchanged. Cases that carry no
weights skip the gate check entirely.

**Elicitation.** The framing director proposes weights; the scope checkpoint presents them as a
100-point allocation the user can redistribute. Because the sheet already renders objectives, this
is a control on an existing screen rather than a new screen. Submitting a redistribution routes
through `request_framing_revision`, so the change is auditable rather than silent.

**Computation.** `compute_ranking` normalizes weights to sum to 1.0, computes
`Σ weight(o) × score(a, o)` per alternative, and returns alternatives ordered by descending total.
`rank_divergence` compares that order against the `rank` field the synthesizer wrote and returns the
positions that disagree.

**Enforcement is a finding, not an override.** When the computed and stated rankings disagree, the
gate emits `value_model.rank_divergence` and the synthesizer must either revise its scores or state
in `key_reasons` why the weighted model does not capture the decision. Deterministic code does not
silently reorder the recommendation — a mismatch is usually a signal that the value model is wrong,
not that the judgment is.

**Weight sensitivity.** `weight_sensitivity` perturbs each weight by ±25% in isolation, recomputes
the ranking, and reports the share of perturbations that preserve the top-ranked alternative,
together with the smallest single weight change that flips it. This is written to the case and
rendered in the final report.

**Coercion warning.** `dict[str, float]` is the field shape that produced the `_base_type` bug where
`dict[str, int]` was misidentified as `str`. Verify the parametrized coercion tests actually reach
both new fields rather than assuming coverage.

## Deliverables

- [ ] `orchestrator/value_model.py` — ranking, divergence and weight-sensitivity functions
- [ ] `DecisionSpec.objective_weights` and `AlternativeAssessment.objective_scores`
- [ ] `orchestrator/gates.py` — `value_model.rank_divergence` check
- [ ] `cursor/roles/director-framing.md`, `cursor/roles/synthesizer.md` — contracts and worked examples
- [ ] `frontend/src/screens/ScopeCheckpoint/` — weight allocation control
- [ ] `orchestrator/render.py` — weighted ranking table and weight-sensitivity line
- [ ] `tests/test_value_model.py` — unit tests for all five functions
- [ ] Regenerated `schemas/` and `frontend/src/generated/`

## Acceptance criteria

- [ ] `make check` and `make frontend-check` are green.
- [ ] A case with no weights produces byte-identical artifacts to the pre-change pipeline
      (verified against a committed fixture case).
- [ ] `compute_ranking` unit tests cover: unnormalized weights, a tie, a missing score, and an
      objective present in weights but absent from scores.
- [ ] The stub pipeline run produces a `FinalRecommendation` whose stated ranks match the computed
      ranks, and the gate emits no `value_model.rank_divergence` finding.
- [ ] A deliberately mis-ranked fixture triggers exactly one `value_model.rank_divergence` finding.
- [ ] The coercion property tests include `objective_weights` and `objective_scores`; a test
      asserts a `dict[str, float]` field is reached by the coercion layer.
- [ ] The scope checkpoint allocates 100 points across objectives, rejects a total ≠ 100, and the
      submitted weights appear in `decision_spec.yaml`.
- [ ] `advisor report` renders the weighted ranking table and the weight-sensitivity figure.

## Verification plan

`make check`, `make frontend-check`, `uv run pytest tests/test_value_model.py -v`, a stub pipeline
run to `done`, a fixture-case diff to confirm no-weights behavior is unchanged, and one live
`--budget-profile small` case carried through the scope checkpoint in the browser with weights set.

## Verification results

Not yet executed.

## Open questions

- Should an alternative with no `objective_scores` be excluded from the computed ranking or scored
  as zero? Proposal: excluded, with a gate finding naming it, so a missing score is visible rather
  than silently penalizing the alternative.
