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
    #: SPEC-043. North star Section 8, Stage 1 lists "available internal information"
    #: among the things intake must extract. Nothing implemented it until now.
    INTERNAL_INFORMATION = "internal_information"


class ClarificationKind(StrEnum):
    """What an intake question is asking for.

    Before SPEC-043 every question had to map to one of eight framing fields, so intake
    could ask "what is your risk tolerance?" but not "what is your cost basis?" — and the
    facts that decide personal cases usually live in the decision owner's head rather
    than on the public web.
    """

    #: Fills one of the framing fields. ``resolves_field`` is required.
    FIELD = "field"
    #: Asks for a document to be placed in the case's ``inputs/`` directory.
    DOCUMENT = "document"
    #: Asks an open substantive question whose answer becomes user-supplied evidence.
    FACT = "fact"


class ClarificationQuestion(ArtifactModel):
    question_id: NonEmptyStr
    question: NonEmptyStr
    materiality_reason: NonEmptyStr
    kind: ClarificationKind = ClarificationKind.FIELD
    #: Required for ``field`` questions, forbidden otherwise. Defaulted so intake
    #: records written before SPEC-043 keep validating.
    resolves_field: IntakeField | None = None

    @model_validator(mode="after")
    def validate_field_target(self) -> ClarificationQuestion:
        if self.kind is ClarificationKind.FIELD and self.resolves_field is None:
            raise ValueError(
                f"clarification question {self.question_id!r} has kind 'field' but names "
                "no resolves_field."
            )
        if self.kind is not ClarificationKind.FIELD and self.resolves_field is not None:
            raise ValueError(
                f"clarification question {self.question_id!r} has kind "
                f"{self.kind.value!r}, which must not name a resolves_field."
            )
        return self


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
    #: SPEC-043 raised the cap from 5: document and fact requests now compete with
    #: field questions for the same budget.
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list, max_length=8)

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
            # Only field questions target a framing slot; document and fact questions
            # ask for material the record has no column for.
            if clarification.resolves_field is None:
                continue
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
