from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import Field

from orchestrator.artifacts import CaseId, TaskRole
from orchestrator.artifacts.common import ArtifactModel
from orchestrator.artifacts.yaml_io import dump_model_to_yaml_text
from orchestrator.case_store import Case, atomic_write_text


class CaseStage(Enum):
    INTAKE = "intake"
    FRAMING = "framing"
    AWAITING_FRAMING_APPROVAL = "awaiting_framing_approval"
    PROVISIONAL_THESIS = "provisional_thesis"
    PLANNING = "planning"
    INVESTIGATION = "investigation"
    PRELIMINARY_RECOMMENDATION = "preliminary_recommendation"
    CHALLENGE = "challenge"
    REPAIR = "repair"
    STOP_DECISION = "stop_decision"
    SYNTHESIS = "synthesis"
    REVIEW = "review"
    AWAITING_FINAL_APPROVAL = "awaiting_final_approval"
    DONE = "done"
    FAILED = "failed"


class CaseState(ArtifactModel):
    case_id: CaseId
    stage: CaseStage = CaseStage.INTAKE
    repair_cycle: int = Field(default=0, ge=0)
    budget_counters: dict[str, int] = Field(default_factory=dict)
    framing_approved: bool = False
    final_approved: bool = False
    failure_cause: str | None = None
    created_at: datetime
    updated_at: datetime


class StepOutcome(Enum):
    ADVANCE = "advance"
    NEEDS_REPAIR = "needs_repair"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class StepPlan:
    stage: CaseStage
    handler_name: str | None
    roles: tuple[TaskRole, ...]
    approval_gate: bool = False


@dataclass(frozen=True, slots=True)
class StepResult:
    outcome: StepOutcome
    error_cause: str | None = None

    @classmethod
    def ok(cls, outcome: StepOutcome = StepOutcome.ADVANCE) -> StepResult:
        return cls(outcome=outcome)

    @classmethod
    def error(cls, cause: str) -> StepResult:
        return cls(outcome=StepOutcome.ERROR, error_cause=cause)


class IllegalTransition(RuntimeError):
    pass


StepHandler = Callable[[Case, CaseState, StepPlan], StepResult]

ACTIVE_STAGES: tuple[CaseStage, ...] = (
    CaseStage.INTAKE,
    CaseStage.FRAMING,
    CaseStage.AWAITING_FRAMING_APPROVAL,
    CaseStage.PROVISIONAL_THESIS,
    CaseStage.PLANNING,
    CaseStage.INVESTIGATION,
    CaseStage.PRELIMINARY_RECOMMENDATION,
    CaseStage.CHALLENGE,
    CaseStage.REPAIR,
    CaseStage.STOP_DECISION,
    CaseStage.SYNTHESIS,
    CaseStage.REVIEW,
    CaseStage.AWAITING_FINAL_APPROVAL,
)

ALLOWED_TRANSITIONS: dict[CaseStage, frozenset[CaseStage]] = {
    CaseStage.INTAKE: frozenset({CaseStage.FRAMING, CaseStage.FAILED}),
    CaseStage.FRAMING: frozenset({CaseStage.AWAITING_FRAMING_APPROVAL, CaseStage.FAILED}),
    CaseStage.AWAITING_FRAMING_APPROVAL: frozenset(
        {CaseStage.PROVISIONAL_THESIS, CaseStage.FAILED}
    ),
    CaseStage.PROVISIONAL_THESIS: frozenset({CaseStage.PLANNING, CaseStage.FAILED}),
    CaseStage.PLANNING: frozenset({CaseStage.INVESTIGATION, CaseStage.FAILED}),
    CaseStage.INVESTIGATION: frozenset({CaseStage.PRELIMINARY_RECOMMENDATION, CaseStage.FAILED}),
    CaseStage.PRELIMINARY_RECOMMENDATION: frozenset({CaseStage.CHALLENGE, CaseStage.FAILED}),
    CaseStage.CHALLENGE: frozenset({CaseStage.STOP_DECISION, CaseStage.FAILED}),
    CaseStage.REPAIR: frozenset({CaseStage.CHALLENGE, CaseStage.FAILED}),
    CaseStage.STOP_DECISION: frozenset({CaseStage.REPAIR, CaseStage.SYNTHESIS, CaseStage.FAILED}),
    CaseStage.SYNTHESIS: frozenset({CaseStage.REVIEW, CaseStage.FAILED}),
    CaseStage.REVIEW: frozenset({CaseStage.AWAITING_FINAL_APPROVAL, CaseStage.FAILED}),
    CaseStage.AWAITING_FINAL_APPROVAL: frozenset({CaseStage.DONE, CaseStage.FAILED}),
    CaseStage.DONE: frozenset(),
    CaseStage.FAILED: frozenset(),
}

_FLOW_PLANS: dict[CaseStage, StepPlan] = {
    CaseStage.INTAKE: StepPlan(CaseStage.INTAKE, "intake", (TaskRole.INTAKE,)),
    CaseStage.FRAMING: StepPlan(CaseStage.FRAMING, "framing", (TaskRole.DIRECTOR,)),
    CaseStage.AWAITING_FRAMING_APPROVAL: StepPlan(
        CaseStage.AWAITING_FRAMING_APPROVAL, None, tuple(), approval_gate=True
    ),
    CaseStage.PROVISIONAL_THESIS: StepPlan(
        CaseStage.PROVISIONAL_THESIS, "provisional_thesis", (TaskRole.DIRECTOR,)
    ),
    CaseStage.PLANNING: StepPlan(CaseStage.PLANNING, "planning", (TaskRole.PLANNER,)),
    CaseStage.INVESTIGATION: StepPlan(
        CaseStage.INVESTIGATION, "investigation", (TaskRole.RESEARCHER, TaskRole.ANALYST)
    ),
    CaseStage.PRELIMINARY_RECOMMENDATION: StepPlan(
        CaseStage.PRELIMINARY_RECOMMENDATION, "preliminary_recommendation", (TaskRole.DIRECTOR,)
    ),
    CaseStage.CHALLENGE: StepPlan(
        CaseStage.CHALLENGE, "challenge", (TaskRole.CHALLENGER, TaskRole.AUDITOR)
    ),
    CaseStage.REPAIR: StepPlan(CaseStage.REPAIR, "repair", (TaskRole.PLANNER,)),
    # No roles: the stop decision is a deterministic StopEvaluator (SPEC-008), never an agent.
    CaseStage.STOP_DECISION: StepPlan(CaseStage.STOP_DECISION, "stop_decision", tuple()),
    CaseStage.SYNTHESIS: StepPlan(CaseStage.SYNTHESIS, "synthesis", (TaskRole.SYNTHESIZER,)),
    CaseStage.REVIEW: StepPlan(CaseStage.REVIEW, "review", (TaskRole.REVIEWER,)),
    CaseStage.AWAITING_FINAL_APPROVAL: StepPlan(
        CaseStage.AWAITING_FINAL_APPROVAL, None, tuple(), approval_gate=True
    ),
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _state_path(case: Case) -> Path:
    return case.root / "state.yaml"


def _initial_state(case: Case) -> CaseState:
    now = _utc_now()
    return CaseState(case_id=case.root.name, created_at=now, updated_at=now)


def load_case_state(case: Case) -> CaseState:
    path = _state_path(case)
    if not path.exists():
        return _initial_state(case)

    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict) or len(loaded) == 0:
        return _initial_state(case)
    return CaseState.model_validate(loaded)


def save_case_state(case: Case, state: CaseState) -> None:
    atomic_write_text(_state_path(case), dump_model_to_yaml_text(state))


def _next_or_raise(from_stage: CaseStage, to_stage: CaseStage) -> None:
    if to_stage not in ALLOWED_TRANSITIONS[from_stage]:
        raise IllegalTransition(f"Illegal transition: {from_stage.name} -> {to_stage.name}")


def route(state: CaseState) -> StepPlan:
    if state.stage in (CaseStage.DONE, CaseStage.FAILED):
        raise IllegalTransition(f"Illegal transition: {state.stage.name} -> <routed>")
    return _FLOW_PLANS[state.stage]


def _resolve_next_stage(
    state: CaseState, result: StepResult, max_repair_cycles: int
) -> tuple[CaseStage, int]:
    if result.outcome is StepOutcome.ERROR:
        return CaseStage.FAILED, state.repair_cycle

    if state.stage is CaseStage.STOP_DECISION:
        if result.outcome is StepOutcome.NEEDS_REPAIR and state.repair_cycle < max_repair_cycles:
            return CaseStage.REPAIR, state.repair_cycle + 1
        return CaseStage.SYNTHESIS, state.repair_cycle

    if state.stage is CaseStage.AWAITING_FRAMING_APPROVAL:
        return CaseStage.PROVISIONAL_THESIS, state.repair_cycle

    if state.stage is CaseStage.AWAITING_FINAL_APPROVAL:
        return CaseStage.DONE, state.repair_cycle

    next_by_stage: dict[CaseStage, CaseStage] = {
        CaseStage.INTAKE: CaseStage.FRAMING,
        CaseStage.FRAMING: CaseStage.AWAITING_FRAMING_APPROVAL,
        CaseStage.PROVISIONAL_THESIS: CaseStage.PLANNING,
        CaseStage.PLANNING: CaseStage.INVESTIGATION,
        CaseStage.INVESTIGATION: CaseStage.PRELIMINARY_RECOMMENDATION,
        CaseStage.PRELIMINARY_RECOMMENDATION: CaseStage.CHALLENGE,
        CaseStage.CHALLENGE: CaseStage.STOP_DECISION,
        CaseStage.REPAIR: CaseStage.CHALLENGE,
        CaseStage.SYNTHESIS: CaseStage.REVIEW,
        CaseStage.REVIEW: CaseStage.AWAITING_FINAL_APPROVAL,
    }
    if state.stage not in next_by_stage:
        raise IllegalTransition(f"Illegal transition: {state.stage.name} -> <unresolved>")
    return next_by_stage[state.stage], state.repair_cycle


def reduce(state: CaseState, result: StepResult, max_repair_cycles: int = 2) -> CaseState:
    if state.stage in (CaseStage.DONE, CaseStage.FAILED):
        raise IllegalTransition(f"Illegal transition: {state.stage.name} -> <reduced>")

    next_stage, next_repair_cycle = _resolve_next_stage(state, result, max_repair_cycles)
    _next_or_raise(state.stage, next_stage)

    failure_cause = result.error_cause if next_stage is CaseStage.FAILED else None
    return state.model_copy(
        update={
            "stage": next_stage,
            "repair_cycle": next_repair_cycle,
            "failure_cause": failure_cause,
        }
    )


def _is_approval_granted(state: CaseState) -> bool:
    if state.stage is CaseStage.AWAITING_FRAMING_APPROVAL:
        return state.framing_approved
    if state.stage is CaseStage.AWAITING_FINAL_APPROVAL:
        return state.final_approved
    return False


def _checkpoint_state(case: Case, state: CaseState) -> None:
    checkpointed = state.model_copy(update={"updated_at": _utc_now()})
    save_case_state(case, checkpointed)


def run_case(
    case: Case,
    handlers: Mapping[str, StepHandler],
    until: CaseStage | None = None,
    *,
    max_repair_cycles: int = 2,
) -> CaseState:
    state = load_case_state(case)

    while True:
        if state.stage in (CaseStage.DONE, CaseStage.FAILED):
            return state
        if until is not None and state.stage is until:
            return state

        plan = route(state)
        if plan.approval_gate:
            if not _is_approval_granted(state):
                return state
            result = StepResult.ok()
        else:
            if plan.handler_name is None:
                raise KeyError(f"Missing handler_name for stage {plan.stage.name}")
            if plan.handler_name not in handlers:
                raise KeyError(f"Missing handler for '{plan.handler_name}'")
            result = handlers[plan.handler_name](case, state, plan)

        state = reduce(state, result, max_repair_cycles=max_repair_cycles)
        _checkpoint_state(case, state)
