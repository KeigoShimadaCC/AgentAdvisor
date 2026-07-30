from __future__ import annotations

from pydantic import Field

from orchestrator.artifacts.common import (
    ArtifactModel,
    Level,
    NonEmptyStr,
    ObjectionId,
    ObjectionResolutionStatus,
    TaskId,
)


class ObjectionRecord(ArtifactModel):
    objection_id: ObjectionId
    target: NonEmptyStr
    claim: NonEmptyStr
    materiality: Level
    reasoning: NonEmptyStr
    resolution_status: ObjectionResolutionStatus
    commissioned_tasks: list[TaskId] = Field(default_factory=list)
