from __future__ import annotations

from pydantic import Field, model_validator

from orchestrator.artifacts.common import ArtifactModel


class ModelStability(ArtifactModel):
    share_of_sensitivity_runs_supporting_recommendation: float = Field(ge=0.0, le=1.0)
    runs_total: int = Field(ge=1)
    runs_supporting: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_consistency(self) -> ModelStability:
        if self.runs_supporting > self.runs_total:
            raise ValueError("runs_supporting must be less than or equal to runs_total.")

        expected_share = self.runs_supporting / self.runs_total
        if abs(self.share_of_sensitivity_runs_supporting_recommendation - expected_share) > 1e-6:
            raise ValueError(
                "share_of_sensitivity_runs_supporting_recommendation must equal "
                "runs_supporting / runs_total within tolerance 1e-6."
            )

        return self
