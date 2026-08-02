from __future__ import annotations

from collections import Counter

from pydantic import Field, model_validator

from orchestrator.artifacts.common import (
    ArtifactModel,
    AssumptionId,
    AssumptionStatus,
    AssumptionType,
    EvidenceId,
    Level,
    NonEmptyStr,
)
from orchestrator.artifacts.probability import ProbabilityEstimate


class AssumptionRecord(ArtifactModel):
    assumption_id: AssumptionId
    claim: NonEmptyStr
    type: AssumptionType
    estimate: ProbabilityEstimate
    confidence: Level
    materiality: Level
    evidence_for: list[EvidenceId] = Field(default_factory=list)
    evidence_against: list[EvidenceId] = Field(default_factory=list)
    status: AssumptionStatus


MAX_ASSUMPTION_RECORDS_PER_BATCH = 10


class AssumptionBatch(ArtifactModel):
    """One assumption-extraction pass over the whole blackboard.

    Mirrors ``EvidenceBatch``: a transport envelope the orchestrator unpacks into
    canonical ``A-`` records. Finding nothing is an explicit outcome, never silence.
    """

    source_scope: NonEmptyStr
    records: list[AssumptionRecord] = Field(default_factory=list)
    no_assumptions_found: bool = False
    extraction_notes: NonEmptyStr

    @model_validator(mode="after")
    def validate_cap_and_empty_outcome(self) -> AssumptionBatch:
        if len(self.records) > MAX_ASSUMPTION_RECORDS_PER_BATCH:
            raise ValueError(
                f"records exceeds the {MAX_ASSUMPTION_RECORDS_PER_BATCH} record cap "
                "for a single assumption-extraction invocation."
            )
        if self.no_assumptions_found and self.records:
            raise ValueError("no_assumptions_found cannot be true while records are present.")
        if not self.no_assumptions_found and not self.records:
            raise ValueError(
                "An empty batch must set no_assumptions_found=true so that finding nothing is "
                "an explicit, auditable outcome rather than a silent failure."
            )
        duplicate_ids = sorted(
            assumption_id
            for assumption_id, count in Counter(
                record.assumption_id for record in self.records
            ).items()
            if count > 1
        )
        if duplicate_ids:
            raise ValueError(f"records contains duplicate assumption_ids: {duplicate_ids}")
        return self
