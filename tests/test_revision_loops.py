"""Sending a case back at either gate (SPEC-028).

The framing gate could previously only be approved: `edits` and `clarification_answers`
were recorded and then ignored, and the state machine had no edge back to framing. These
cover both revision loops, their caps, and the fact that a revision re-holds the gate.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_pipeline_stub import PipelineStubBackend

from orchestrator import control
from orchestrator.artifacts import (
    FinalApproval,
    FinalDecision,
    FramingApproval,
    FramingDecision,
)
from orchestrator.case_store import Case
from orchestrator.pipeline import SMALL_BUDGET
from orchestrator.state_machine import (
    MAX_FINAL_REVISIONS,
    MAX_FRAMING_REVISIONS,
    CaseStage,
    CaseState,
    StepOutcome,
    StepResult,
    load_case_state,
    reduce,
)

PROMPT = "Should I buy the condo or keep renting for another year?"
NOW = datetime.now(UTC)


# --- reducer-level: routing, counters, gate re-holding ------------------------------


def _state(**kwargs: object) -> CaseState:
    base = {
        "case_id": "case-001-revision",
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(kwargs)
    return CaseState(**base)  # type: ignore[arg-type]


def test_a_pending_framing_revision_routes_back_to_framing() -> None:
    state = _state(
        stage=CaseStage.AWAITING_FRAMING_APPROVAL,
        framing_approved=True,
        pending_framing_revision=True,
    )
    nxt = reduce(state, StepResult.ok())

    assert nxt.stage is CaseStage.FRAMING
    assert nxt.framing_revisions == 1
    # The gate must hold again: a revised framing is not pre-approved.
    assert nxt.framing_approved is False
    assert nxt.pending_framing_revision is False


def test_without_a_revision_request_the_framing_gate_advances() -> None:
    state = _state(stage=CaseStage.AWAITING_FRAMING_APPROVAL, framing_approved=True)
    nxt = reduce(state, StepResult.ok())

    assert nxt.stage is CaseStage.STRUCTURING
    assert nxt.framing_revisions == 0


def test_framing_revisions_stop_at_the_cap() -> None:
    state = _state(
        stage=CaseStage.AWAITING_FRAMING_APPROVAL,
        framing_approved=True,
        pending_framing_revision=True,
        framing_revisions=MAX_FRAMING_REVISIONS,
    )
    nxt = reduce(state, StepResult.ok())

    assert nxt.stage is CaseStage.STRUCTURING
    assert nxt.framing_revisions == MAX_FRAMING_REVISIONS


def test_a_pending_final_revision_routes_back_to_synthesis() -> None:
    state = _state(
        stage=CaseStage.AWAITING_FINAL_APPROVAL,
        final_approved=True,
        pending_final_revision=True,
    )
    nxt = reduce(state, StepResult.ok())

    assert nxt.stage is CaseStage.SYNTHESIS
    assert nxt.final_revisions == 1
    assert nxt.final_approved is False
    assert nxt.pending_final_revision is False


def test_final_revisions_stop_at_the_cap() -> None:
    state = _state(
        stage=CaseStage.AWAITING_FINAL_APPROVAL,
        final_approved=True,
        pending_final_revision=True,
        final_revisions=MAX_FINAL_REVISIONS,
    )
    nxt = reduce(state, StepResult.ok())

    assert nxt.stage is CaseStage.DONE


def test_a_user_revision_is_counted_separately_from_a_review_retry() -> None:
    """A reviewer-driven retry and a person asking for changes are different events."""
    state = _state(
        stage=CaseStage.AWAITING_FINAL_APPROVAL,
        final_approved=True,
        pending_final_revision=True,
        synthesis_retries=1,
    )
    nxt = reduce(state, StepResult.ok())

    assert nxt.stage is CaseStage.SYNTHESIS
    assert nxt.final_revisions == 1
    assert nxt.synthesis_retries == 1


def test_an_error_still_fails_the_case_at_a_gate() -> None:
    state = _state(
        stage=CaseStage.AWAITING_FRAMING_APPROVAL,
        framing_approved=True,
        pending_framing_revision=True,
    )
    nxt = reduce(state, StepResult(outcome=StepOutcome.ERROR, error_cause="boom"))
    assert nxt.stage is CaseStage.FAILED


# --- control-level: recording the request ------------------------------------------


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("AGENTADVISOR_RUNTIME_ROOT", str(tmp_path / "runtime"))
    monkeypatch.setenv("AGENTADVISOR_MEMORY_ROOT", str(tmp_path / "memory"))
    return tmp_path / "cases"


def _run(case: Case) -> None:
    control.run_to_halt(
        case,
        raw_prompt=PROMPT,
        budget=SMALL_BUDGET,
        backend=PipelineStubBackend(case),
    )


def _started(env: Path) -> Case:
    case = control.new_case(PROMPT, slug="revision", cases_root=env)
    _run(case)
    return case


def _edits() -> FramingApproval:
    return FramingApproval(
        decision=FramingDecision.EDIT,
        approved_by="tester",
        approved_at=datetime.now(UTC),
        edits={"question": "Buy the condo, keep renting, or move cities?"},
    )


def test_requesting_a_framing_revision_marks_the_case(env: Path) -> None:
    case = _started(env)
    state = control.request_framing_revision(case, _edits())

    assert state.pending_framing_revision is True
    assert state.framing_approved is True  # released so the pipeline can move
    assert (case.root / "shared" / "framing_approval.yaml").exists()


def test_a_revision_request_re_runs_framing_and_re_holds_the_gate(env: Path) -> None:
    case = _started(env)
    control.request_framing_revision(case, _edits())
    _run(case)

    state = load_case_state(case)
    assert state.stage is CaseStage.AWAITING_FRAMING_APPROVAL
    assert state.framing_revisions == 1
    assert state.framing_approved is False


def test_a_revised_case_can_then_be_approved(env: Path) -> None:
    case = _started(env)
    control.request_framing_revision(case, _edits())
    _run(case)

    control.approve_framing(
        case,
        FramingApproval(
            decision=FramingDecision.APPROVE,
            approved_by="tester",
            approved_at=datetime.now(UTC),
        ),
    )
    _run(case)

    assert load_case_state(case).stage is CaseStage.AWAITING_FINAL_APPROVAL


def test_clarification_answers_are_a_valid_revision(env: Path) -> None:
    case = _started(env)
    state = control.request_framing_revision(
        case,
        FramingApproval(
            decision=FramingDecision.ANSWER_CLARIFICATIONS,
            approved_by="tester",
            approved_at=datetime.now(UTC),
            clarification_answers={"Q1": "My deadline is the end of September."},
        ),
    )
    assert state.pending_framing_revision is True


def test_a_plain_approval_is_not_a_revision(env: Path) -> None:
    case = _started(env)
    with pytest.raises(control.ControlError):
        control.request_framing_revision(
            case,
            FramingApproval(
                decision=FramingDecision.APPROVE,
                approved_by="tester",
                approved_at=datetime.now(UTC),
            ),
        )


def test_framing_revisions_are_refused_past_the_cap(env: Path) -> None:
    case = _started(env)
    for _ in range(MAX_FRAMING_REVISIONS):
        control.request_framing_revision(case, _edits())
        _run(case)

    with pytest.raises(control.RevisionLimitReached) as excinfo:
        control.request_framing_revision(case, _edits())
    assert str(MAX_FRAMING_REVISIONS) in str(excinfo.value)


def test_a_framing_revision_at_the_wrong_stage_is_refused(env: Path) -> None:
    case = control.new_case(PROMPT, slug="revision", cases_root=env)
    with pytest.raises(control.WrongStage):
        control.request_framing_revision(case, _edits())


def _send_back(note: str = "The downside case is not addressed.") -> FinalApproval:
    return FinalApproval(
        decision=FinalDecision.REVISE,
        approved_by="tester",
        approved_at=datetime.now(UTC),
        note=note,
    )


def test_sending_the_recommendation_back_returns_it_to_synthesis(env: Path) -> None:
    case = _started(env)
    control.approve_framing(
        case,
        FramingApproval(
            decision=FramingDecision.APPROVE,
            approved_by="tester",
            approved_at=datetime.now(UTC),
        ),
    )
    _run(case)
    assert load_case_state(case).stage is CaseStage.AWAITING_FINAL_APPROVAL

    control.request_final_revision(case, _send_back())
    _run(case)

    state = load_case_state(case)
    assert state.final_revisions == 1
    assert state.stage is CaseStage.AWAITING_FINAL_APPROVAL
    assert state.final_approved is False

    # And a second send-back is refused.
    with pytest.raises(control.RevisionLimitReached):
        control.request_final_revision(case, _send_back("Still not addressed."))


def test_an_accept_is_not_a_send_back(env: Path) -> None:
    case = _started(env)
    with pytest.raises(control.ControlError):
        control.request_final_revision(
            case,
            FinalApproval(
                decision=FinalDecision.ACCEPT,
                approved_by="tester",
                approved_at=datetime.now(UTC),
            ),
        )
