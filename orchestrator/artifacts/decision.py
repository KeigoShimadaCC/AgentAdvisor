from __future__ import annotations

from datetime import date

from pydantic import Field

from orchestrator.artifacts.common import (
    ArtifactModel,
    CaseId,
    Depth,
    NonEmptyStr,
    Reversibility,
    RiskTolerance,
)


class DecisionSpec(ArtifactModel):
    decision_id: CaseId
    question: NonEmptyStr
    owner: NonEmptyStr
    deadline: date
    alternatives: list[NonEmptyStr] = Field(min_length=1)
    objectives: list[NonEmptyStr] = Field(min_length=1)
    constraints: list[NonEmptyStr] = Field(default_factory=list)
    risk_tolerance: RiskTolerance
    reversibility: Reversibility
    depth: Depth
