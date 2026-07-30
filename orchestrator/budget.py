from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping
from datetime import datetime
from enum import StrEnum
from threading import Lock
from typing import Literal

from pydantic import BaseModel, Field

from orchestrator.artifacts.disclosure import DisclosureRecord, StopReason
from orchestrator.state_machine import CaseState


class BudgetConfig(BaseModel):
    max_agent_invocations: int = Field(default=40, ge=1)
    max_concurrent_workers: int = Field(default=3, ge=1)
    max_repair_cycles: int = Field(default=2, ge=0)
    max_research_tasks: int = Field(default=15, ge=0)
    max_high_tier_calls: int = Field(default=6, ge=0)
    max_wall_clock_s: int = Field(default=7200, ge=1)


class BudgetKind(StrEnum):
    AGENT_INVOCATIONS = "agent_invocations"
    CONCURRENT_WORKERS = "concurrent_workers"
    REPAIR_CYCLES = "repair_cycles"
    RESEARCH_TASKS = "research_tasks"
    HIGH_TIER_CALLS = "high_tier_calls"
    WALL_CLOCK_S = "wall_clock_s"


class ModelTier(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_KIND_TO_CAP_ATTR: dict[BudgetKind, str] = {
    BudgetKind.AGENT_INVOCATIONS: "max_agent_invocations",
    BudgetKind.CONCURRENT_WORKERS: "max_concurrent_workers",
    BudgetKind.REPAIR_CYCLES: "max_repair_cycles",
    BudgetKind.RESEARCH_TASKS: "max_research_tasks",
    BudgetKind.HIGH_TIER_CALLS: "max_high_tier_calls",
    BudgetKind.WALL_CLOCK_S: "max_wall_clock_s",
}


class BudgetLedger:
    def __init__(
        self,
        state: CaseState,
        config: BudgetConfig,
        model_tier_map: Mapping[str, str | ModelTier],
    ) -> None:
        self._counters = state.budget_counters
        self._config = config
        self._model_tier_map = model_tier_map
        self._lock = Lock()

    def try_consume(self, kind: str, model: str | None = None) -> bool:
        try:
            budget_kind = BudgetKind(kind)
        except ValueError:
            return False

        counters_to_increment = [budget_kind]
        if (
            budget_kind is BudgetKind.AGENT_INVOCATIONS
            and model is not None
            and self._is_high_tier_model(model)
        ):
            counters_to_increment.append(BudgetKind.HIGH_TIER_CALLS)

        with self._lock:
            if not self._can_consume_all(self._counters, counters_to_increment):
                return False
            for counter_kind in counters_to_increment:
                counter_name = counter_kind.value
                self._counters[counter_name] = self._counters.get(counter_name, 0) + 1
            return True

    def _can_consume_all(
        self,
        counters: MutableMapping[str, int],
        counter_kinds: list[BudgetKind],
    ) -> bool:
        for counter_kind in counter_kinds:
            cap_attr = _KIND_TO_CAP_ATTR[counter_kind]
            cap = getattr(self._config, cap_attr)
            count = counters.get(counter_kind.value, 0)
            if count >= cap:
                return False
        return True

    def _is_high_tier_model(self, model: str) -> bool:
        tier = self._model_tier_map.get(model)
        if tier is None:
            return False
        if isinstance(tier, ModelTier):
            return tier is ModelTier.HIGH
        return tier == ModelTier.HIGH.value


class StopEvaluatorInputs(BaseModel):
    open_critical_evidence_gaps: bool
    unresolved_material_objections: bool
    recommendation_stable: bool
    expected_value_of_more_research_low: bool
    remaining_budget: Mapping[str, int] = Field(default_factory=dict)
    deadline: datetime | None = None
    depth_limit_reached: bool = False


class StopDecision(BaseModel):
    action: Literal["continue", "stop"]
    reasons: tuple[StopReason, ...] = ()
    disclosure: DisclosureRecord | None = None


class StopEvaluator:
    def __init__(self, clock: Callable[[], datetime]) -> None:
        self._clock = clock

    def evaluate(self, inputs: StopEvaluatorInputs) -> StopDecision:
        reasons: list[StopReason] = []

        if not inputs.open_critical_evidence_gaps:
            reasons.append(StopReason.NO_CRITICAL_EVIDENCE_GAPS_REMAIN)
        if inputs.recommendation_stable:
            reasons.append(StopReason.RECOMMENDATION_STABLE_ACROSS_SENSITIVITY_RANGES)
        if not inputs.unresolved_material_objections:
            reasons.append(StopReason.NO_UNRESOLVED_OBJECTION_LIKELY_TO_CHANGE_DECISION)
        if inputs.expected_value_of_more_research_low:
            reasons.append(StopReason.EXPECTED_VALUE_OF_MORE_RESEARCH_LOW)

        exhausted_dimensions: list[str] = sorted(
            dimension for dimension, remaining in inputs.remaining_budget.items() if remaining <= 0
        )
        if exhausted_dimensions:
            reasons.append(StopReason.INVESTIGATION_BUDGET_EXHAUSTED)

        deadline_reached = inputs.deadline is not None and self._clock() >= inputs.deadline
        if deadline_reached or inputs.depth_limit_reached:
            reasons.append(StopReason.USER_DEADLINE_OR_DEPTH_LIMIT_REACHED)
            if deadline_reached:
                exhausted_dimensions.append("deadline")
            if inputs.depth_limit_reached:
                exhausted_dimensions.append("depth_limit")

        if not reasons:
            return StopDecision(action="continue")

        disclosure: DisclosureRecord | None = None
        if (
            StopReason.INVESTIGATION_BUDGET_EXHAUSTED in reasons
            or StopReason.USER_DEADLINE_OR_DEPTH_LIMIT_REACHED in reasons
        ):
            disclosure = DisclosureRecord(
                stop_reasons=tuple(reasons),
                exhausted_dimensions=tuple(dict.fromkeys(exhausted_dimensions)),
            )

        return StopDecision(action="stop", reasons=tuple(reasons), disclosure=disclosure)
