from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from orchestrator.artifacts.common import ArtifactModel


class StopReason(StrEnum):
    NO_CRITICAL_EVIDENCE_GAPS_REMAIN = "no_critical_evidence_gaps_remain"
    RECOMMENDATION_STABLE_ACROSS_SENSITIVITY_RANGES = (
        "recommendation_stable_across_plausible_sensitivity_ranges"
    )
    NO_UNRESOLVED_OBJECTION_LIKELY_TO_CHANGE_DECISION = (
        "no_unresolved_objection_likely_to_change_decision"
    )
    EXPECTED_VALUE_OF_MORE_RESEARCH_LOW = "expected_value_of_more_research_low"
    INVESTIGATION_BUDGET_EXHAUSTED = "investigation_budget_exhausted"
    USER_DEADLINE_OR_DEPTH_LIMIT_REACHED = "user_deadline_or_depth_limit_reached"


class DisclosureRecord(ArtifactModel):
    stop_reasons: tuple[StopReason, ...]
    exhausted_dimensions: tuple[str, ...] = Field(min_length=1)
