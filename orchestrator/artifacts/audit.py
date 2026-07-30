from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from orchestrator.artifacts.common import ArtifactModel, NonEmptyStr


class AuditUsage(ArtifactModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class AuditEvent(ArtifactModel):
    ts: datetime
    actor: NonEmptyStr
    event_type: NonEmptyStr
    payload: dict[str, Any] = Field(default_factory=dict)
    model: str | None = None
    cli_version: str | None = None
    usage: AuditUsage | None = None
    duration_ms: int | None = Field(default=None, ge=0)
