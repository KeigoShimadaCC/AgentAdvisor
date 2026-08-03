"""Placeholder detection, driven through the coercion layer that writes the markers.

The existing render tests assert against the literal basis strings, which proves the
predicate works today but not that it keeps working. These drive the *real* coercion
entry points instead, so rewording a filler in `yaml_io` breaks a test here rather than
silently turning a placeholder back into a rendered measurement.
"""

from __future__ import annotations

from typing import Any

from orchestrator.artifacts.confidence import ConfidenceAssessment
from orchestrator.artifacts.sentinels import (
    COERCION_DEFAULT_BASES,
    CONFIDENCE_WORD_PREFIX,
    confidence_render_label,
    is_confidence_placeholder,
    is_model_stability_placeholder,
    model_stability_render_label,
)
from orchestrator.artifacts.stability import ModelStability
from orchestrator.artifacts.yaml_io import (
    _CONFIDENCE_WORD_VALUES,
    _DEFAULT_FILLERS,
    _confidence_from_word,
)


def _filled(field_name: str) -> dict[str, Any]:
    return dict(_DEFAULT_FILLERS[field_name])


# --- the markers are derived, not copied -------------------------------------------


def test_every_confidence_filler_basis_is_recognised() -> None:
    """Whatever `_DEFAULT_FILLERS` stamps on a confidence must read as a placeholder."""
    bases = [str(filler["basis"]) for filler in _DEFAULT_FILLERS.values() if "basis" in filler]
    assert bases, "no confidence fillers found — this test has lost its subject"

    for basis in bases:
        assert basis.strip() in COERCION_DEFAULT_BASES
        assert is_confidence_placeholder(ConfidenceAssessment(value=0.5, basis=basis))


def test_every_qualitative_word_conversion_is_recognised() -> None:
    """Each word `yaml_io` converts must produce a basis the sentinel catches."""
    for word in _CONFIDENCE_WORD_VALUES:
        converted = _confidence_from_word(word)
        assert converted is not None

        confidence = ConfidenceAssessment(
            value=float(converted["value"]), basis=str(converted["basis"])
        )
        assert is_confidence_placeholder(confidence), f"missed conversion of {word!r}"
        assert "Not assessed" in confidence_render_label(confidence)


def test_the_word_prefix_is_derived_from_a_real_conversion() -> None:
    """The prefix must be a genuine prefix of what `yaml_io` writes, not a guess."""
    converted = _confidence_from_word(next(iter(_CONFIDENCE_WORD_VALUES)))
    assert converted is not None
    assert str(converted["basis"]).startswith(CONFIDENCE_WORD_PREFIX)
    assert CONFIDENCE_WORD_PREFIX.strip(), "an empty prefix would match everything"


def test_the_stability_filler_is_recognised() -> None:
    stability = ModelStability(**_filled("model_stability"))
    assert is_model_stability_placeholder(stability)
    assert "not assessed" in model_stability_render_label(stability)


# --- real assessments are left alone -------------------------------------------------


def test_a_real_confidence_is_not_a_placeholder() -> None:
    confidence = ConfidenceAssessment(
        value=0.74,
        basis="Staged entry dominates alternatives across most tested sensitivities.",
    )
    assert not is_confidence_placeholder(confidence)

    label = confidence_render_label(confidence)
    assert "74.0%" in label
    assert "Not assessed" not in label


def test_a_measured_stability_is_not_a_placeholder() -> None:
    stability = ModelStability(
        share_of_sensitivity_runs_supporting_recommendation=0.8,
        runs_total=20,
        runs_supporting=16,
    )
    assert not is_model_stability_placeholder(stability)

    label = model_stability_render_label(stability)
    assert "16/20" in label
    assert "not assessed" not in label


def test_a_single_supported_run_is_not_treated_as_a_filler() -> None:
    """The filler is one run with zero support; one run that *did* support is real."""
    stability = ModelStability(
        share_of_sensitivity_runs_supporting_recommendation=1.0,
        runs_total=1,
        runs_supporting=1,
    )
    assert not is_model_stability_placeholder(stability)


def test_a_confidence_merely_mentioning_assessment_is_not_a_placeholder() -> None:
    """Matching is exact or prefixed, so ordinary prose cannot be mistaken for a filler."""
    confidence = ConfidenceAssessment(
        value=0.6,
        basis="Two sources were independently assessed and agree on the direction.",
    )
    assert not is_confidence_placeholder(confidence)
