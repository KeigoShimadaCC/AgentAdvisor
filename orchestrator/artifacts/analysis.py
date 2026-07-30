from __future__ import annotations

from pathlib import PurePosixPath

from pydantic import Field, model_validator

from orchestrator.artifacts.common import (
    ArtifactModel,
    AssumptionId,
    EvidenceId,
    NonEmptyStr,
    TaskId,
)
from orchestrator.artifacts.probability import ProbabilityEstimate


class AnalysisScenario(ArtifactModel):
    scenario_name: NonEmptyStr
    probability: ProbabilityEstimate


class SensitivityRow(ArtifactModel):
    parameter: NonEmptyStr
    parameter_value: float | NonEmptyStr
    resulting_expected_values: dict[NonEmptyStr, float] = Field(min_length=1)
    preferred_alternative: NonEmptyStr

    @model_validator(mode="after")
    def validate_preferred_alternative_present(self) -> SensitivityRow:
        if self.preferred_alternative not in self.resulting_expected_values:
            raise ValueError("preferred_alternative must be a key in resulting_expected_values.")
        return self


class BreakEvenThreshold(ArtifactModel):
    parameter: NonEmptyStr
    threshold_value: float
    favored_alternative_below: NonEmptyStr
    favored_alternative_above: NonEmptyStr


class AnalysisResult(ArtifactModel):
    task_id: TaskId
    script_path: NonEmptyStr
    results_path: NonEmptyStr
    scenarios: list[AnalysisScenario] = Field(min_length=1)
    expected_values_by_alternative: dict[NonEmptyStr, float] = Field(min_length=1)
    sensitivity_table: list[SensitivityRow] = Field(min_length=1)
    break_even_thresholds: list[BreakEvenThreshold] = Field(default_factory=list)
    assumption_ids: list[AssumptionId] = Field(default_factory=list)
    evidence_ids: list[EvidenceId] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_paths_and_sensitivity_shape(self) -> AnalysisResult:
        for field_name, path_value in (
            ("script_path", self.script_path),
            ("results_path", self.results_path),
        ):
            path = PurePosixPath(path_value)
            if path.is_absolute():
                raise ValueError(f"{field_name} must be relative to the case root.")
            if ".." in path.parts:
                raise ValueError(f"{field_name} must not contain '..' path traversal.")

        expected_alternatives = set(self.expected_values_by_alternative.keys())
        for row_index, sensitivity_row in enumerate(self.sensitivity_table):
            row_alternatives = set(sensitivity_row.resulting_expected_values.keys())
            if row_alternatives != expected_alternatives:
                raise ValueError(
                    "sensitivity_table row "
                    f"{row_index} expected value keys {sorted(row_alternatives)} do not match "
                    "expected_values_by_alternative keys "
                    f"{sorted(expected_alternatives)}."
                )
        return self
