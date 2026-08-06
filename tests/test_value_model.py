"""SPEC-038 — the deterministic value model and its gate check."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from orchestrator.artifacts import (
    AlternativeAssessment,
    ConfidenceAssessment,
    DecisionSpec,
    Depth,
    FinalRecommendation,
    ModelStability,
    NextAction,
    ProbabilityEstimate,
    ProbabilityMethod,
    Reversibility,
    RiskTolerance,
)
from orchestrator.case_store import create_case
from orchestrator.gates import run_stage_gate
from orchestrator.value_model import (
    compute_ranking,
    normalize_weights,
    rank_divergence,
    weight_sensitivity,
    weighted_score,
)

RETURN = "expected_return"
SAFETY = "downside_protection"
LIQUIDITY = "liquidity"


def _alt(name: str, rank: int, scores: dict[str, float] | None) -> AlternativeAssessment:
    return AlternativeAssessment(
        alternative=name,
        rank=rank,
        rationale=f"Rationale for {name}.",
        objective_scores=scores,
    )


def _spec(weights: dict[str, float] | None, **overrides: Any) -> DecisionSpec:
    payload: dict[str, Any] = {
        "decision_id": "case-001-value",
        "question": "Should I proceed?",
        "owner": "user",
        "deadline": date(2026, 12, 31),
        "alternatives": ["a", "b"],
        "objectives": [RETURN, SAFETY, LIQUIDITY],
        "risk_tolerance": RiskTolerance.MODERATE,
        "reversibility": Reversibility.PARTIALLY_REVERSIBLE,
        "depth": Depth.STANDARD,
        "objective_weights": weights,
    }
    payload.update(overrides)
    return DecisionSpec(**payload)


def _final(assessments: list[AlternativeAssessment]) -> FinalRecommendation:
    return FinalRecommendation(
        recommended_action="Proceed.",
        timing="Now.",
        decision_confidence_summary="Moderate.",
        alternatives_considered=assessments,
        key_reasons=["Weighted value is highest [E-001]."],
        scenario_analysis=[
            {
                "scenario_name": "base",
                "summary": "Base case.",
                "probability": ProbabilityEstimate(
                    method=ProbabilityMethod.SCENARIO_MODEL, point=0.6, adjustments=[]
                ),
            }
        ],
        next_actions=[
            NextAction(
                action_id="N-001",
                action="Start",
                owner="user",
                by_date=date(2026, 8, 15),
                first_step="Open the checklist",
                why_now="It is the first step",
            )
        ],
        outcome_probabilities={
            "success": ProbabilityEstimate(
                method=ProbabilityMethod.SCENARIO_MODEL, point=0.6, adjustments=[]
            )
        },
        evidence_confidence=ConfidenceAssessment(value=0.6, basis="Mixed"),
        recommendation_confidence=ConfidenceAssessment(value=0.65, basis="Balanced"),
        model_stability=ModelStability(
            share_of_sensitivity_runs_supporting_recommendation=0.7,
            runs_total=10,
            runs_supporting=7,
        ),
    )


# ── schema validation ────────────────────────────────────────────────────────


def test_weights_may_be_omitted_entirely() -> None:
    assert _spec(None).objective_weights is None


def test_empty_weight_mapping_is_rejected() -> None:
    with pytest.raises(ValidationError, match="omitted entirely"):
        _spec({})


def test_weights_naming_an_unknown_objective_are_rejected() -> None:
    with pytest.raises(ValidationError, match="not in the spec"):
        _spec({RETURN: 50.0, "not_an_objective": 50.0})


def test_non_positive_weight_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must be positive"):
        _spec({RETURN: 50.0, SAFETY: 0.0})


def test_objective_score_out_of_range_is_rejected() -> None:
    with pytest.raises(ValidationError, match=r"\[0, 1\]"):
        _alt("a", 1, {RETURN: 1.5})


def test_empty_objective_scores_mapping_is_rejected() -> None:
    with pytest.raises(ValidationError, match="omitted entirely"):
        _alt("a", 1, {})


# ── normalize_weights ────────────────────────────────────────────────────────


def test_normalize_weights_scales_to_one() -> None:
    normalized = normalize_weights({RETURN: 30.0, SAFETY: 70.0})
    assert normalized[RETURN] == pytest.approx(0.3)
    assert normalized[SAFETY] == pytest.approx(0.7)
    assert sum(normalized.values()) == pytest.approx(1.0)


def test_normalize_weights_handles_unnormalized_input() -> None:
    normalized = normalize_weights({RETURN: 3.0, SAFETY: 3.0, LIQUIDITY: 6.0})
    assert normalized[LIQUIDITY] == pytest.approx(0.5)


def test_normalize_weights_rejects_empty_mapping() -> None:
    with pytest.raises(ValueError, match="empty weight mapping"):
        normalize_weights({})


# ── weighted_score ───────────────────────────────────────────────────────────


def test_weighted_score_is_the_weighted_sum() -> None:
    score, missing = weighted_score({RETURN: 40.0, SAFETY: 60.0}, {RETURN: 1.0, SAFETY: 0.5})
    assert score == pytest.approx(0.7)
    assert missing == ()


def test_weighted_score_renormalizes_over_scored_objectives_only() -> None:
    """A partially scored alternative is not penalized for the gap; the gap is
    reported instead."""
    score, missing = weighted_score({RETURN: 40.0, SAFETY: 60.0}, {RETURN: 0.8})
    assert score == pytest.approx(0.8)
    assert missing == (SAFETY,)


# ── compute_ranking ──────────────────────────────────────────────────────────


def test_compute_ranking_orders_by_weighted_score() -> None:
    ranked = compute_ranking(
        {RETURN: 40.0, SAFETY: 60.0},
        [
            _alt("aggressive", 1, {RETURN: 0.9, SAFETY: 0.2}),
            _alt("balanced", 2, {RETURN: 0.6, SAFETY: 0.8}),
        ],
    )
    assert [row.alternative for row in ranked] == ["balanced", "aggressive"]
    assert ranked[0].computed_rank == 1
    assert ranked[0].stated_rank == 2


def test_compute_ranking_breaks_ties_on_the_stated_order() -> None:
    ranked = compute_ranking(
        {RETURN: 50.0, SAFETY: 50.0},
        [
            _alt("second", 2, {RETURN: 0.5, SAFETY: 0.5}),
            _alt("first", 1, {RETURN: 0.5, SAFETY: 0.5}),
        ],
    )
    assert [row.alternative for row in ranked] == ["first", "second"]


def test_compute_ranking_excludes_unscored_alternatives(
    # Resolves the spec's open question: excluded, not scored as zero, so a
    # missing score reads as an omission rather than a worthless option.
) -> None:
    ranked = compute_ranking(
        {RETURN: 50.0, SAFETY: 50.0},
        [_alt("scored", 1, {RETURN: 0.5, SAFETY: 0.5}), _alt("unscored", 2, None)],
    )
    assert [row.alternative for row in ranked] == ["scored"]


def test_compute_ranking_reports_a_missing_objective() -> None:
    ranked = compute_ranking(
        {RETURN: 50.0, SAFETY: 50.0},
        [_alt("partial", 1, {RETURN: 0.5})],
    )
    assert ranked[0].missing_objectives == (SAFETY,)


def test_compute_ranking_is_empty_when_nothing_is_scored() -> None:
    assert compute_ranking({RETURN: 100.0}, [_alt("a", 1, None)]) == []


# ── rank_divergence ──────────────────────────────────────────────────────────


def test_rank_divergence_agrees_when_orders_match() -> None:
    divergence = rank_divergence(
        {RETURN: 40.0, SAFETY: 60.0},
        [
            _alt("balanced", 1, {RETURN: 0.6, SAFETY: 0.8}),
            _alt("aggressive", 2, {RETURN: 0.9, SAFETY: 0.2}),
        ],
    )
    assert divergence.agrees
    assert divergence.positions == ()


def test_rank_divergence_reports_a_swap() -> None:
    divergence = rank_divergence(
        {RETURN: 40.0, SAFETY: 60.0},
        [
            _alt("aggressive", 1, {RETURN: 0.9, SAFETY: 0.2}),
            _alt("balanced", 2, {RETURN: 0.6, SAFETY: 0.8}),
        ],
    )
    assert not divergence.agrees
    assert divergence.top_choice_differs
    assert {name for name, _, _ in divergence.positions} == {"aggressive", "balanced"}


def test_rank_divergence_compares_order_not_literal_rank_values() -> None:
    """Ranks of 2/4/6 are the same order as 1/2/3 and must not read as a
    disagreement."""
    divergence = rank_divergence(
        {RETURN: 50.0, SAFETY: 50.0},
        [
            _alt("best", 2, {RETURN: 0.9, SAFETY: 0.9}),
            _alt("middle", 4, {RETURN: 0.6, SAFETY: 0.6}),
            _alt("worst", 6, {RETURN: 0.1, SAFETY: 0.1}),
        ],
    )
    assert divergence.agrees


def test_rank_divergence_lists_unscored_alternatives() -> None:
    divergence = rank_divergence(
        {RETURN: 100.0},
        [_alt("scored", 1, {RETURN: 0.5}), _alt("skipped", 2, None)],
    )
    assert divergence.unscored == ("skipped",)


# ── weight_sensitivity ───────────────────────────────────────────────────────


def test_weight_sensitivity_reports_a_stable_top_choice() -> None:
    sensitivity = weight_sensitivity(
        {RETURN: 40.0, SAFETY: 60.0},
        [
            _alt("dominant", 1, {RETURN: 0.95, SAFETY: 0.95}),
            _alt("weak", 2, {RETURN: 0.1, SAFETY: 0.1}),
        ],
    )
    assert sensitivity is not None
    assert sensitivity.share_preserving_top == 1.0
    assert sensitivity.smallest_flip is None


def test_weight_sensitivity_finds_the_weight_that_flips_the_choice() -> None:
    sensitivity = weight_sensitivity(
        {RETURN: 50.0, SAFETY: 50.0},
        [
            _alt("balanced", 1, {RETURN: 0.50, SAFETY: 0.56}),
            _alt("aggressive", 2, {RETURN: 0.60, SAFETY: 0.44}),
        ],
    )
    assert sensitivity is not None
    assert sensitivity.share_preserving_top < 1.0
    assert sensitivity.smallest_flip is not None
    assert sensitivity.flipped_by


def test_weight_sensitivity_returns_none_for_a_single_objective() -> None:
    """Scaling the only weight cannot change the order, so there is nothing to
    report."""
    assert weight_sensitivity({RETURN: 100.0}, [_alt("a", 1, {RETURN: 0.5})]) is None


def test_weight_sensitivity_rejects_an_out_of_range_perturbation() -> None:
    with pytest.raises(ValueError, match="perturbation"):
        weight_sensitivity(
            {RETURN: 50.0, SAFETY: 50.0},
            [_alt("a", 1, {RETURN: 0.5, SAFETY: 0.5})],
            perturbation=1.5,
        )


# ── gate check ───────────────────────────────────────────────────────────────


def _case(tmp_path: Path, weights: dict[str, float] | None, alts: list[AlternativeAssessment]):
    case = create_case("value", cases_root=tmp_path)
    case.write_artifact(_spec(weights))
    case.write_artifact(_final(alts))
    return case


def test_agreeing_ranking_produces_no_divergence_finding(tmp_path: Path) -> None:
    case = _case(
        tmp_path,
        {RETURN: 40.0, SAFETY: 60.0},
        [
            _alt("balanced", 1, {RETURN: 0.6, SAFETY: 0.8}),
            _alt("aggressive", 2, {RETURN: 0.9, SAFETY: 0.2}),
        ],
    )
    report = run_stage_gate(case, "synthesis", as_of=date(2026, 8, 1))
    assert not [f for f in report.findings if f.check_id == "value_model.rank_divergence"]


def test_mis_ranked_recommendation_produces_exactly_one_divergence_finding(
    tmp_path: Path,
) -> None:
    case = _case(
        tmp_path,
        {RETURN: 40.0, SAFETY: 60.0},
        [
            _alt("aggressive", 1, {RETURN: 0.9, SAFETY: 0.2}),
            _alt("balanced", 2, {RETURN: 0.6, SAFETY: 0.8}),
        ],
    )
    report = run_stage_gate(case, "synthesis", as_of=date(2026, 8, 1))
    findings = [f for f in report.findings if f.check_id == "value_model.rank_divergence"]
    assert len(findings) == 1
    assert set(findings[0].target_ids) == {"aggressive", "balanced"}


def test_unscored_alternative_produces_its_own_finding(tmp_path: Path) -> None:
    case = _case(
        tmp_path,
        {RETURN: 100.0},
        [_alt("scored", 1, {RETURN: 0.5}), _alt("skipped", 2, None)],
    )
    report = run_stage_gate(case, "synthesis", as_of=date(2026, 8, 1))
    findings = [f for f in report.findings if f.check_id == "value_model.unscored_alternative"]
    assert len(findings) == 1
    assert findings[0].target_ids == ["skipped"]


def test_case_without_weights_produces_no_value_model_findings(tmp_path: Path) -> None:
    """A case predating the value model must behave exactly as it did before."""
    case = _case(tmp_path, None, [_alt("a", 1, None), _alt("b", 2, None)])
    report = run_stage_gate(case, "synthesis", as_of=date(2026, 8, 1))
    assert not [f for f in report.findings if f.check_id.startswith("value_model.")]
