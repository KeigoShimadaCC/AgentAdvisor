from __future__ import annotations

from pydantic import Field

from orchestrator.artifacts.common import ArtifactModel, NonEmptyStr


class ConfidenceAssessment(ArtifactModel):
    value: float = Field(ge=0.0, le=1.0)
    basis: NonEmptyStr
