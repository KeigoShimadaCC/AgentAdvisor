"""The sentinel predicates must recognise whatever the coercion layer writes.

Each test drives the real coercion entry points rather than hand-writing the
filler text, so a change to `yaml_io` that the sentinels do not follow fails here
instead of silently re-labelling a placeholder as a measurement.
"""

from __future__ import annotations

from typing import Any

from orchestrator.artifacts import ConfidenceAssessment, FinalRecommendation, ModelStability
from orchestrator.artifacts.sentinels import (
    PLACEHOLDER_CONFIDENCE_BASES,
    is_unassessed_confidence,
    is_unassessed_stability,
)
from orchestrator.artifacts.yaml_io import (
    coerce_payload_for_model,
    fill_missing_required_defaults,
)


def _default_filled(field_name: str) -> dict[str, Any]:
    filled = fill_missing_required_defaults(FinalRecommendation, {})
    assert isinstance(filled, dict)
    value = filled[field_name]
    assert isinstance(value, dict)
    return value


def test_default_filled_stability_is_unassessed() -> None:
    stability = ModelStability.model_validate(_default_filled("model_stability"))

    assert is_unassessed_stability(stability)


def test_measured_stability_is_assessed() -> None:
    stability = ModelStability(
        share_of_sensitivity_runs_supporting_recommendation=0.8,
        runs_total=20,
        runs_supporting=16,
    )

    assert not is_unassessed_stability(stability)


def test_default_filled_confidence_is_unassessed() -> None:
    for field_name in ("evidence_confidence", "recommendation_confidence"):
        confidence = ConfidenceAssessment.model_validate(_default_filled(field_name))

        assert is_unassessed_confidence(confidence), field_name


def test_word_substituted_confidence_is_unassessed() -> None:
    coerced = coerce_payload_for_model(
        FinalRecommendation, {"recommendation_confidence": "moderate"}
    )
    assert isinstance(coerced, dict)
    confidence = ConfidenceAssessment.model_validate(coerced["recommendation_confidence"])

    assert is_unassessed_confidence(confidence)


def test_an_assessed_basis_is_not_a_sentinel() -> None:
    confidence = ConfidenceAssessment(
        value=0.63,
        basis="One high-directness filing plus one comparative study with stated limits.",
    )

    assert not is_unassessed_confidence(confidence)


def test_placeholder_bases_include_the_default_and_the_word_substitutions() -> None:
    assert "Not independently assessed" in PLACEHOLDER_CONFIDENCE_BASES
    assert any("qualitative level" in basis for basis in PLACEHOLDER_CONFIDENCE_BASES)
