"""End-to-end pipeline entry point.

Wires stage handlers to the state machine, manages budgets, and
supports both interactive (halt at approval gates) and unattended
(auto-approve) operation.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from orchestrator.artifacts import FramingApproval, FramingDecision
from orchestrator.backend import AgentBackend, CursorCLIBackend
from orchestrator.budget import BudgetConfig, BudgetLedger
from orchestrator.case_store import Case, create_case
from orchestrator.citations import register_citation_hooks
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


def run(
    case: Case,
    *,
    raw_prompt: str,
    backend: AgentBackend | None = None,
    budget_config: BudgetConfig | None = None,
    auto_approve: bool = False,
    model_tier_map: dict[str, str] | None = None,
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
    )
    handlers._budget_ledger = ledger
    handlers._task_graph = task_graph

    handler_map = handlers.handlers()

    if auto_approve:
        return _run_unattended(case, handler_map, budget, state)
    return run_case(case, handler_map)


def _run_unattended(
    case: Case,
    handler_map: Mapping[str, StepHandler],
    budget: BudgetConfig,
    state: CaseState,
) -> CaseState:
    """Run the pipeline with auto-approval at both gates."""
    while True:
        state = run_case(case, handler_map, max_repair_cycles=budget.max_repair_cycles)

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
    )
    return case, state
