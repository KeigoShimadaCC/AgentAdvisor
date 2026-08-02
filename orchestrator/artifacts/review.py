from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import Field, model_validator

from orchestrator.artifacts.common import ArtifactModel, NonEmptyStr
from orchestrator.artifacts.verification import CitationVerdict

ReviewTargetId = Annotated[str, Field(pattern=r"^(?:case-\d+[-a-z0-9-]*|[EATO]-\d+)$")]


class ReviewOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class ReviewDefectType(StrEnum):
    FALSE_PRECISION = "false_precision"
    UNSUPPORTED_CITATION = "unsupported_citation"
    CONFIDENCE_LANGUAGE_MISMATCH = "confidence_language_mismatch"
    INDEPENDENCE_OVERSTATEMENT = "independence_overstatement"


class ReviewDefect(ArtifactModel):
    defect_type: ReviewDefectType
    target_id: ReviewTargetId
    explanation: NonEmptyStr


class ReviewReport(ArtifactModel):
    outcome: ReviewOutcome
    defects: list[ReviewDefect] = Field(default_factory=list)
    citation_verdicts: list[CitationVerdict] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_outcome_defect_consistency(self) -> ReviewReport:
        if self.outcome is ReviewOutcome.FAIL and not self.defects:
            raise ValueError("defects must be non-empty when outcome is 'fail'.")
        if self.outcome is ReviewOutcome.PASS and self.defects:
            raise ValueError("defects must be empty when outcome is 'pass'.")
        return self
