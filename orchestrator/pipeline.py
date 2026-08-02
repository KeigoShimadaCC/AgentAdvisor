"""End-to-end pipeline entry point.

Wires stage handlers to the state machine, manages budgets, and
supports both interactive (halt at approval gates) and unattended
(auto-approve) operation.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from orchestrator.artifacts import AuditEvent, FramingApproval, FramingDecision
from orchestrator.backend import AgentBackend, CursorCLIBackend
from orchestrator.budget import BudgetConfig, BudgetLedger
from orchestrator.case_store import Case, create_case
from orchestrator.citations import register_citation_hooks
from orchestrator.memory import MemoryStore, write_digests
from orchestrator.stages import StageHandlers
from orchestrator.state_machine import (
    CaseStage,
    CaseState,
    StepHandler,
    load_case_state,
    run_case,
    save_case_state,
)
from orchestrator.task_graph import TaskGraph

# Model tier map for budget accounting (from role configs).
_DEFAULT_MODEL_TIER_MAP: dict[str, str] = {
    "claude-opus-5-thinking-high": "high",
    "gpt-5.6-sol-high": "high",
    "gpt-5.6-sol": "high",
    "gpt-5.3-codex": "medium",
    "gpt-5.2": "medium",
    "composer-2.5": "low",
    "cursor-grok-4.5-low": "low",
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

MAX_SYNTHESIS_RETRIES = 1


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
) -> CaseState:
    """Run the full decision pipeline on a case.

    Parameters
    ----------
    case:
        The case to run (created via ``create_case``).
    raw_prompt:
        The user's raw decision prompt.
    backend:
        Agent backend (defaults to ``CursorCLIBackend``).
    budget_config:
        Budget configuration (defaults to ``DEFAULT_BUDGET``).
    auto_approve:
        If True, automatically approve at both gates without halting.
        Used for unattended benchmark runs.
    model_tier_map:
        Model name to tier mapping for budget accounting.

    Returns
    -------
    Final case state.
    """
    backend_impl = backend or CursorCLIBackend()
    budget = budget_config or DEFAULT_BUDGET
    tier_map = model_tier_map or _DEFAULT_MODEL_TIER_MAP

    # Register citation hooks before any Director invocation
    register_citation_hooks()

    # Prior-case recall, written before the first invocation so it can be projected.
    # Nothing in it is citable; it is context, not evidence.
    store = memory_store or MemoryStore()
    write_digests(case, question=raw_prompt, store=store)

    # Initialize budget ledger from current state
    state = load_case_state(case)
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
    )
    handlers._budget_ledger = ledger
    handlers._task_graph = task_graph

    handler_map = handlers.handlers()

    if auto_approve:
        final_state = _run_unattended(case, handler_map, budget, state)
    else:
        final_state = run_case(case, handler_map, max_synthesis_retries=MAX_SYNTHESIS_RETRIES)

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
) -> CaseState:
    """Run the pipeline with auto-approval at both gates."""
    while True:
        state = run_case(
            case,
            handler_map,
            max_repair_cycles=budget.max_repair_cycles,
            max_synthesis_retries=MAX_SYNTHESIS_RETRIES,
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
