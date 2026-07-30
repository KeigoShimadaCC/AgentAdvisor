from __future__ import annotations

from datetime import date

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
