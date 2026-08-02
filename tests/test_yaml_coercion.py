from __future__ import annotations

import pytest

from orchestrator.artifacts import (
    ObjectionRecord,
    PreliminaryRecommendation,
)
from orchestrator.artifacts.yaml_io import (
    coerce_payload_for_model,
    fill_missing_required_defaults,
)


def _recommendation_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "preferred_alternative": "staged_entry",
        "rationale": ["Growth is strong [E-001]"],
        "key_assumptions": [],
        "outcome_probabilities": {
            "positive_return_12m": {"method": "scenario_model", "point": 0.5}
        },
        "evidence_confidence": {"value": 0.5, "basis": "Mixed"},
        "recommendation_confidence": {"value": 0.6, "basis": "Balanced"},
        "model_stability": {
            "share_of_sensitivity_runs_supporting_recommendation": 1.0,
            "runs_total": 2,
            "runs_supporting": 2,
        },
        "unresolved_evidence_gaps": [],
        "major_risks": ["drawdown"],
    }
    payload.update(overrides)
    return payload


def test_a_bare_level_word_becomes_a_confidence_assessment() -> None:
    payload = _recommendation_payload(evidence_confidence="medium")

    coerced = coerce_payload_for_model(PreliminaryRecommendation, payload)
    model = PreliminaryRecommendation.model_validate(coerced)

    assert model.evidence_confidence.value == pytest.approx(0.5)
    assert "medium" in model.evidence_confidence.basis


def test_the_conversion_is_disclosed_in_the_basis_not_hidden() -> None:
    payload = _recommendation_payload(recommendation_confidence="high")

    model = PreliminaryRecommendation.model_validate(
        coerce_payload_for_model(PreliminaryRecommendation, payload)
    )

    assert model.recommendation_confidence.value == pytest.approx(0.75)
    assert "did not supply" in model.recommendation_confidence.basis


def test_an_unrecognized_word_is_left_alone_to_fail_validation() -> None:
    payload = _recommendation_payload(evidence_confidence="vibes")

    coerced = coerce_payload_for_model(PreliminaryRecommendation, payload)

    assert coerced["evidence_confidence"] == "vibes"


def test_a_real_assessment_is_never_overwritten() -> None:
    payload = _recommendation_payload()

    coerced = coerce_payload_for_model(PreliminaryRecommendation, payload)

    assert coerced["evidence_confidence"] == {"value": 0.5, "basis": "Mixed"}


def test_inconsistent_model_stability_share_is_recomputed() -> None:
    payload = _recommendation_payload(
        model_stability={
            "share_of_sensitivity_runs_supporting_recommendation": 0.9,
            "runs_total": 4,
            "runs_supporting": 1,
        }
    )

    model = PreliminaryRecommendation.model_validate(
        coerce_payload_for_model(PreliminaryRecommendation, payload)
    )

    assert model.model_stability.share_of_sensitivity_runs_supporting_recommendation == (
        pytest.approx(0.25)
    )


def test_a_missing_confidence_field_gets_a_conservative_default() -> None:
    payload = _recommendation_payload()
    del payload["evidence_confidence"]

    filled = fill_missing_required_defaults(PreliminaryRecommendation, payload)
    model = PreliminaryRecommendation.model_validate(filled)

    assert model.evidence_confidence.value == pytest.approx(0.5)
    assert model.evidence_confidence.basis == "Not independently assessed"


def test_missing_content_fields_are_not_invented() -> None:
    payload = _recommendation_payload()
    del payload["outcome_probabilities"]

    filled = fill_missing_required_defaults(PreliminaryRecommendation, payload)

    assert "outcome_probabilities" not in filled


def test_a_known_enum_mistake_is_mapped_to_the_valid_value() -> None:
    payload = {
        "objection_id": "O-001",
        "target_section": "preliminary_recommendation.rationale[0]",
        "claim": "The growth extrapolation is unsupported.",
        "materiality": "high",
        "reasoning": "No source establishes forward growth.",
        "reversal_evidence": "Forward guidance from the company.",
        "referenced_evidence_ids": [],
        "referenced_assumption_ids": [],
        "resolution_status": "unresolved",
        "commissioned_tasks": [],
    }

    model = ObjectionRecord.model_validate(coerce_payload_for_model(ObjectionRecord, payload))

    assert model.resolution_status.value == "open"
