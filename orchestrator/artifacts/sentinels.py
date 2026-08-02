"""Sentinel predicates for placeholder uncertainty values.

The coercion layer fills missing ``ModelStability``, ``evidence_confidence``, and
``recommendation_confidence`` fields with conservative defaults so validation can
pass.  These defaults are not real assessments — rendering them as measurements
(e.g. "0.0%" or "50%") violates north star Section 9: never present one quantity
as another.

This module is the single source of truth for "this value is a placeholder."
SPEC-032 (CaseView projection) imports these predicates rather than re-deriving.
"""

from __future__ import annotations

from orchestrator.artifacts.confidence import ConfidenceAssessment
from orchestrator.artifacts.stability import ModelStability

# Basis strings that mark a confidence as a coercion default, not a real assessment.
_COERCION_DEFAULT_BASIS = "Not independently assessed"

# Prefix that marks a confidence as a word-substitution conversion.
_CONFIDENCE_WORD_PREFIX = "Converted from the qualitative level"


def is_model_stability_placeholder(stability: ModelStability) -> bool:
    """True when the stability record is a coercion default (single run, zero support)."""
    return stability.runs_total <= 1 and stability.runs_supporting == 0


def is_confidence_placeholder(confidence: ConfidenceAssessment) -> bool:
    """True when the confidence was filled by coercion rather than assessed."""
    if confidence.basis.strip() == _COERCION_DEFAULT_BASIS:
        return True
    if confidence.basis.strip().startswith(_CONFIDENCE_WORD_PREFIX):
        return True
    return False


def confidence_render_label(confidence: ConfidenceAssessment) -> str:
    """Return the display string for a confidence, handling sentinels.

    Real assessments render as ``"62.5% (basis: …)"``.
    Placeholders render as ``"Not assessed (basis: …)"``.
    """
    if is_confidence_placeholder(confidence):
        return f"Not assessed (basis: {confidence.basis})"
    return f"{confidence.value * 100:.1f}% (basis: {confidence.basis})"


def model_stability_render_label(stability: ModelStability) -> str:
    """Return the display string for model stability, handling sentinels."""
    if is_model_stability_placeholder(stability):
        return "not assessed (single run)"
    share = stability.share_of_sensitivity_runs_supporting_recommendation
    return (
        f"{share * 100:.1f}% "
        f"({stability.runs_supporting}/{stability.runs_total} sensitivity runs "
        "support the recommendation)"
    )
