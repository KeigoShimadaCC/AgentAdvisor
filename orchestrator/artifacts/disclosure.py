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


# SPEC-056 follow-up: these values reach users, so they need words.
#
# The case surface, the delivery sheet and the exported `final_recommendation.md`
# all rendered the raw enum for the whole of phase 9 — "Stop reasons:
# no_critical_evidence_gaps_remain, recommendation_stable_across_plausible_...".
# They live beside the enum so that adding a reason without deciding what it
# says to a human is a visible omission rather than a silent leak.
#
# Deliberately *not* applied to `projection.py`, which feeds agents rather than
# people: what an agent reads is pipeline input, not presentation.
_STOP_REASON_PHRASES: dict[StopReason, str] = {
    StopReason.NO_CRITICAL_EVIDENCE_GAPS_REMAIN: "no critical evidence gaps remained",
    StopReason.RECOMMENDATION_STABLE_ACROSS_SENSITIVITY_RANGES: (
        "the recommendation held across the plausible range of assumptions"
    ),
    StopReason.NO_UNRESOLVED_OBJECTION_LIKELY_TO_CHANGE_DECISION: (
        "no open objection looked likely to change the decision"
    ),
    StopReason.EXPECTED_VALUE_OF_MORE_RESEARCH_LOW: (
        "further research looked unlikely to change the answer"
    ),
    StopReason.INVESTIGATION_BUDGET_EXHAUSTED: "the investigation budget ran out",
    StopReason.USER_DEADLINE_OR_DEPTH_LIMIT_REACHED: "your depth limit was reached",
}

_BUDGET_KIND_PHRASES: dict[str, str] = {
    "agent_invocations": "agent invocations",
    "concurrent_workers": "concurrent workers",
    "repair_cycles": "repair cycles",
    "research_tasks": "research tasks",
    "high_tier_calls": "premium-model calls",
    "wall_clock_s": "wall-clock time",
}


def stop_reason_phrase(reason: StopReason | str) -> str:
    """A human phrase for a stop reason, degrading to readable text."""
    try:
        return _STOP_REASON_PHRASES[StopReason(reason)]
    except (ValueError, KeyError):
        return str(reason).replace("_", " ")


def budget_kind_phrase(kind: str) -> str:
    """A human phrase for an exhausted budget dimension."""
    return _BUDGET_KIND_PHRASES.get(kind, kind.replace("_", " "))
