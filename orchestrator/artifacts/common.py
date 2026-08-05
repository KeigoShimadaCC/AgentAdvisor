from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

SchemaVersion = Annotated[int, Field(ge=1)]
NonEmptyStr = Annotated[str, Field(min_length=1)]

EvidenceId = Annotated[str, Field(pattern=r"^E-\d+$")]
AssumptionId = Annotated[str, Field(pattern=r"^A-\d+$")]
TaskId = Annotated[str, Field(pattern=r"^T-\d+$")]
ObjectionId = Annotated[str, Field(pattern=r"^O-\d+$")]
ActionId = Annotated[str, Field(pattern=r"^N-\d+$")]
IssueNodeId = Annotated[str, Field(pattern=r"^Q-\d+(?:\.\d+)*$")]
CaseId = Annotated[str, Field(pattern=r"^case-\d+[-a-z0-9-]*$")]


class ArtifactModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: SchemaVersion = 1


class Level(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskTolerance(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class Reversibility(StrEnum):
    FULLY_REVERSIBLE = "fully_reversible"
    PARTIALLY_REVERSIBLE = "partially_reversible"
    IRREVERSIBLE = "irreversible"


class Depth(StrEnum):
    LIGHT = "light"
    STANDARD = "standard"
    DEEP = "deep"


class AssumptionType(StrEnum):
    FORECAST = "forecast"
    STRUCTURAL = "structural"
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    REGULATORY = "regulatory"
    BEHAVIORAL = "behavioral"


class AssumptionStatus(StrEnum):
    UNRESOLVED = "unresolved"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    RETIRED = "retired"


class ObjectionResolutionStatus(StrEnum):
    OPEN = "open"
    PARTIALLY_RESOLVED = "partially_resolved"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class TaskRole(StrEnum):
    INTAKE = "intake"
    PLANNER = "planner"
    DIRECTOR = "director"
    STRUCTURER = "structurer"
    CHALLENGER = "challenger"
    PREMORTEM = "premortem"
    AUDITOR = "auditor"
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    ASSUMPTION_ANALYST = "assumption_analyst"
    ACH_ANALYST = "ach"
    SYNTHESIZER = "synthesizer"
    REVIEWER = "reviewer"
    SPECIALIST = "specialist"


class TaskStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class PriorityLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SourceType(StrEnum):
    REGULATORY_FILING = "regulatory_filing"
    OFFICIAL_STATISTIC = "official_statistic"
    LAW_OR_STANDARD = "law_or_standard"
    ORIGINAL_RESEARCH = "original_research"
    REPUTABLE_SECONDARY = "reputable_secondary"
    SPECIALIST_REPORTING = "specialist_reporting"
    OTHER = "other"


class ProbabilityMethod(StrEnum):
    REFERENCE_CLASS = "reference_class"
    SCENARIO_MODEL = "scenario_model"
    STRUCTURED_SUBJECTIVE = "structured_subjective"
