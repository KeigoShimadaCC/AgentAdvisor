from __future__ import annotations

from pydantic import Field

from orchestrator.artifacts.common import (
    ArtifactModel,
    AssumptionId,
    AssumptionStatus,
    AssumptionType,
    EvidenceId,
    Level,
    NonEmptyStr,
)
from orchestrator.artifacts.probability import ProbabilityEstimate


class AssumptionRecord(ArtifactModel):
    assumption_id: AssumptionId
    claim: NonEmptyStr
    type: AssumptionType
    estimate: ProbabilityEstimate
    confidence: Level
    materiality: Level
    evidence_for: list[EvidenceId] = Field(default_factory=list)
    evidence_against: list[EvidenceId] = Field(default_factory=list)
    status: AssumptionStatus
