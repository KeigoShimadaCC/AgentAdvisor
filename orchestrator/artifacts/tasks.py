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
    probability_of_changing_conclusion: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Estimated probability that this task's output changes the recommendation.",
    )
    estimated_cost: float = Field(
        default=1.0,
        gt=0.0,
        description="Estimated cost in expected agent-invocation units.",
    )
    inputs: list[NonEmptyStr] = Field(min_length=1)
    required_output: NonEmptyStr
    completion_criteria: NonEmptyStr
    status: TaskStatus
    priority: PriorityLevel
    priority_score: int = Field(ge=1, le=100)
    priority_rationale: NonEmptyStr
