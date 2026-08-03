"""End-to-end pipeline entry point.

Wires stage handlers to the state machine, manages budgets, and
supports both interactive (halt at approval gates) and unattended
(auto-approve) operation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from orchestrator.artifacts import (
    AuditEvent,
    DecisionSpec,
    FramingApproval,
    FramingDecision,
    IntakeRecord,
)
from orchestrator.artifacts.common import Depth
from orchestrator.backend import AgentBackend, make_backend
from orchestrator.budget import BudgetConfig, BudgetLedger
from orchestrator.case_store import Case, create_case
from orchestrator.citations import register_citation_hooks
from orchestrator.memory import MemoryStore, write_digests
from orchestrator.stages import StageHandlers
from orchestrator.state_machine import (
    ACTIVE_STAGES,
    CaseStage,
    CaseState,
    StepHandler,
    load_case_state,
    run_case,
    save_case_state,
)
from orchestrator.task_graph import TaskGraph

# Model tier map for budget accounting (from role configs). Model ids are unique
# across backends, so one map serves both. Only the genuinely expensive models
# are "high": that counter caps the frontier calls, not every capable model.
_DEFAULT_MODEL_TIER_MAP: dict[str, str] = {
    "claude-opus-5-thinking-high": "high",
    "gpt-5.6-sol-high": "high",
    "gpt-5.6-sol": "high",
    "gpt-5.3-codex": "medium",
    "gpt-5.2": "medium",
    "composer-2.5": "low",
    "cursor-grok-4.5-low": "low",
    # droid backend
    "claude-opus-4-8": "high",
    "gpt-5.5-pro": "high",
    "claude-sonnet-5": "medium",
    "gpt-5.4": "medium",
    "claude-haiku-4-5-20251001": "low",
}

SMALL_BUDGET = BudgetConfig(
    max_agent_invocations=15,
    max_concurrent_workers=2,
    max_repair_cycles=1,
    max_research_tasks=8,
    max_high_tier_calls=4,
    max_wall_clock_s=3600,
)

DEFAULT_BUDGET = BudgetConfig()

DEEP_BUDGET = BudgetConfig(
    max_agent_invocations=60,
    max_concurrent_workers=3,
    max_repair_cycles=2,
    max_research_tasks=25,
    max_high_tier_calls=10,
    max_wall_clock_s=10800,
)

MAX_SYNTHESIS_RETRIES = 1


@dataclass(frozen=True, slots=True)
class ResumeReport:
    """Result of preparing a case for safe resume."""

    reset_task_ids: list[str] = field(default_factory=list)
    was_interrupted: bool = False


def prepare_resume(case: Case) -> ResumeReport:
    """Reconcile orphaned active tasks before resuming an interrupted case.

    Returns a report of which task ids were reset and whether the case was
    in an active (non-terminal) stage.  Idempotent: calling it on a case with
    no orphaned tasks is a no-op.
    """
    state = load_case_state(case)
    was_interrupted = state.stage in ACTIVE_STAGES

    task_graph = TaskGraph(case)
    reset_task_ids = task_graph.reconcile_orphans()

    case.audit(
        AuditEvent(
            ts=datetime.now(UTC),
            actor="orchestrator",
            event_type="prepare_resume",
            payload={
                "reset_task_ids": reset_task_ids,
                "was_interrupted": was_interrupted,
            },
        )
    )

    return ResumeReport(
        reset_task_ids=reset_task_ids,
        was_interrupted=was_interrupted,
    )


def select_budget_for_depth(depth: Depth) -> tuple[BudgetConfig, str]:
    """Map a decision depth to a budget preset and its profile name."""
    if depth is Depth.LIGHT:
        return SMALL_BUDGET, "light"
    if depth is Depth.DEEP:
        return DEEP_BUDGET, "deep"
    return DEFAULT_BUDGET, "standard"


def run(
    case: Case,
    *,
    raw_prompt: str,
    backend: AgentBackend | None = None,
    budget_config: BudgetConfig | None = None,
    auto_approve: bool = False,
    model_tier_map: dict[str, str] | None = None,
    memory_store: MemoryStore | None = None,
    dual_track: bool = True,
    depth: Depth | None = None,
    clock: Callable[[], datetime] | None = None,
) -> CaseState:
    """Run the full decision pipeline on a case.

    Parameters
    ----------
    case:
        The case to run (created via ``create_case``).
    raw_prompt:
        The user's raw decision prompt.
    backend:
        Agent backend (defaults to the one named by ``AGENTADVISOR_BACKEND``).
    budget_config:
        Budget configuration.  If ``None``, the budget is selected from
        ``depth`` (light → SMALL, standard → DEFAULT, deep → DEEP).
    auto_approve:
        If True, automatically approve at both gates without halting.
        Used for unattended benchmark runs.
    model_tier_map:
        Model name to tier mapping for budget accounting.
    depth:
        Decision depth for budget profile selection when ``budget_config``
        is ``None``.  Falls back to the intake/decision-spec depth if
        available, else ``DEFAULT_BUDGET``.
    clock:
        Injectable clock for wall-clock tracking (testing).

    Returns
    -------
    Final case state.
    """
    backend_impl = backend or make_backend()
    clock_fn = clock or (lambda: datetime.now(UTC))
    tier_map = model_tier_map or _DEFAULT_MODEL_TIER_MAP

    # Resolve the effective budget and profile name.
    effective_depth = depth
    if effective_depth is None:
        # Try to read depth from an existing intake record or decision spec.
        try:
            intake = case.read_artifact(IntakeRecord)
            effective_depth = intake.depth
        except FileNotFoundError:
            try:
                spec = case.read_artifact(DecisionSpec)
                effective_depth = spec.depth
            except FileNotFoundError:
                pass

    if budget_config is not None:
        budget = budget_config
        profile_name = "explicit"
    elif effective_depth is not None:
        budget, profile_name = select_budget_for_depth(effective_depth)
    else:
        budget = DEFAULT_BUDGET
        profile_name = "standard"

    case.audit(
        AuditEvent(
            ts=clock_fn(),
            actor="orchestrator",
            event_type="budget_profile_selected",
            payload={"profile": profile_name},
        )
    )

    # Register citation hooks before any Director invocation
    register_citation_hooks()

    # Prior-case recall, written before the first invocation so it can be projected.
    # Nothing in it is citable; it is context, not evidence.
    store = memory_store or MemoryStore()
    write_digests(case, question=raw_prompt, store=store)

    # Initialize budget ledger from current state
    state = load_case_state(case)

    # Safe-resume: reconcile orphaned active tasks when resuming an interrupted case.
    if state.stage in ACTIVE_STAGES and state.stage is not CaseStage.INTAKE:
        prepare_resume(case)

    if state.started_at_run is None:
        state = state.model_copy(update={"started_at_run": clock_fn()})
    ledger = BudgetLedger(state, budget, tier_map)

    # Initialize task graph
    task_graph = TaskGraph(
        case,
        budget_ledger=ledger,
        budget_kind="agent_invocations",
        enforce_marginal_value_gate=False,
    )

    # Create stage handlers
    handlers = StageHandlers(
        backend=backend_impl,
        budget_config=budget,
        raw_prompt=raw_prompt,
        model_tier_map=tier_map,
        dual_track=dual_track,
        clock=clock_fn,
    )
    handlers._budget_ledger = ledger
    handlers._task_graph = task_graph

    handler_map = handlers.handlers()

    if auto_approve:
        final_state = _run_unattended(case, handler_map, budget, state, clock_fn)
    else:
        final_state = run_case(
            case,
            handler_map,
            max_synthesis_retries=MAX_SYNTHESIS_RETRIES,
            initial_state=state,
            clock=clock_fn,
        )

    if final_state.stage is CaseStage.DONE:
        _record_into_memory(case, store)
    return final_state


def _record_into_memory(case: Case, store: MemoryStore) -> None:
    """Snapshot a completed case so later cases can recall it. Never fatal."""
    try:
        entry = store.record_case(case)
    except Exception as exc:  # noqa: BLE001
        case.audit(
            AuditEvent(
                ts=datetime.now(UTC),
                actor="memory",
                event_type="case_memory_write_failed",
                payload={"error": str(exc)},
            )
        )
        return
    case.audit(
        AuditEvent(
            ts=datetime.now(UTC),
            actor="memory",
            event_type="case_recorded_to_memory",
            payload={
                "case_id": entry.case_id,
                "recommended_action": entry.recommended_action,
                "memory_root": str(store.root),
            },
        )
    )


def _run_unattended(
    case: Case,
    handler_map: Mapping[str, StepHandler],
    budget: BudgetConfig,
    state: CaseState,
    clock: Callable[[], datetime] | None = None,
) -> CaseState:
    """Run the pipeline with auto-approval at both gates."""
    while True:
        state = run_case(
            case,
            handler_map,
            max_repair_cycles=budget.max_repair_cycles,
            max_synthesis_retries=MAX_SYNTHESIS_RETRIES,
            initial_state=state,
            clock=clock,
        )

        if state.stage is CaseStage.AWAITING_FRAMING_APPROVAL:
            # Auto-approve framing
            approval = FramingApproval(
                decision=FramingDecision.APPROVE,
                approved_by="auto-approve",
                approved_at=datetime.now(UTC),
            )
            case.write_artifact(approval)
            state = state.model_copy(update={"framing_approved": True})
            save_case_state(case, state)
            continue

        if state.stage is CaseStage.AWAITING_FINAL_APPROVAL:
            # Auto-approve final recommendation
            state = state.model_copy(update={"final_approved": True})
            save_case_state(case, state)
            continue

        # DONE or FAILED
        return state


def run_scenario(
    prompt: str,
    *,
    slug: str = "scenario",
    budget_config: BudgetConfig | None = None,
    backend: AgentBackend | None = None,
    cases_root: Path | None = None,
    memory_store: MemoryStore | None = None,
    dual_track: bool = True,
) -> tuple[Case, CaseState]:
    """Create a case and run it unattended end-to-end.

    Convenience function for benchmark runners.
    """
    case = create_case(slug, cases_root=cases_root)
    state = run(
        case,
        raw_prompt=prompt,
        backend=backend,
        budget_config=budget_config or SMALL_BUDGET,
        auto_approve=True,
        memory_store=memory_store,
        dual_track=dual_track,
    )
    return case, state
