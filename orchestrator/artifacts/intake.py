from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from orchestrator.artifacts.common import (
    ArtifactModel,
    Depth,
    NonEmptyStr,
    Reversibility,
    RiskTolerance,
)


class IntakeField(StrEnum):
    DECISION_QUESTION = "decision_question"
    DEADLINE = "deadline"
    ALTERNATIVES_MENTIONED = "alternatives_mentioned"
    OBJECTIVES = "objectives"
    CONSTRAINTS = "constraints"
    RISK_TOLERANCE = "risk_tolerance"
    REVERSIBILITY = "reversibility"
    DEPTH = "depth"


class ClarificationQuestion(ArtifactModel):
    question_id: NonEmptyStr
    resolves_field: IntakeField
    question: NonEmptyStr
    materiality_reason: NonEmptyStr


class IntakeRecord(ArtifactModel):
    raw_prompt: NonEmptyStr
    decision_question: NonEmptyStr | None = None
    deadline: date | None = None
    alternatives_mentioned: list[NonEmptyStr] | None = Field(default=None, min_length=1)
    objectives: list[NonEmptyStr] | None = Field(default=None, min_length=1)
    constraints: list[NonEmptyStr] | None = Field(default=None, min_length=1)
    risk_tolerance: RiskTolerance | None = None
    reversibility: Reversibility | None = None
    depth: Depth | None = None
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def validate_clarifications_target_unknown_fields(self) -> IntakeRecord:
        unknown_fields: dict[IntakeField, Any] = {
            IntakeField.DECISION_QUESTION: self.decision_question,
            IntakeField.DEADLINE: self.deadline,
            IntakeField.ALTERNATIVES_MENTIONED: self.alternatives_mentioned,
            IntakeField.OBJECTIVES: self.objectives,
            IntakeField.CONSTRAINTS: self.constraints,
            IntakeField.RISK_TOLERANCE: self.risk_tolerance,
            IntakeField.REVERSIBILITY: self.reversibility,
            IntakeField.DEPTH: self.depth,
        }
        for clarification in self.clarification_questions:
            if unknown_fields[clarification.resolves_field] is not None:
                raise ValueError(
                    f"clarification question {clarification.question_id!r} targets "
                    f"{clarification.resolves_field.value}, but that field is already populated."
                )
        return self


class FramingDecision(StrEnum):
    APPROVE = "approve"
    EDIT = "edit"
    ANSWER_CLARIFICATIONS = "answer_clarifications"


class FramingApproval(ArtifactModel):
    decision: FramingDecision
    approved_by: NonEmptyStr
    approved_at: datetime
    edits: dict[NonEmptyStr, Any] = Field(default_factory=dict)
    clarification_answers: dict[NonEmptyStr, NonEmptyStr] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_decision_payload(self) -> FramingApproval:
        if self.decision is FramingDecision.EDIT and not self.edits:
            raise ValueError("edits are required when decision is 'edit'.")
        if (
            self.decision is FramingDecision.ANSWER_CLARIFICATIONS
            and not self.clarification_answers
        ):
            raise ValueError(
                "clarification_answers are required when decision is 'answer_clarifications'."
            )
        if self.decision is FramingDecision.APPROVE:
            if self.edits:
                raise ValueError("edits must be empty when decision is 'approve'.")
            if self.clarification_answers:
                raise ValueError("clarification_answers must be empty when decision is 'approve'.")
        return self
