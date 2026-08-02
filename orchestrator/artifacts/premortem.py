from __future__ import annotations

from pydantic import Field, model_validator

from orchestrator.artifacts.common import (
    ArtifactModel,
    AssumptionId,
    EvidenceId,
    Level,
    NonEmptyStr,
)
from orchestrator.artifacts.probability import ProbabilityEstimate

MAX_FAILURE_MODES = 5


class FailureMode(ArtifactModel):
    failure_mode: NonEmptyStr
    narrative: NonEmptyStr
    probability: ProbabilityEstimate
    severity: Level
    leading_indicators: list[NonEmptyStr] = Field(min_length=1)
    preventive_action: NonEmptyStr
    referenced_evidence_ids: list[EvidenceId] = Field(default_factory=list)
    referenced_assumption_ids: list[AssumptionId] = Field(default_factory=list)


class PreMortemReport(ArtifactModel):
    """Prospective hindsight: assume the recommendation was taken and it failed.

    Distinct from the Challenger, which attacks the reasoning as it stands. This
    attacks the future, and its leading indicators become change-triggers.
    """

    horizon: NonEmptyStr
    assumed_outcome: NonEmptyStr
    failure_modes: list[FailureMode] = Field(min_length=1)
    most_likely_failure_mode: NonEmptyStr

    @model_validator(mode="after")
    def validate_cap_and_reference(self) -> PreMortemReport:
        if len(self.failure_modes) > MAX_FAILURE_MODES:
            raise ValueError(f"failure_modes exceeds the {MAX_FAILURE_MODES} cap.")
        names = {mode.failure_mode for mode in self.failure_modes}
        if self.most_likely_failure_mode not in names:
            raise ValueError(
                "most_likely_failure_mode must match one of the listed failure_mode values."
            )
        return self
