from __future__ import annotations

from pydantic import Field, model_validator

from orchestrator.artifacts.common import ArtifactModel, EvidenceId, NonEmptyStr, ProbabilityMethod


class ProbabilityAdjustment(ArtifactModel):
    description: NonEmptyStr
    delta: float
    evidence_ids: list[EvidenceId] = Field(min_length=1)


class ProbabilityEstimate(ArtifactModel):
    method: ProbabilityMethod
    reference_class: NonEmptyStr | None = None
    base_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    point: float | None = Field(default=None, ge=0.0, le=1.0)
    interval_low: float | None = Field(default=None, ge=0.0, le=1.0)
    interval_high: float | None = Field(default=None, ge=0.0, le=1.0)
    adjustments: list[ProbabilityAdjustment] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_point_or_interval(self) -> ProbabilityEstimate:
        if self.method == ProbabilityMethod.REFERENCE_CLASS:
            if self.reference_class is None:
                raise ValueError("reference_class is required when method is reference_class.")
            if self.base_rate is None:
                raise ValueError("base_rate is required when method is reference_class.")

        has_point = self.point is not None
        has_interval = self.interval_low is not None or self.interval_high is not None

        if has_point and has_interval:
            raise ValueError("Use either point or interval_low/interval_high, not both.")
        if not has_point and not has_interval:
            raise ValueError("Either point or interval_low/interval_high is required.")
        if self.interval_low is None and self.interval_high is not None:
            raise ValueError("interval_low is required when interval_high is set.")
        if self.interval_high is None and self.interval_low is not None:
            raise ValueError("interval_high is required when interval_low is set.")
        if self.interval_low is not None and self.interval_high is not None:
            if self.interval_low > self.interval_high:
                raise ValueError("interval_low must be less than or equal to interval_high.")
        return self
