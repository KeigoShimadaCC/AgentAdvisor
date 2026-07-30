from __future__ import annotations

from datetime import date

from pydantic import Field, model_validator

from orchestrator.artifacts.common import ArtifactModel, EvidenceId, Level, NonEmptyStr, SourceType


class EvidenceRecord(ArtifactModel):
    evidence_id: EvidenceId
    claim: NonEmptyStr
    source_title: NonEmptyStr
    publisher: NonEmptyStr
    source_url: NonEmptyStr
    source_type: SourceType
    publication_date: date
    retrieval_date: date
    excerpt: NonEmptyStr
    reliability: Level
    directness: Level
    independence_group: NonEmptyStr
    limitations: list[NonEmptyStr]
    retrieved_by: NonEmptyStr


MAX_EVIDENCE_RECORDS_PER_BATCH = 8


class EvidenceBatch(ArtifactModel):
    """One researcher invocation's full yield for a single assigned question."""

    task_id: NonEmptyStr
    question: NonEmptyStr
    records: list[EvidenceRecord] = Field(default_factory=list)
    no_evidence_found: bool = False
    search_notes: NonEmptyStr

    @model_validator(mode="after")
    def validate_cap_and_empty_outcome(self) -> EvidenceBatch:
        if len(self.records) > MAX_EVIDENCE_RECORDS_PER_BATCH:
            raise ValueError(
                f"records exceeds the {MAX_EVIDENCE_RECORDS_PER_BATCH} record cap "
                "for a single researcher invocation."
            )
        if self.no_evidence_found and self.records:
            raise ValueError("no_evidence_found cannot be true while records are present.")
        if not self.no_evidence_found and not self.records:
            raise ValueError(
                "An empty batch must set no_evidence_found=true so that finding nothing is "
                "an explicit, auditable outcome rather than a silent failure."
            )
        duplicate_ids = {
            evidence_id
            for evidence_id in (record.evidence_id for record in self.records)
            if [r.evidence_id for r in self.records].count(evidence_id) > 1
        }
        if duplicate_ids:
            raise ValueError(f"records contains duplicate evidence_ids: {sorted(duplicate_ids)}")
        return self
