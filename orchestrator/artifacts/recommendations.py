from __future__ import annotations

from pydantic import Field

from orchestrator.artifacts.common import (
    ArtifactModel,
    AssumptionId,
    EvidenceId,
    NonEmptyStr,
)
from orchestrator.artifacts.confidence import ConfidenceAssessment
from orchestrator.artifacts.probability import ProbabilityEstimate
from orchestrator.artifacts.stability import ModelStability


class AlternativeAssessment(ArtifactModel):
    alternative: NonEmptyStr
    rank: int = Field(ge=1)
    rationale: NonEmptyStr


class ScenarioAssessment(ArtifactModel):
    scenario_name: NonEmptyStr
    summary: NonEmptyStr
    probability: ProbabilityEstimate


class Counterargument(ArtifactModel):
    claim: NonEmptyStr
    resolution: NonEmptyStr
    resolved: bool


class PreliminaryRecommendation(ArtifactModel):
    preferred_alternative: NonEmptyStr
    rationale: list[NonEmptyStr] = Field(min_length=1)
    key_assumptions: list[AssumptionId] = Field(default_factory=list)
    outcome_probabilities: dict[NonEmptyStr, ProbabilityEstimate] = Field(min_length=1)
    evidence_confidence: ConfidenceAssessment
    recommendation_confidence: ConfidenceAssessment
    model_stability: ModelStability
    unresolved_evidence_gaps: list[NonEmptyStr] = Field(default_factory=list)
    major_risks: list[NonEmptyStr] = Field(default_factory=list)


class FinalRecommendation(ArtifactModel):
    recommended_action: NonEmptyStr
    timing: NonEmptyStr
    decision_confidence_summary: NonEmptyStr
    alternatives_considered: list[AlternativeAssessment] = Field(min_length=1)
    key_reasons: list[NonEmptyStr] = Field(min_length=1)
    scenario_analysis: list[ScenarioAssessment] = Field(min_length=1)
    quantitative_findings: list[NonEmptyStr] = Field(default_factory=list)
    strongest_counterarguments: list[Counterargument] = Field(default_factory=list)
    critical_assumptions: list[AssumptionId] = Field(default_factory=list)
    recommendation_change_triggers: list[NonEmptyStr] = Field(default_factory=list)
    next_actions: list[NonEmptyStr] = Field(min_length=1)
    citations: list[EvidenceId] = Field(default_factory=list)
    outcome_probabilities: dict[NonEmptyStr, ProbabilityEstimate] = Field(min_length=1)
    evidence_confidence: ConfidenceAssessment
    recommendation_confidence: ConfidenceAssessment
    model_stability: ModelStability
