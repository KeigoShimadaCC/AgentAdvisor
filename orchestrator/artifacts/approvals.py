"""Final approval artifact for the second consent gate (SPEC-027).

The framing gate uses :class:`~orchestrator.artifacts.intake.FramingApproval`;
this module adds the final-gate equivalent so that ``final_approved=True``
always has an auditable record on disk.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from orchestrator.artifacts.common import ArtifactModel, NonEmptyStr


class FinalDecision(StrEnum):
    ACCEPT = "accept"
    REVISE = "revise"


class FinalApproval(ArtifactModel):
    decision: FinalDecision
    note: str = Field(default="")
    approved_by: NonEmptyStr
    approved_at: datetime

    @model_validator(mode="after")
    def validate_decision_payload(self) -> FinalApproval:
        if self.decision is FinalDecision.REVISE and not self.note.strip():
            raise ValueError("note is required when decision is 'revise'.")
        if self.decision is FinalDecision.ACCEPT and self.note.strip():
            raise ValueError("note must be empty when decision is 'accept'.")
        return self
