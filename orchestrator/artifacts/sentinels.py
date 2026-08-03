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

# The marker strings are derived from the module that writes them, never copied.
# A second copy would drift the first time a filler is reworded, and a drifted
# sentinel fails silently in the worst direction: it stops recognising a
# placeholder and the renderer presents it as a measurement again — the exact
# defect this module exists to prevent.
from orchestrator.artifacts.yaml_io import (  # noqa: PLC2701 - see above
    _CONFIDENCE_WORD_VALUES,
    _DEFAULT_FILLERS,
    _confidence_from_word,
)


def _coercion_default_bases() -> frozenset[str]:
    """Every basis string `_DEFAULT_FILLERS` can stamp on a confidence."""
    return frozenset(
        str(filler["basis"]).strip() for filler in _DEFAULT_FILLERS.values() if "basis" in filler
    )


def _confidence_word_prefix() -> str:
    """The invariant prefix of a word-substitution basis.

    Derived by asking `_confidence_from_word` for a real conversion and keeping the
    part before the quoted level, so a reworded message is picked up automatically.
    """
    sample_word = next(iter(_CONFIDENCE_WORD_VALUES))
    converted = _confidence_from_word(sample_word)
    if converted is None:  # pragma: no cover - impossible for a known word
        raise RuntimeError("yaml_io no longer converts a known confidence word.")
    return str(converted["basis"]).split("'", 1)[0]


#: Computed once at import; both are pure functions of yaml_io's own constants.
COERCION_DEFAULT_BASES = _coercion_default_bases()
CONFIDENCE_WORD_PREFIX = _confidence_word_prefix()


def is_model_stability_placeholder(stability: ModelStability) -> bool:
    """True when the stability record is a coercion default (single run, zero support)."""
    return stability.runs_total <= 1 and stability.runs_supporting == 0


def is_confidence_placeholder(confidence: ConfidenceAssessment) -> bool:
    """True when the confidence was filled by coercion rather than assessed."""
    basis = confidence.basis.strip()
    if basis in COERCION_DEFAULT_BASES:
        return True
    if basis.startswith(CONFIDENCE_WORD_PREFIX):
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
