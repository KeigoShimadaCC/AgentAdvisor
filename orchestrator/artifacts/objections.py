from __future__ import annotations

from collections import Counter
from enum import StrEnum

from pydantic import Field, model_validator

from orchestrator.artifacts.common import (
    ArtifactModel,
    AssumptionId,
    EvidenceId,
    Level,
    NonEmptyStr,
    ObjectionId,
    ObjectionResolutionStatus,
    TaskId,
)


class ObjectionRecord(ArtifactModel):
    objection_id: ObjectionId
    target_section: NonEmptyStr
    claim: NonEmptyStr
    materiality: Level
    reasoning: NonEmptyStr
    reversal_evidence: NonEmptyStr
    referenced_evidence_ids: list[EvidenceId] = Field(default_factory=list)
    referenced_assumption_ids: list[AssumptionId] = Field(default_factory=list)
    resolution_status: ObjectionResolutionStatus
    commissioned_tasks: list[TaskId] = Field(default_factory=list)


class ObjectionMode(StrEnum):
    STANDARD = "standard"
    FINAL_PASS = "final_pass"


class ObjectionBatch(ArtifactModel):
    mode: ObjectionMode
    objections: list[ObjectionRecord] = Field(default_factory=list)
    no_objections_justification: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_caps_and_empty_batches(self) -> ObjectionBatch:
        cap = 2 if self.mode is ObjectionMode.FINAL_PASS else 5
        if len(self.objections) > cap:
            raise ValueError(f"objections exceeds {cap} cap for mode '{self.mode.value}'.")

        if not self.objections and self.no_objections_justification is None:
            raise ValueError(
                "An empty objections list requires no_objections_justification so that finding no "
                "material objections is an explicit, auditable claim."
            )
        if self.objections and self.no_objections_justification is not None:
            raise ValueError(
                "no_objections_justification must be omitted when objections are present."
            )

        id_counts = Counter(objection.objection_id for objection in self.objections)
        duplicate_ids = sorted(
            objection_id for objection_id, count in id_counts.items() if count > 1
        )
        if duplicate_ids:
            raise ValueError(f"objections contains duplicate objection_ids: {duplicate_ids}")
        return self
