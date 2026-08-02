"""The user's decision at the final gate.

The framing gate has had an auditable record since SPEC-010 (``FramingApproval``); the
final gate had none, so the second and more consequential consent moment left no trace
beyond a boolean in ``state.yaml``. This artifact closes that asymmetry: accepting a
recommendation, or sending it back, is now a recorded act with an author and a time.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import model_validator

from orchestrator.artifacts.common import ArtifactModel, NonEmptyStr


class FinalDecision(StrEnum):
    ACCEPT = "accept"
    REVISE = "revise"


class FinalApproval(ArtifactModel):
    decision: FinalDecision
    approved_by: NonEmptyStr
    approved_at: datetime
    note: str = ""

    @model_validator(mode="after")
    def validate_decision_payload(self) -> FinalApproval:
        if self.decision is FinalDecision.REVISE and not self.note.strip():
            raise ValueError(
                "A note is required when decision is 'revise'; it is what the synthesis pass "
                "is asked to address."
            )
        return self
