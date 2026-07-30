from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import Field

from orchestrator.artifacts.common import ArtifactModel, Level, NonEmptyStr

ArtifactReferenceId = Annotated[
    str,
    Field(pattern=r"^(?:case-\d+[-a-z0-9-]*|[EATO]-\d+)$"),
]


class AuditFindingType(StrEnum):
    IRRELEVANT_TASK = "irrelevant_task"
    DUPLICATED_WORK = "duplicated_work"
    MANDATE_VIOLATION = "mandate_violation"
    UNSUPPORTED_CLAIM = "unsupported_claim"


class AuditIssue(ArtifactModel):
    finding_type: AuditFindingType
    target_ids: list[ArtifactReferenceId] = Field(min_length=1)
    severity: Level
    reason: NonEmptyStr
    high_stakes_escalation: bool = False


class AuditStopInput(ArtifactModel):
    open_critical_evidence_gaps: bool
    unresolved_material_objections: bool
    recommendation_stable: bool
    expected_value_of_more_research_low: bool
    remaining_budget: dict[str, int] = Field(default_factory=dict)
    deadline: datetime | None = None
    depth_limit_reached: bool = False
    open_critical_evidence_gaps_reason: NonEmptyStr
    unresolved_material_objections_reason: NonEmptyStr
    recommendation_stable_reason: NonEmptyStr
    expected_value_of_more_research_low_reason: NonEmptyStr


class AuditFinding(ArtifactModel):
    findings: list[AuditIssue] = Field(default_factory=list)
    stop_input: AuditStopInput
