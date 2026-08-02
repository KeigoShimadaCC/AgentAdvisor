from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from orchestrator.artifacts.common import ArtifactModel, NonEmptyStr


class GateSeverity(StrEnum):
    """Ordered: a gate's outcome is the maximum severity among its findings."""

    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


_SEVERITY_ORDER: dict[GateSeverity, int] = {
    GateSeverity.PASS: 0,
    GateSeverity.WARN: 1,
    GateSeverity.BLOCK: 2,
}


def max_severity(severities: list[GateSeverity]) -> GateSeverity:
    if not severities:
        return GateSeverity.PASS
    return max(severities, key=lambda severity: _SEVERITY_ORDER[severity])


class GateFinding(ArtifactModel):
    check_id: NonEmptyStr
    severity: GateSeverity
    message: NonEmptyStr
    target_ids: list[NonEmptyStr] = Field(default_factory=list)


class GateReport(ArtifactModel):
    """Result of the deterministic process gate run at a stage boundary."""

    stage: NonEmptyStr
    outcome: GateSeverity
    findings: list[GateFinding] = Field(default_factory=list)
    cancelled_task_ids: list[NonEmptyStr] = Field(default_factory=list)
    checked_at: datetime

    @property
    def passed(self) -> bool:
        return self.outcome is not GateSeverity.BLOCK

    @property
    def blocking(self) -> list[GateFinding]:
        return [finding for finding in self.findings if finding.severity is GateSeverity.BLOCK]
