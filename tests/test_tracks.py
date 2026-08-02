from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator.artifacts import (
    ConfidenceAssessment,
    ModelStability,
    PreliminaryRecommendation,
    ProbabilityEstimate,
    ProbabilityMethod,
    TrackDivergence,
)
from orchestrator.tracks import build_position, compare_tracks


def _recommendation(alternative: str, *, rationale: list[str] | None = None):
    return PreliminaryRecommendation(
        preferred_alternative=alternative,
        rationale=rationale if rationale is not None else ["Primary reason"],
        key_assumptions=[],
        outcome_probabilities={
            "positive_return_12m": ProbabilityEstimate(
                method=ProbabilityMethod.SCENARIO_MODEL, point=0.5
            )
        },
        evidence_confidence=ConfidenceAssessment(value=0.5, basis="Mixed"),
        recommendation_confidence=ConfidenceAssessment(value=0.62, basis="Balanced"),
        model_stability=ModelStability(
            share_of_sensitivity_runs_supporting_recommendation=1.0,
            runs_total=2,
            runs_supporting=2,
        ),
        unresolved_evidence_gaps=[],
        major_risks=["drawdown"],
    )


def _positions(left: str, right: str):
    return [
        build_position(
            track_id="track-a",
            model="cursor-grok-4.5-low",
            recommendation=_recommendation(left),
        ),
        build_position(
            track_id="track-b", model="composer-2.5", recommendation=_recommendation(right)
        ),
    ]


def test_position_records_the_canonical_model_family() -> None:
    position = build_position(
        track_id="track-a",
        model="cursor-grok-4.5-low",
        recommendation=_recommendation("staged_entry"),
    )
    assert position.model_family == "xai"
    assert position.recommendation_confidence == pytest.approx(0.62)


def test_agreement_is_reported_as_a_weak_signal_not_evidence() -> None:
    divergence = compare_tracks(
        stage="preliminary_recommendation", positions=_positions("staged_entry", "staged_entry")
    )

    assert divergence.agreement is True
    assert "weak positive signal" in divergence.divergence_summary
    assert divergence.reconciled_alternative is None


def test_disagreement_is_reported_not_averaged() -> None:
    divergence = compare_tracks(
        stage="preliminary_recommendation",
        positions=_positions("staged_entry", "etf_diversified"),
    )

    assert divergence.agreement is False
    assert "not averaged" in divergence.divergence_summary
    assert "staged_entry" in divergence.divergence_summary
    assert "etf_diversified" in divergence.divergence_summary


def test_cosmetic_naming_differences_still_count_as_agreement() -> None:
    divergence = compare_tracks(
        stage="preliminary_recommendation",
        positions=_positions("Staged Entry", "staged_entry"),
    )
    assert divergence.agreement is True


def test_position_carries_the_leading_rationale_item() -> None:
    position = build_position(
        track_id="track-b",
        model="composer-2.5",
        recommendation=_recommendation(
            "staged_entry", rationale=["Concentration risk dominates [E-001]", "Secondary point"]
        ),
    )
    assert position.top_reason == "Concentration risk dominates [E-001]"


def test_two_tracks_on_the_same_family_are_rejected() -> None:
    positions = [
        build_position(
            track_id="track-a", model="composer-2.5", recommendation=_recommendation("a")
        ),
        build_position(
            track_id="track-b", model="composer-2.5", recommendation=_recommendation("b")
        ),
    ]
    with pytest.raises(ValidationError, match="two distinct model families"):
        compare_tracks(stage="preliminary_recommendation", positions=positions)


def test_a_single_track_is_not_a_divergence() -> None:
    with pytest.raises(ValidationError):
        TrackDivergence(
            stage="preliminary_recommendation",
            positions=[
                build_position(
                    track_id="track-a",
                    model="composer-2.5",
                    recommendation=_recommendation("a"),
                )
            ],
            agreement=True,
            divergence_summary="Only one track ran.",
        )
