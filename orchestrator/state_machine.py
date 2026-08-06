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
    STRUCTURING = "structuring"
    PROVISIONAL_THESIS = "provisional_thesis"
    PLANNING = "planning"
    INVESTIGATION = "investigation"
    EVIDENCE_CRITIQUE = "evidence_critique"
    ASSUMPTION_LEDGER = "assumption_ledger"
    COMPETING_HYPOTHESES = "competing_hypotheses"
    PRELIMINARY_RECOMMENDATION = "preliminary_recommendation"
    PRE_MORTEM = "pre_mortem"
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
    synthesis_retries: int = Field(default=0, ge=0)
    framing_revisions: int = Field(default=0, ge=0)
    final_revisions: int = Field(default=0, ge=0)
    budget_counters: dict[str, int] = Field(default_factory=dict)
    started_at_run: datetime | None = Field(default=None)
    elapsed_s: float = Field(default=0.0)
    framing_approved: bool = False
    final_approved: bool = False
    review_accepted: bool | None = Field(default=None)
    failure_cause: str | None = None
    created_at: datetime
    updated_at: datetime


MAX_FRAMING_REVISIONS = 2
MAX_FINAL_REVISIONS = 1


class StepOutcome(Enum):
    ADVANCE = "advance"
    NEEDS_REPAIR = "needs_repair"
    NEEDS_RESYNTHESIS = "needs_resynthesis"
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
    CaseStage.STRUCTURING,
    CaseStage.PROVISIONAL_THESIS,
    CaseStage.PLANNING,
    CaseStage.INVESTIGATION,
    CaseStage.EVIDENCE_CRITIQUE,
    CaseStage.ASSUMPTION_LEDGER,
    CaseStage.COMPETING_HYPOTHESES,
    CaseStage.PRELIMINARY_RECOMMENDATION,
    CaseStage.PRE_MORTEM,
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
        {CaseStage.STRUCTURING, CaseStage.FRAMING, CaseStage.FAILED}
    ),
    CaseStage.STRUCTURING: frozenset({CaseStage.PROVISIONAL_THESIS, CaseStage.FAILED}),
    CaseStage.PROVISIONAL_THESIS: frozenset({CaseStage.PLANNING, CaseStage.FAILED}),
    CaseStage.PLANNING: frozenset({CaseStage.INVESTIGATION, CaseStage.FAILED}),
    CaseStage.INVESTIGATION: frozenset({CaseStage.EVIDENCE_CRITIQUE, CaseStage.FAILED}),
    CaseStage.EVIDENCE_CRITIQUE: frozenset({CaseStage.ASSUMPTION_LEDGER, CaseStage.FAILED}),
    CaseStage.ASSUMPTION_LEDGER: frozenset({CaseStage.COMPETING_HYPOTHESES, CaseStage.FAILED}),
    CaseStage.COMPETING_HYPOTHESES: frozenset(
        {CaseStage.PRELIMINARY_RECOMMENDATION, CaseStage.FAILED}
    ),
    CaseStage.PRELIMINARY_RECOMMENDATION: frozenset({CaseStage.PRE_MORTEM, CaseStage.FAILED}),
    CaseStage.PRE_MORTEM: frozenset({CaseStage.CHALLENGE, CaseStage.FAILED}),
    CaseStage.CHALLENGE: frozenset({CaseStage.STOP_DECISION, CaseStage.FAILED}),
    CaseStage.REPAIR: frozenset({CaseStage.CHALLENGE, CaseStage.FAILED}),
    CaseStage.STOP_DECISION: frozenset({CaseStage.REPAIR, CaseStage.SYNTHESIS, CaseStage.FAILED}),
    CaseStage.SYNTHESIS: frozenset({CaseStage.REVIEW, CaseStage.FAILED}),
    CaseStage.REVIEW: frozenset(
        {CaseStage.AWAITING_FINAL_APPROVAL, CaseStage.SYNTHESIS, CaseStage.FAILED}
    ),
    CaseStage.AWAITING_FINAL_APPROVAL: frozenset(
        {CaseStage.DONE, CaseStage.SYNTHESIS, CaseStage.FAILED}
    ),
    CaseStage.DONE: frozenset(),
    CaseStage.FAILED: frozenset(),
}

_FLOW_PLANS: dict[CaseStage, StepPlan] = {
    CaseStage.INTAKE: StepPlan(CaseStage.INTAKE, "intake", (TaskRole.INTAKE,)),
    CaseStage.FRAMING: StepPlan(CaseStage.FRAMING, "framing", (TaskRole.DIRECTOR,)),
    CaseStage.AWAITING_FRAMING_APPROVAL: StepPlan(
        CaseStage.AWAITING_FRAMING_APPROVAL, None, tuple(), approval_gate=True
    ),
    CaseStage.STRUCTURING: StepPlan(CaseStage.STRUCTURING, "structuring", (TaskRole.STRUCTURER,)),
    CaseStage.PROVISIONAL_THESIS: StepPlan(
        CaseStage.PROVISIONAL_THESIS, "provisional_thesis", (TaskRole.DIRECTOR,)
    ),
    CaseStage.PLANNING: StepPlan(CaseStage.PLANNING, "planning", (TaskRole.PLANNER,)),
    CaseStage.INVESTIGATION: StepPlan(
        CaseStage.INVESTIGATION, "investigation", (TaskRole.RESEARCHER, TaskRole.ANALYST)
    ),
    # No roles: the evidence critique is computed deterministically from the blackboard.
    CaseStage.EVIDENCE_CRITIQUE: StepPlan(
        CaseStage.EVIDENCE_CRITIQUE, "evidence_critique", tuple()
    ),
    CaseStage.ASSUMPTION_LEDGER: StepPlan(
        CaseStage.ASSUMPTION_LEDGER, "assumption_ledger", (TaskRole.ASSUMPTION_ANALYST,)
    ),
    CaseStage.COMPETING_HYPOTHESES: StepPlan(
        CaseStage.COMPETING_HYPOTHESES, "competing_hypotheses", (TaskRole.ACH_ANALYST,)
    ),
    CaseStage.PRELIMINARY_RECOMMENDATION: StepPlan(
        CaseStage.PRELIMINARY_RECOMMENDATION, "preliminary_recommendation", (TaskRole.DIRECTOR,)
    ),
    CaseStage.PRE_MORTEM: StepPlan(CaseStage.PRE_MORTEM, "pre_mortem", (TaskRole.PREMORTEM,)),
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


def revision_transition(
    state: CaseState,
    target: CaseStage,
) -> CaseState:
    """Perform an explicit backward transition for a revision request.

    Unlike ``reduce`` (which is driven by step results), this is triggered
    directly by the control layer when a user requests a framing or final
    revision.  The revision cap is enforced here so it lives in deterministic
    routing, not in prompts.

    Raises ``IllegalTransition`` if the transition is not allowed or the
    revision cap has been reached.
    """
    if target is CaseStage.FRAMING:
        if state.framing_revisions >= MAX_FRAMING_REVISIONS:
            raise IllegalTransition(
                f"Framing revision cap reached ({MAX_FRAMING_REVISIONS}). "
                "No further framing revisions allowed."
            )
        _next_or_raise(state.stage, target)
        return state.model_copy(
            update={"stage": target, "framing_revisions": state.framing_revisions + 1}
        )

    if target is CaseStage.SYNTHESIS:
        if state.final_revisions >= MAX_FINAL_REVISIONS:
            raise IllegalTransition(
                f"Final revision cap reached ({MAX_FINAL_REVISIONS}). "
                "No further final revisions allowed."
            )
        _next_or_raise(state.stage, target)
        return state.model_copy(
            update={"stage": target, "final_revisions": state.final_revisions + 1}
        )

    raise IllegalTransition(
        f"revision_transition only targets FRAMING or SYNTHESIS, not {target.name}"
    )


def route(state: CaseState) -> StepPlan:
    if state.stage in (CaseStage.DONE, CaseStage.FAILED):
        raise IllegalTransition(f"Illegal transition: {state.stage.name} -> <routed>")
    return _FLOW_PLANS[state.stage]


@dataclass(frozen=True, slots=True)
class _Transition:
    stage: CaseStage
    repair_cycle: int
    synthesis_retries: int


def _resolve_next_stage(
    state: CaseState,
    result: StepResult,
    max_repair_cycles: int,
    max_synthesis_retries: int,
) -> _Transition:
    if result.outcome is StepOutcome.ERROR:
        return _Transition(CaseStage.FAILED, state.repair_cycle, state.synthesis_retries)

    if state.stage is CaseStage.STOP_DECISION:
        if result.outcome is StepOutcome.NEEDS_REPAIR and state.repair_cycle < max_repair_cycles:
            return _Transition(CaseStage.REPAIR, state.repair_cycle + 1, state.synthesis_retries)
        return _Transition(CaseStage.SYNTHESIS, state.repair_cycle, state.synthesis_retries)

    if state.stage is CaseStage.REVIEW:
        if (
            result.outcome is StepOutcome.NEEDS_RESYNTHESIS
            and state.synthesis_retries < max_synthesis_retries
        ):
            return _Transition(CaseStage.SYNTHESIS, state.repair_cycle, state.synthesis_retries + 1)
        return _Transition(
            CaseStage.AWAITING_FINAL_APPROVAL, state.repair_cycle, state.synthesis_retries
        )

    if state.stage is CaseStage.AWAITING_FRAMING_APPROVAL:
        return _Transition(CaseStage.STRUCTURING, state.repair_cycle, state.synthesis_retries)

    if state.stage is CaseStage.AWAITING_FINAL_APPROVAL:
        return _Transition(CaseStage.DONE, state.repair_cycle, state.synthesis_retries)

    next_by_stage: dict[CaseStage, CaseStage] = {
        CaseStage.INTAKE: CaseStage.FRAMING,
        CaseStage.FRAMING: CaseStage.AWAITING_FRAMING_APPROVAL,
        CaseStage.STRUCTURING: CaseStage.PROVISIONAL_THESIS,
        CaseStage.PROVISIONAL_THESIS: CaseStage.PLANNING,
        CaseStage.PLANNING: CaseStage.INVESTIGATION,
        CaseStage.INVESTIGATION: CaseStage.EVIDENCE_CRITIQUE,
        CaseStage.EVIDENCE_CRITIQUE: CaseStage.ASSUMPTION_LEDGER,
        CaseStage.ASSUMPTION_LEDGER: CaseStage.COMPETING_HYPOTHESES,
        CaseStage.COMPETING_HYPOTHESES: CaseStage.PRELIMINARY_RECOMMENDATION,
        CaseStage.PRELIMINARY_RECOMMENDATION: CaseStage.PRE_MORTEM,
        CaseStage.PRE_MORTEM: CaseStage.CHALLENGE,
        CaseStage.CHALLENGE: CaseStage.STOP_DECISION,
        CaseStage.REPAIR: CaseStage.CHALLENGE,
        CaseStage.SYNTHESIS: CaseStage.REVIEW,
    }
    if state.stage not in next_by_stage:
        raise IllegalTransition(f"Illegal transition: {state.stage.name} -> <unresolved>")
    return _Transition(next_by_stage[state.stage], state.repair_cycle, state.synthesis_retries)


def reduce(
    state: CaseState,
    result: StepResult,
    max_repair_cycles: int = 2,
    *,
    max_synthesis_retries: int = 1,
) -> CaseState:
    if state.stage in (CaseStage.DONE, CaseStage.FAILED):
        raise IllegalTransition(f"Illegal transition: {state.stage.name} -> <reduced>")

    transition = _resolve_next_stage(state, result, max_repair_cycles, max_synthesis_retries)
    _next_or_raise(state.stage, transition.stage)

    failure_cause = result.error_cause if transition.stage is CaseStage.FAILED else None
    return state.model_copy(
        update={
            "stage": transition.stage,
            "repair_cycle": transition.repair_cycle,
            "synthesis_retries": transition.synthesis_retries,
            "failure_cause": failure_cause,
        }
    )


def _is_approval_granted(state: CaseState) -> bool:
    if state.stage is CaseStage.AWAITING_FRAMING_APPROVAL:
        return state.framing_approved
    if state.stage is CaseStage.AWAITING_FINAL_APPROVAL:
        return state.final_approved
    return False


def _checkpoint_state(
    case: Case, state: CaseState, clock: Callable[[], datetime] | None = None
) -> CaseState:
    now = (clock or _utc_now)()
    elapsed_s = state.elapsed_s
    if state.started_at_run is not None:
        elapsed_s += (now - state.started_at_run).total_seconds()
    checkpointed = state.model_copy(
        update={
            "updated_at": now,
            "elapsed_s": elapsed_s,
            "started_at_run": now,
        }
    )
    save_case_state(case, checkpointed)
    return checkpointed


def run_case(
    case: Case,
    handlers: Mapping[str, StepHandler],
    until: CaseStage | None = None,
    *,
    max_repair_cycles: int = 2,
    max_synthesis_retries: int = 1,
    initial_state: CaseState | None = None,
    clock: Callable[[], datetime] | None = None,
) -> CaseState:
    # Callers holding a BudgetLedger must pass their own state: the ledger mutates
    # state.budget_counters in place, and re-loading here would strand those counters
    # on an object that is never checkpointed.
    state = initial_state if initial_state is not None else load_case_state(case)

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

        state = reduce(
            state,
            result,
            max_repair_cycles=max_repair_cycles,
            max_synthesis_retries=max_synthesis_retries,
        )
        state = _checkpoint_state(case, state, clock=clock)
