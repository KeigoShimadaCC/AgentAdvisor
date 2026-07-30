from __future__ import annotations

from pydantic import Field

from orchestrator.artifacts.common import (
    ArtifactModel,
    Level,
    NonEmptyStr,
    PriorityLevel,
    TaskId,
    TaskRole,
    TaskStatus,
)


class TaskRecord(ArtifactModel):
    task_id: TaskId
    role: TaskRole
    question: NonEmptyStr
    why_it_matters: NonEmptyStr
    expected_information_gain: Level
    materiality: Level
    inputs: list[NonEmptyStr] = Field(min_length=1)
    required_output: NonEmptyStr
    completion_criteria: NonEmptyStr
    status: TaskStatus
    priority: PriorityLevel
    priority_score: int = Field(ge=1, le=100)
    priority_rationale: NonEmptyStr
