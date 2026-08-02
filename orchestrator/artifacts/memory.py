from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from orchestrator.artifacts.common import (
    ArtifactModel,
    CaseId,
    Level,
    NonEmptyStr,
    SourceType,
)


class OutcomeRecord(ArtifactModel):
    """A realized outcome attached to a completed case, recorded by the user."""

    recorded_at: datetime
    outcome_summary: NonEmptyStr
    recommendation_followed: bool
    forecast_outcome_name: NonEmptyStr
    forecast_probability: float = Field(ge=0.0, le=1.0)
    realized: bool


class PriorCaseEntry(ArtifactModel):
    case_id: CaseId
    decision_question: NonEmptyStr
    keywords: list[NonEmptyStr] = Field(default_factory=list)
    domains: list[NonEmptyStr] = Field(default_factory=list)
    recommended_action: NonEmptyStr
    alternatives_considered: list[NonEmptyStr] = Field(default_factory=list)
    recommendation_confidence: float = Field(ge=0.0, le=1.0)
    evidence_confidence: float = Field(ge=0.0, le=1.0)
    headline_outcome_name: NonEmptyStr | None = None
    headline_outcome_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    completed_at: datetime
    outcome: OutcomeRecord | None = None


class SourceReputation(ArtifactModel):
    domain: NonEmptyStr
    times_cited: int = Field(ge=0)
    times_contradicted: int = Field(ge=0)
    mean_authority: float = Field(ge=0.0, le=1.0)
    source_types: list[SourceType] = Field(default_factory=list)
    case_ids: list[CaseId] = Field(default_factory=list)


class RecurringAssumption(ArtifactModel):
    normalized_claim: NonEmptyStr
    example_claim: NonEmptyStr
    occurrences: int = Field(ge=1)
    max_materiality: Level
    case_ids: list[CaseId] = Field(default_factory=list)


class PriorEvidenceEntry(ArtifactModel):
    claim: NonEmptyStr
    source_title: NonEmptyStr
    publisher: NonEmptyStr
    source_url: NonEmptyStr
    source_type: SourceType
    publication_date: date
    topics: list[NonEmptyStr] = Field(default_factory=list)
    from_case_id: CaseId
    authority_score: float = Field(ge=0.0, le=1.0)


class CalibrationSummary(ArtifactModel):
    sample_size: int = Field(ge=0)
    brier_score: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_forecast: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_realized: float | None = Field(default=None, ge=0.0, le=1.0)
    interpretation: NonEmptyStr


class CaseMemoryDigest(ArtifactModel):
    """The compact cross-case brief projected into a live case.

    Everything here is prior context, not evidence. Nothing in this digest may be
    cited; it exists to stop the system from starting every case with an empty head.
    """

    generated_at: datetime
    prior_cases: list[PriorCaseEntry] = Field(default_factory=list)
    source_reputations: list[SourceReputation] = Field(default_factory=list)
    recurring_assumptions: list[RecurringAssumption] = Field(default_factory=list)
    calibration: CalibrationSummary | None = None
    usage_note: NonEmptyStr


class PriorEvidenceDigest(ArtifactModel):
    """Standing-research-program output: evidence carried over from earlier cases.

    Records here are stale by construction and must be re-verified before citation;
    they are never written to the blackboard by the orchestrator.
    """

    generated_at: datetime
    entries: list[PriorEvidenceEntry] = Field(default_factory=list)
    staleness_warning: NonEmptyStr
