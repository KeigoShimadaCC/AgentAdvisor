from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from orchestrator.budget import (
    BudgetConfig,
    BudgetKind,
    BudgetLedger,
    ModelTier,
    StopDecision,
    StopEvaluator,
    StopEvaluatorInputs,
    StopReason,
)
from orchestrator.state_machine import CaseState


def _state() -> CaseState:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return CaseState(case_id="case-001-budget", created_at=now, updated_at=now)


@pytest.mark.parametrize(
    ("kind", "config_overrides", "consume_kwargs"),
    [
        (BudgetKind.AGENT_INVOCATIONS, {"max_agent_invocations": 2}, {}),
        (BudgetKind.CONCURRENT_WORKERS, {"max_concurrent_workers": 2}, {}),
        (BudgetKind.REPAIR_CYCLES, {"max_repair_cycles": 2}, {}),
        (BudgetKind.RESEARCH_TASKS, {"max_research_tasks": 2}, {}),
        (
            BudgetKind.HIGH_TIER_CALLS,
            {"max_high_tier_calls": 2, "max_agent_invocations": 10},
            {"kind": BudgetKind.AGENT_INVOCATIONS.value, "model": "model-high"},
        ),
        (BudgetKind.WALL_CLOCK_S, {"max_wall_clock_s": 2}, {}),
    ],
)
def test_try_consume_returns_false_when_exceeding_cap(
    kind: BudgetKind,
    config_overrides: dict[str, int],
    consume_kwargs: dict[str, Any],
) -> None:
    config_payload = {
        "max_agent_invocations": 100,
        "max_concurrent_workers": 100,
        "max_repair_cycles": 100,
        "max_research_tasks": 100,
        "max_high_tier_calls": 100,
        "max_wall_clock_s": 100,
    }
    config_payload.update(config_overrides)
    ledger = BudgetLedger(
        state=_state(),
        config=BudgetConfig(**config_payload),
        model_tier_map={"model-high": "high"},
    )

    kwargs: dict[str, Any]
    if consume_kwargs:
        kwargs = consume_kwargs
    else:
        kwargs = {"kind": kind.value}

    assert ledger.try_consume(**kwargs)
    assert ledger.try_consume(**kwargs)
    assert not ledger.try_consume(**kwargs)


def test_concurrent_consumers_never_overshoot_cap() -> None:
    state = _state()
    cap = 17
    ledger = BudgetLedger(
        state=state,
        config=BudgetConfig(
            max_agent_invocations=100,
            max_concurrent_workers=100,
            max_repair_cycles=100,
            max_research_tasks=cap,
            max_high_tier_calls=100,
            max_wall_clock_s=1000,
        ),
        model_tier_map={},
    )

    with ThreadPoolExecutor(max_workers=100) as pool:
        results = list(
            pool.map(
                lambda _: ledger.try_consume(BudgetKind.RESEARCH_TASKS.value),
                range(100),
            )
        )

    assert sum(results) == cap
    assert state.budget_counters[BudgetKind.RESEARCH_TASKS.value] == cap


def test_high_tier_counted_only_for_mapped_high_models() -> None:
    state = _state()
    ledger = BudgetLedger(
        state=state,
        config=BudgetConfig(max_agent_invocations=10, max_high_tier_calls=10),
        model_tier_map={
            "model-high": "high",
            "model-medium": "medium",
        },
    )

    assert ledger.try_consume(BudgetKind.AGENT_INVOCATIONS.value, model="model-high")
    assert ledger.try_consume(BudgetKind.AGENT_INVOCATIONS.value, model="model-medium")
    assert ledger.try_consume(BudgetKind.AGENT_INVOCATIONS.value, model="unknown-model")

    assert state.budget_counters[BudgetKind.AGENT_INVOCATIONS.value] == 3
    assert state.budget_counters[BudgetKind.HIGH_TIER_CALLS.value] == 1


@pytest.mark.parametrize(
    ("inputs_update", "expected_reasons"),
    [
        (
            {"open_critical_evidence_gaps": False},
            {StopReason.NO_CRITICAL_EVIDENCE_GAPS_REMAIN},
        ),
        (
            {"recommendation_stable": True},
            {StopReason.RECOMMENDATION_STABLE_ACROSS_SENSITIVITY_RANGES},
        ),
        (
            {"unresolved_material_objections": False},
            {StopReason.NO_UNRESOLVED_OBJECTION_LIKELY_TO_CHANGE_DECISION},
        ),
        (
            {"expected_value_of_more_research_low": True},
            {StopReason.EXPECTED_VALUE_OF_MORE_RESEARCH_LOW},
        ),
        (
            {"remaining_budget": {"max_research_tasks": 0}},
            {StopReason.INVESTIGATION_BUDGET_EXHAUSTED},
        ),
        (
            {"deadline": datetime(2026, 1, 1, 12, tzinfo=UTC)},
            {StopReason.USER_DEADLINE_OR_DEPTH_LIMIT_REACHED},
        ),
    ],
)
def test_stop_evaluator_covers_every_stage_9_reason(
    inputs_update: dict[str, Any], expected_reasons: set[StopReason]
) -> None:
    evaluator = StopEvaluator(clock=lambda: datetime(2026, 1, 1, 12, tzinfo=UTC))
    base_inputs = StopEvaluatorInputs(
        open_critical_evidence_gaps=True,
        unresolved_material_objections=True,
        recommendation_stable=False,
        expected_value_of_more_research_low=False,
        remaining_budget={"max_research_tasks": 1},
        deadline=datetime(2026, 1, 1, 13, tzinfo=UTC),
    )
    decision = evaluator.evaluate(base_inputs.model_copy(update=inputs_update))

    assert decision.action == "stop"
    assert set(decision.reasons) == expected_reasons


def test_stop_evaluator_continue_case() -> None:
    evaluator = StopEvaluator(clock=lambda: datetime(2026, 1, 1, 12, tzinfo=UTC))
    decision = evaluator.evaluate(
        StopEvaluatorInputs(
            open_critical_evidence_gaps=True,
            unresolved_material_objections=True,
            recommendation_stable=False,
            expected_value_of_more_research_low=False,
            remaining_budget={"max_research_tasks": 3},
            deadline=datetime(2026, 1, 1, 13, tzinfo=UTC),
        )
    )

    assert decision == StopDecision(action="continue", reasons=(), disclosure=None)


def test_budget_exhaustion_emits_disclosure_record() -> None:
    evaluator = StopEvaluator(clock=lambda: datetime(2026, 1, 1, 12, tzinfo=UTC))
    decision = evaluator.evaluate(
        StopEvaluatorInputs(
            open_critical_evidence_gaps=True,
            unresolved_material_objections=True,
            recommendation_stable=False,
            expected_value_of_more_research_low=False,
            remaining_budget={
                "max_research_tasks": 0,
                "max_high_tier_calls": -1,
                "max_agent_invocations": 2,
            },
        )
    )

    assert decision.action == "stop"
    assert StopReason.INVESTIGATION_BUDGET_EXHAUSTED in decision.reasons
    assert decision.disclosure is not None
    assert decision.disclosure.exhausted_dimensions == (
        "max_high_tier_calls",
        "max_research_tasks",
    )


def test_wall_clock_stop_uses_injected_clock() -> None:
    before_deadline = datetime(2026, 1, 1, 12, tzinfo=UTC)
    after_deadline = before_deadline + timedelta(minutes=2)
    deadline = before_deadline + timedelta(minutes=1)

    evaluator_before = StopEvaluator(clock=lambda: before_deadline)
    continue_decision = evaluator_before.evaluate(
        StopEvaluatorInputs(
            open_critical_evidence_gaps=True,
            unresolved_material_objections=True,
            recommendation_stable=False,
            expected_value_of_more_research_low=False,
            remaining_budget={"max_research_tasks": 1},
            deadline=deadline,
        )
    )
    assert continue_decision.action == "continue"

    evaluator_after = StopEvaluator(clock=lambda: after_deadline)
    stop_decision = evaluator_after.evaluate(
        StopEvaluatorInputs(
            open_critical_evidence_gaps=True,
            unresolved_material_objections=True,
            recommendation_stable=False,
            expected_value_of_more_research_low=False,
            remaining_budget={"max_research_tasks": 1},
            deadline=deadline,
        )
    )

    assert stop_decision.action == "stop"
    assert stop_decision.reasons == (StopReason.USER_DEADLINE_OR_DEPTH_LIMIT_REACHED,)


# ── The high-capability ceiling can actually fire ────────────────────────────
#
# North star Section 13 caps "maximum high-capability model calls".  Counting only
# frontier models left the cap unable to fire on any shipped configuration:
# cursor runs every role on `low` models and droid on `medium`, so nothing ever
# mapped to `high` and the counter sat at zero while seven roles declared
# `model_tier: high`.  A ceiling enforced by a counter that cannot increment is
# not a ceiling.


def _tiered_ledger(**config: Any) -> tuple[CaseState, BudgetLedger]:
    state = _state()
    ledger = BudgetLedger(
        state=state,
        config=BudgetConfig(**config),
        model_tier_map={"model-high": "high", "model-medium": "medium", "model-low": "low"},
    )
    return state, ledger


def test_frontier_model_still_counts_against_the_ceiling() -> None:
    """The original semantics survive, so a future frontier config stays correct."""

    _, ledger = _tiered_ledger(max_agent_invocations=10, max_high_tier_calls=10)

    assert ledger.counts_against_high_tier("model-high")
    assert ledger.counts_against_high_tier("model-high", role_tier="low")


def test_escalating_a_high_tier_role_counts_even_on_a_medium_model() -> None:
    """The case the shipped config actually produces."""

    _, ledger = _tiered_ledger(max_agent_invocations=10, max_high_tier_calls=10)

    assert ledger.counts_against_high_tier("model-medium", role_tier="high")
    assert ledger.counts_against_high_tier("model-low", role_tier=ModelTier.HIGH)


def test_escalating_a_lower_tier_role_does_not_count() -> None:
    _, ledger = _tiered_ledger(max_agent_invocations=10, max_high_tier_calls=10)

    assert not ledger.counts_against_high_tier("model-medium", role_tier="medium")
    assert not ledger.counts_against_high_tier("model-low", role_tier="low")
    assert not ledger.counts_against_high_tier("model-medium")


def test_the_ceiling_refuses_once_reached() -> None:
    state, ledger = _tiered_ledger(max_agent_invocations=10, max_high_tier_calls=2)

    assert ledger.try_consume(BudgetKind.HIGH_TIER_CALLS.value)
    assert ledger.try_consume(BudgetKind.HIGH_TIER_CALLS.value)
    assert not ledger.try_consume(BudgetKind.HIGH_TIER_CALLS.value)
    assert state.budget_counters[BudgetKind.HIGH_TIER_CALLS.value] == 2


def test_shipped_roles_reach_the_ceiling_through_their_declared_tier() -> None:
    """The regression guard: no role's model maps to `high` on either backend.

    If this stops being true the cap still works — `counts_against_high_tier`
    returns True on the model alone — but the reason the role-tier arm exists
    would have gone away, and that is worth noticing rather than assuming.
    """

    from orchestrator.artifacts import TaskRole
    from orchestrator.pipeline import _DEFAULT_MODEL_TIER_MAP
    from orchestrator.roles_config import load_role_config, models_for

    high_tier_roles = []
    for role in TaskRole:
        try:
            config = load_role_config(role)
        except Exception:
            continue
        if config.model_tier == "high":
            high_tier_roles.append(config)

    assert high_tier_roles, "expected at least one role to declare model_tier: high"

    for config in high_tier_roles:
        for backend in ("cursor", "droid"):
            escalation = models_for(config, backend).escalation_model
            assert _DEFAULT_MODEL_TIER_MAP.get(escalation) != "high", (
                f"{config.stem} on {backend} now escalates to a frontier model "
                f"({escalation}); the model-based arm covers it and this guard is stale."
            )
