from __future__ import annotations

from datetime import date

from pydantic import Field, model_validator

from orchestrator.artifacts.common import (
    ArtifactModel,
    CaseId,
    Depth,
    NonEmptyStr,
    Reversibility,
    RiskTolerance,
)


class DecisionSpec(ArtifactModel):
    decision_id: CaseId
    question: NonEmptyStr
    owner: NonEmptyStr
    deadline: date
    alternatives: list[NonEmptyStr] = Field(min_length=1)
    objectives: list[NonEmptyStr] = Field(min_length=1)
    constraints: list[NonEmptyStr] = Field(default_factory=list)
    risk_tolerance: RiskTolerance
    reversibility: Reversibility
    depth: Depth
    #: SPEC-038. Relative importance of each objective, as elicited from the decision
    #: owner at the scope checkpoint. Optional: a case without weights behaves exactly
    #: as it did before the value model existed.
    objective_weights: dict[NonEmptyStr, float] | None = None

    @model_validator(mode="after")
    def validate_objective_weights(self) -> DecisionSpec:
        if self.objective_weights is None:
            return self
        if not self.objective_weights:
            raise ValueError(
                "objective_weights must be omitted entirely rather than set to an empty mapping."
            )
        unknown = sorted(set(self.objective_weights) - set(self.objectives))
        if unknown:
            raise ValueError(f"objective_weights names objectives not in the spec: {unknown}")
        non_positive = sorted(name for name, w in self.objective_weights.items() if w <= 0)
        if non_positive:
            raise ValueError(
                f"objective_weights must be positive; non-positive for: {non_positive}"
            )
        return self
