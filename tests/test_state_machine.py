from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from orchestrator.case_store import Case, create_case
from orchestrator.state_machine import (
    ACTIVE_STAGES,
    ALLOWED_TRANSITIONS,
    CaseStage,
    CaseState,
    IllegalTransition,
    StepHandler,
    StepOutcome,
    StepPlan,
    StepResult,
    load_case_state,
    reduce,
    run_case,
    save_case_state,
)

EXPECTED_HAPPY_PATH_WRITES: list[CaseStage] = [
    CaseStage.FRAMING,
    CaseStage.AWAITING_FRAMING_APPROVAL,
    CaseStage.STRUCTURING,
    CaseStage.PROVISIONAL_THESIS,
    CaseStage.PLANNING,
    CaseStage.INVESTIGATION,
    CaseStage.EVIDENCE_CRITIQUE,
    CaseStage.ASSUMPTION_LEDGER,
    CaseStage.PRELIMINARY_RECOMMENDATION,
    CaseStage.PRE_MORTEM,
    CaseStage.CHALLENGE,
    CaseStage.STOP_DECISION,
    CaseStage.SYNTHESIS,
    CaseStage.REVIEW,
    CaseStage.AWAITING_FINAL_APPROVAL,
    CaseStage.DONE,
]


def _state_for(stage: CaseStage) -> CaseState:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return CaseState(case_id="case-001-test", stage=stage, created_at=now, updated_at=now)


def _approved_state(case: Case) -> CaseState:
    base = load_case_state(case)
    approved = base.model_copy(update={"framing_approved": True, "final_approved": True})
    save_case_state(case, approved)
    return approved


def _spy_state_writes(monkeypatch: pytest.MonkeyPatch) -> list[CaseStage]:
    from orchestrator import state_machine as sm

    writes: list[CaseStage] = []
    original_atomic_write = sm.atomic_write_text

    def _spy_atomic_write(path: Path, content: str) -> None:
        data = yaml.safe_load(content)
        writes.append(CaseState.model_validate(data).stage)
        original_atomic_write(path, content)

    monkeypatch.setattr("orchestrator.state_machine.atomic_write_text", _spy_atomic_write)
    return writes


def _build_handlers(
    *,
    executed: list[CaseStage],
    stop_outcomes: Iterator[StepOutcome] | None = None,
    review_outcomes: Iterator[StepOutcome] | None = None,
) -> dict[str, StepHandler]:
    def _default_handler(_: Case, __: CaseState, plan: StepPlan) -> StepResult:
        executed.append(plan.stage)
        return StepResult.ok()

    def _stop_handler(_: Case, __: CaseState, plan: StepPlan) -> StepResult:
        executed.append(plan.stage)
        if stop_outcomes is None:
            return StepResult.ok()
        return StepResult.ok(next(stop_outcomes))

    def _review_handler(_: Case, __: CaseState, plan: StepPlan) -> StepResult:
        executed.append(plan.stage)
        if review_outcomes is None:
            return StepResult.ok()
        return StepResult.ok(next(review_outcomes))

    return {
        "intake": _default_handler,
        "framing": _default_handler,
        "structuring": _default_handler,
        "provisional_thesis": _default_handler,
        "planning": _default_handler,
        "investigation": _default_handler,
        "evidence_critique": _default_handler,
        "assumption_ledger": _default_handler,
        "preliminary_recommendation": _default_handler,
        "pre_mortem": _default_handler,
        "challenge": _default_handler,
        "repair": _default_handler,
        "stop_decision": _stop_handler,
        "synthesis": _default_handler,
        "review": _review_handler,
    }


def test_happy_path_walks_to_done_and_checkpoints_every_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = create_case("happy-path", cases_root=tmp_path)
    _approved_state(case)

    writes = _spy_state_writes(monkeypatch)
    executed: list[CaseStage] = []
    handlers = _build_handlers(executed=executed)

    final_state = run_case(case, handlers)

    assert final_state.stage is CaseStage.DONE
    assert writes == EXPECTED_HAPPY_PATH_WRITES
    assert len(writes) == len(EXPECTED_HAPPY_PATH_WRITES)
    assert writes[writes.index(CaseStage.PROVISIONAL_THESIS) + 1] is CaseStage.PLANNING


def test_repair_loop_is_capped_and_forces_synthesis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = create_case("repair-cap", cases_root=tmp_path)
    _approved_state(case)

    writes = _spy_state_writes(monkeypatch)
    executed: list[CaseStage] = []
    stop_outcomes = iter(
        [
            StepOutcome.NEEDS_REPAIR,
            StepOutcome.NEEDS_REPAIR,
            StepOutcome.NEEDS_REPAIR,
        ]
    )
    handlers = _build_handlers(executed=executed, stop_outcomes=stop_outcomes)

    final_state = run_case(case, handlers, max_repair_cycles=2)

    assert final_state.stage is CaseStage.DONE
    assert final_state.repair_cycle == 2
    assert writes.count(CaseStage.REPAIR) == 2
    assert writes.count(CaseStage.STOP_DECISION) == 3

    stop_indexes = [index for index, stage in enumerate(writes) if stage is CaseStage.STOP_DECISION]
    assert writes[stop_indexes[0] + 1] is CaseStage.REPAIR
    assert writes[stop_indexes[1] + 1] is CaseStage.REPAIR
    assert writes[stop_indexes[2] + 1] is CaseStage.SYNTHESIS

    sequence = [
        stage
        for stage in writes
        if stage in {CaseStage.REPAIR, CaseStage.CHALLENGE, CaseStage.STOP_DECISION}
    ]
    assert sequence == [
        CaseStage.CHALLENGE,
        CaseStage.STOP_DECISION,
        CaseStage.REPAIR,
        CaseStage.CHALLENGE,
        CaseStage.STOP_DECISION,
        CaseStage.REPAIR,
        CaseStage.CHALLENGE,
        CaseStage.STOP_DECISION,
    ]


def test_illegal_transition_raises_with_stage_names() -> None:
    state = _state_for(CaseStage.STOP_DECISION)
    original = ALLOWED_TRANSITIONS[CaseStage.STOP_DECISION]
    ALLOWED_TRANSITIONS[CaseStage.STOP_DECISION] = frozenset({CaseStage.SYNTHESIS})
    try:
        with pytest.raises(IllegalTransition, match="STOP_DECISION -> REPAIR"):
            reduce(state, StepResult.ok(StepOutcome.NEEDS_REPAIR))
    finally:
        ALLOWED_TRANSITIONS[CaseStage.STOP_DECISION] = original


@pytest.mark.parametrize("stage", ACTIVE_STAGES)
def test_failed_reachable_from_every_active_stage(stage: CaseStage) -> None:
    state = _state_for(stage)
    next_state = reduce(state, StepResult.error("boom"))
    assert next_state.stage is CaseStage.FAILED
    assert next_state.failure_cause == "boom"


def test_approval_halt_and_resume_after_approval(tmp_path: Path) -> None:
    case = create_case("approval-halt", cases_root=tmp_path)
    executed: list[CaseStage] = []
    handlers = _build_handlers(executed=executed)

    paused_state = run_case(case, handlers)
    assert paused_state.stage is CaseStage.AWAITING_FRAMING_APPROVAL
    assert executed == [CaseStage.INTAKE, CaseStage.FRAMING]

    approved = load_case_state(case).model_copy(update={"framing_approved": True})
    save_case_state(case, approved)

    resumed_state = run_case(case, handlers, until=CaseStage.PLANNING)
    assert resumed_state.stage is CaseStage.PLANNING
    assert CaseStage.STRUCTURING in executed
    assert CaseStage.PROVISIONAL_THESIS in executed


def test_failed_review_returns_to_synthesis_once_then_advances(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = create_case("review-retry", cases_root=tmp_path)
    _approved_state(case)

    writes = _spy_state_writes(monkeypatch)
    review_outcomes = iter([StepOutcome.NEEDS_RESYNTHESIS, StepOutcome.NEEDS_RESYNTHESIS])
    handlers = _build_handlers(executed=[], review_outcomes=review_outcomes)

    final_state = run_case(case, handlers, max_synthesis_retries=1)

    assert final_state.stage is CaseStage.DONE
    assert final_state.synthesis_retries == 1
    assert writes.count(CaseStage.SYNTHESIS) == 2
    assert writes.count(CaseStage.REVIEW) == 2
    review_indexes = [index for index, stage in enumerate(writes) if stage is CaseStage.REVIEW]
    assert writes[review_indexes[0] + 1] is CaseStage.SYNTHESIS
    assert writes[review_indexes[1] + 1] is CaseStage.AWAITING_FINAL_APPROVAL


@pytest.mark.parametrize("interrupt_stage", EXPECTED_HAPPY_PATH_WRITES)
def test_kill_and_resume_matches_uninterrupted_run(
    tmp_path: Path, interrupt_stage: CaseStage
) -> None:
    from orchestrator import state_machine as sm

    uninterrupted_case = create_case("uninterrupted", cases_root=tmp_path)
    _approved_state(uninterrupted_case)
    uninterrupted_writes: list[CaseStage] = []
    original_atomic_write = sm.atomic_write_text

    def _uninterrupted_spy(path: Path, content: str) -> None:
        data = yaml.safe_load(content)
        uninterrupted_writes.append(CaseState.model_validate(data).stage)
        original_atomic_write(path, content)

    monkeypatch_uninterrupted = pytest.MonkeyPatch()
    monkeypatch_uninterrupted.setattr(
        "orchestrator.state_machine.atomic_write_text", _uninterrupted_spy
    )
    try:
        uninterrupted_handlers = _build_handlers(executed=[])
        run_case(uninterrupted_case, uninterrupted_handlers)
    finally:
        monkeypatch_uninterrupted.undo()

    interrupted_case = create_case("interrupted", cases_root=tmp_path)
    _approved_state(interrupted_case)
    interrupted_writes: list[CaseStage] = []

    def _interrupted_spy(path: Path, content: str) -> None:
        data = yaml.safe_load(content)
        interrupted_writes.append(CaseState.model_validate(data).stage)
        original_atomic_write(path, content)

    monkeypatch_interrupted = pytest.MonkeyPatch()
    monkeypatch_interrupted.setattr(
        "orchestrator.state_machine.atomic_write_text", _interrupted_spy
    )
    try:
        interrupted_handlers = _build_handlers(executed=[])
        run_case(interrupted_case, interrupted_handlers, until=interrupt_stage)
        reloaded = load_case_state(interrupted_case)
        assert reloaded.stage is interrupt_stage
        run_case(interrupted_case, interrupted_handlers)
    finally:
        monkeypatch_interrupted.undo()

    assert uninterrupted_writes == interrupted_writes
