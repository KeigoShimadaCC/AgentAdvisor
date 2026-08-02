from __future__ import annotations

from pydantic import Field, model_validator

from orchestrator.artifacts.common import ArtifactModel, NonEmptyStr


class TrackPosition(ArtifactModel):
    track_id: NonEmptyStr
    model: NonEmptyStr
    model_family: NonEmptyStr
    preferred_alternative: NonEmptyStr
    top_reason: NonEmptyStr
    recommendation_confidence: float = Field(ge=0.0, le=1.0)


class TrackDivergence(ArtifactModel):
    """Result of running two independent theses on different model families.

    This is a diversity signal, not a probability. It never feeds ``model_stability``
    and the positions are never averaged; disagreement is reported as disagreement.
    """

    stage: NonEmptyStr
    positions: list[TrackPosition] = Field(min_length=2)
    agreement: bool
    divergence_summary: NonEmptyStr
    reconciled_alternative: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_families_differ(self) -> TrackDivergence:
        families = {position.model_family for position in self.positions}
        if len(families) < 2:
            raise ValueError(
                "dual-track reasoning requires at least two distinct model families; "
                f"got {sorted(families)}."
            )
        return self
