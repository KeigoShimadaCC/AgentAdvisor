"""Dual-track reasoning: two independent theses, compared, never averaged.

One Director on one model is a single point of epistemic failure. Two Directors on
different model families give a real diversity signal. The signal is reported as
agreement or disagreement; it is never converted into a probability and never feeds
``model_stability``, which remains a property of the sensitivity analysis.
"""

from __future__ import annotations

import re

from orchestrator.artifacts import PreliminaryRecommendation, TrackDivergence, TrackPosition
from orchestrator.roles_config import family

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _normalize_alternative(value: str) -> str:
    return _NON_ALNUM_RE.sub(" ", value.lower()).strip()


def _top_reason(recommendation: PreliminaryRecommendation) -> str:
    return recommendation.rationale[0] if recommendation.rationale else "no rationale supplied"


def build_position(
    *,
    track_id: str,
    model: str,
    recommendation: PreliminaryRecommendation,
) -> TrackPosition:
    return TrackPosition(
        track_id=track_id,
        model=model,
        model_family=family(model, canonical=True),
        preferred_alternative=recommendation.preferred_alternative,
        top_reason=_top_reason(recommendation),
        recommendation_confidence=recommendation.recommendation_confidence.value,
    )


def compare_tracks(
    *,
    stage: str,
    positions: list[TrackPosition],
) -> TrackDivergence:
    normalized = {_normalize_alternative(position.preferred_alternative) for position in positions}
    agreement = len(normalized) == 1

    if agreement:
        summary = (
            f"Both tracks independently preferred '{positions[0].preferred_alternative}'. "
            "Agreement across model families is a weak positive signal, not evidence."
        )
    else:
        rendered = "; ".join(
            f"{position.track_id} ({position.model_family}) -> {position.preferred_alternative}"
            for position in positions
        )
        summary = (
            f"Tracks disagreed: {rendered}. The disagreement is reported, not averaged, and "
            "must be resolved on the merits or carried forward as unresolved."
        )

    return TrackDivergence(
        stage=stage,
        positions=positions,
        agreement=agreement,
        divergence_summary=summary,
    )
