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


class IndependentVerdict(StrEnum):
    CONCUR = "concur"
    CONCUR_WITH_RESERVATIONS = "concur_with_reservations"
    DISSENT = "dissent"


class IndependentReview(ArtifactModel):
    """A second opinion on the substance, from a reviewer that never saw the reasoning.

    The existing ``ReviewReport`` is a conformance check: citations resolve, confidence
    language matches, worksheet items are all answered.  It catches malformed output but
    cannot catch a well-formed conclusion the evidence does not support, because nobody
    re-derives the answer.

    This role receives the conclusion and the raw evidence ledger but not the thesis
    history, objections, track divergence or pre-mortem, and answers one question: would
    you reach this conclusion from this evidence?
    """

    verdict: IndependentVerdict
    reasoning: NonEmptyStr
    #: Required on dissent: the conclusion this reviewer would have reached instead.
    #: A dissent that cannot name an alternative is a reservation, not a dissent.
    divergent_conclusion: NonEmptyStr | None = None
    unsupported_claims: list[NonEmptyStr] = Field(default_factory=list)
    evidence_ids: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dissent_names_an_alternative(self) -> IndependentReview:
        if self.verdict is IndependentVerdict.DISSENT and not self.divergent_conclusion:
            raise ValueError(
                "divergent_conclusion is required when verdict is 'dissent': a dissent that "
                "cannot state the conclusion it would reach instead is a reservation."
            )
        if self.verdict is IndependentVerdict.CONCUR and self.divergent_conclusion:
            raise ValueError("divergent_conclusion must be empty when verdict is 'concur'.")
        return self


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
