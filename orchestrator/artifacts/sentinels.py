"""Predicates that recognise coercion placeholders in artifact values.

`orchestrator.artifacts.yaml_io` fills a missing or malformed uncertainty field
with a conservative placeholder rather than losing the whole case, and records
the substitution in a `CoercionReport`. That report is a live object owned by one
validation pass: a rendered case is read back from disk long after it is gone, so
everything downstream of storage has to recognise a placeholder from the stored
value alone.

North star Section 9 calls presenting one uncertainty quantity as another a
defect; presenting a placeholder as a measurement is the same defect. These
predicates are the single source of truth for "this value was never assessed" —
the Markdown export and the CaseView projection import them instead of
re-deriving the rule and disagreeing about it.
"""

from __future__ import annotations

from orchestrator.artifacts.confidence import ConfidenceAssessment
from orchestrator.artifacts.stability import ModelStability

# Private imports on purpose: the filler texts must come from the module that
# writes them. A second copy of the literals would drift, and a drifted sentinel
# fails silently by re-labelling a placeholder as a measurement.
from orchestrator.artifacts.yaml_io import (
    _CONFIDENCE_WORD_VALUES,
    _DEFAULT_FILLERS,
    _confidence_from_word,
)

UNASSESSED_STABILITY_REASON = "single run"
UNASSESSED_CONFIDENCE_REASON = "coercion placeholder rather than an assessment"


def _placeholder_confidence_bases() -> frozenset[str]:
    """Every `basis` string the coercion layer can write into a confidence field."""
    bases = {str(filler["basis"]) for filler in _DEFAULT_FILLERS.values() if "basis" in filler}
    for word in _CONFIDENCE_WORD_VALUES:
        converted = _confidence_from_word(word)
        if converted is not None:
            bases.add(str(converted["basis"]))
    return frozenset(basis.strip() for basis in bases)


PLACEHOLDER_CONFIDENCE_BASES: frozenset[str] = _placeholder_confidence_bases()


def is_unassessed_stability(model_stability: ModelStability) -> bool:
    """True when the stability figure measures nothing.

    A single run cannot vary an assumption, so `runs_total <= 1` is either the
    coercion default (`runs_total: 1`, `runs_supporting: 0`, share `0.0`) or a
    lone run. Either way the share is arithmetic over one sample, not a
    sensitivity result.
    """
    return model_stability.runs_total <= 1


def is_unassessed_confidence(confidence: ConfidenceAssessment) -> bool:
    """True when the basis is one of the coercion layer's filler texts.

    The value carried alongside such a basis is a default (0.5) or a number read
    off a prose word, never a calibrated assessment.
    """
    return confidence.basis.strip() in PLACEHOLDER_CONFIDENCE_BASES
