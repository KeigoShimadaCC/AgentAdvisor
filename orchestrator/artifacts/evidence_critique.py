from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from orchestrator.artifacts.common import (
    ArtifactModel,
    EvidenceId,
    NonEmptyStr,
    SourceType,
)


class SourceTier(StrEnum):
    """Authority tier of an evidence source, ordered strongest to weakest."""

    PRIMARY = "primary"
    OFFICIAL = "official"
    REPUTABLE = "reputable"
    WEAK = "weak"


class EvidenceFlag(StrEnum):
    SINGLE_SOURCE_CLUSTER = "single_source_cluster"
    STALE = "stale"
    LOW_DIRECTNESS = "low_directness"
    LOW_RELIABILITY = "low_reliability"
    MISSING_LIMITATIONS = "missing_limitations"
    WEAK_SOURCE_TIER = "weak_source_tier"


SOURCE_TIER_BY_TYPE: dict[SourceType, SourceTier] = {
    SourceType.REGULATORY_FILING: SourceTier.PRIMARY,
    SourceType.OFFICIAL_STATISTIC: SourceTier.PRIMARY,
    SourceType.LAW_OR_STANDARD: SourceTier.OFFICIAL,
    SourceType.ORIGINAL_RESEARCH: SourceTier.OFFICIAL,
    SourceType.REPUTABLE_SECONDARY: SourceTier.REPUTABLE,
    SourceType.SPECIALIST_REPORTING: SourceTier.REPUTABLE,
    SourceType.OTHER: SourceTier.WEAK,
}

SOURCE_TIER_WEIGHT: dict[SourceTier, float] = {
    SourceTier.PRIMARY: 1.0,
    SourceTier.OFFICIAL: 0.8,
    SourceTier.REPUTABLE: 0.55,
    SourceTier.WEAK: 0.25,
}


class EvidenceAuthorityScore(ArtifactModel):
    evidence_id: EvidenceId
    source_tier: SourceTier
    authority_score: float = Field(ge=0.0, le=1.0)
    age_days: int = Field(ge=0)
    independence_group: NonEmptyStr
    flags: list[EvidenceFlag] = Field(default_factory=list)


class IndependenceCluster(ArtifactModel):
    independence_group: NonEmptyStr
    evidence_ids: list[EvidenceId] = Field(min_length=1)
    share_of_corpus: float = Field(ge=0.0, le=1.0)


class EvidenceCritique(ArtifactModel):
    """Deterministic quality assessment of the whole evidence corpus.

    Computed by ``orchestrator.evidence_critic`` from the blackboard, never asserted
    by an agent, so it cannot be talked up.
    """

    evidence_count: int = Field(ge=0)
    scored: list[EvidenceAuthorityScore] = Field(default_factory=list)
    clusters: list[IndependenceCluster] = Field(default_factory=list)
    corpus_authority_mean: float = Field(ge=0.0, le=1.0)
    primary_source_share: float = Field(ge=0.0, le=1.0)
    max_cluster_share: float = Field(ge=0.0, le=1.0)
    independent_group_count: int = Field(ge=0)
    weakest_evidence_ids: list[EvidenceId] = Field(default_factory=list)
    gaps: list[NonEmptyStr] = Field(default_factory=list)
