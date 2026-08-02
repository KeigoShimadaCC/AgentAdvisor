from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from orchestrator.artifacts.common import (
    ArtifactModel,
    IssueNodeId,
    Level,
    NonEmptyStr,
    ObjectionId,
    PriorityLevel,
    TaskRole,
)


class PlanningMode(StrEnum):
    INITIAL = "initial"
    REPAIR = "repair"


class TaskProposalRecord(ArtifactModel):
    role: TaskRole
    issue_node_id: IssueNodeId | None = None
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
    priority: PriorityLevel
    priority_score: int = Field(ge=1, le=100)
    priority_rationale: NonEmptyStr


class TaskProposal(ArtifactModel):
    task: TaskProposalRecord
    depends_on_indices: list[int] = Field(default_factory=list)
    resolves_objections: list[ObjectionId] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dependency_indices_non_negative(self) -> TaskProposal:
        for dependency_index in self.depends_on_indices:
            if dependency_index < 0:
                raise ValueError("depends_on_indices must contain only non-negative indices.")
        return self


class TaskProposalBatch(ArtifactModel):
    mode: PlanningMode
    proposals: list[TaskProposal] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_caps_and_dependency_ranges(self) -> TaskProposalBatch:
        cap = 4 if self.mode is PlanningMode.REPAIR else 10
        if len(self.proposals) > cap:
            raise ValueError(f"proposals exceeds {cap} cap for mode '{self.mode.value}'.")

        if self.mode is PlanningMode.REPAIR:
            for proposal_index, proposal in enumerate(self.proposals):
                if not proposal.resolves_objections:
                    raise ValueError(
                        "repair mode requires resolves_objections for every proposal; "
                        f"proposal index {proposal_index} is missing it."
                    )

        for proposal_index, proposal in enumerate(self.proposals):
            for dependency_index in proposal.depends_on_indices:
                if dependency_index >= len(self.proposals):
                    raise ValueError(
                        "depends_on_indices contains out-of-range index "
                        f"{dependency_index} for proposal index {proposal_index}."
                    )
                if dependency_index == proposal_index:
                    raise ValueError(f"proposal index {proposal_index} cannot depend on itself.")
        return self
