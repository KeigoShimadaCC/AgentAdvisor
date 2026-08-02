from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from orchestrator.artifacts.common import (
    ArtifactModel,
    AssumptionId,
    EvidenceId,
    NonEmptyStr,
    ObjectionId,
)


class ThesisTrigger(StrEnum):
    PROVISIONAL = "provisional"
    RECONCILIATION = "reconciliation"
    INVESTIGATION_WAVE = "investigation_wave"
    PRELIMINARY = "preliminary"
    REPAIR = "repair"


class ThesisRevision(ArtifactModel):
    """One entry in the append-only thesis ledger.

    The ledger makes belief movement inspectable: what the system thought, when it
    changed its mind, and what changed it.
    """

    revision: int = Field(ge=1)
    trigger: ThesisTrigger
    preferred_alternative: NonEmptyStr
    previous_alternative: NonEmptyStr | None = None
    changed: bool
    rationale_digest: list[NonEmptyStr] = Field(default_factory=list)
    changed_because_evidence_ids: list[EvidenceId] = Field(default_factory=list)
    changed_because_assumption_ids: list[AssumptionId] = Field(default_factory=list)
    changed_because_objection_ids: list[ObjectionId] = Field(default_factory=list)
    recommendation_confidence: float = Field(ge=0.0, le=1.0)
    evidence_confidence: float = Field(ge=0.0, le=1.0)
    recorded_at: datetime
