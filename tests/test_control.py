"""The shared control layer: gates, status, runs (SPEC-027).

These exercise the module the CLI and any future web service both sit on, so the
assertions are about case state and artifacts on disk rather than printed output.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_pipeline_stub import PipelineStubBackend

from orchestrator import control
from orchestrator.artifacts import (
    FinalApproval,
    FinalDecision,
    FramingApproval,
    FramingDecision,
    IntakeRecord,
)
from orchestrator.case_store import Case
from orchestrator.pipeline import SMALL_BUDGET
from orchestrator.state_machine import CaseStage, load_case_state, save_case_state
from orchestrator.supervisor import case_lock

PROMPT = "Should I take the Series B offer or stay at the larger company?"


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
    case = control.new_case(PROMPT, slug="control", cases_root=env)
    _run(case)
    return case


def _audit_events(case: Case) -> list[dict[str, object]]:
    path = case.root / "audit.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _event_types(case: Case) -> list[str]:
    return [str(event["event_type"]) for event in _audit_events(case)]


def _approve_framing(case: Case) -> None:
    control.approve_framing(
        case,
        FramingApproval(
            decision=FramingDecision.APPROVE,
            approved_by="tester",
            approved_at=datetime.now(UTC),
        ),
    )


def _accept_final(case: Case) -> None:
    control.approve_final(
        case,
        FinalApproval(
            decision=FinalDecision.ACCEPT,
            approved_by="tester",
            approved_at=datetime.now(UTC),
        ),
    )


# --- creation and prompt recovery -------------------------------------------------


def test_new_case_creates_a_case_and_audits_it(env: Path) -> None:
    case = control.new_case(PROMPT, slug="control", cases_root=env)

    assert case.root.exists()
    assert "control_case_created" in _event_types(case)


def test_an_empty_prompt_is_refused(env: Path) -> None:
    with pytest.raises(control.ControlError):
        control.new_case("   ", slug="control", cases_root=env)


def test_raw_prompt_is_recovered_from_the_intake_record(env: Path) -> None:
    """The intake record is the only place the user's words survive verbatim."""
    case = _started(env)
    recorded = case.read_artifact(IntakeRecord).raw_prompt

    assert control.raw_prompt_for(case) == recorded
    assert recorded


def test_a_case_without_intake_cannot_be_resumed(env: Path) -> None:
    case = control.new_case(PROMPT, slug="control", cases_root=env)
    with pytest.raises(control.MissingPrompt):
        control.raw_prompt_for(case)


# --- the lifecycle through both gates ---------------------------------------------


def test_run_halts_at_the_framing_gate_and_audits_the_run(env: Path) -> None:
    case = _started(env)

    state = load_case_state(case)
    assert state.stage is CaseStage.AWAITING_FRAMING_APPROVAL
    assert state.framing_approved is False

    types = _event_types(case)
    assert "control_run_started" in types
    assert "control_run_finished" in types


def test_framing_approval_writes_the_artifact_and_clears_the_gate(env: Path) -> None:
    case = _started(env)
    state = control.approve_framing(
        case,
        FramingApproval(
            decision=FramingDecision.APPROVE,
            approved_by="tester",
            approved_at=datetime.now(UTC),
        ),
    )

    assert state.framing_approved is True
    assert (case.root / "shared" / "framing_approval.yaml").exists()
    assert load_case_state(case).framing_approved is True
    assert "control_checkpoint_signed" in _event_types(case)


def test_the_case_reaches_the_final_gate_after_framing_approval(env: Path) -> None:
    case = _started(env)
    _approve_framing(case)
    _run(case)

    assert load_case_state(case).stage is CaseStage.AWAITING_FINAL_APPROVAL


def test_final_approval_writes_the_second_gate_record(env: Path) -> None:
    """The gap this spec closes: the final gate used to leave no artifact at all."""
    case = _started(env)
    _approve_framing(case)
    _run(case)

    state = control.approve_final(
        case,
        FinalApproval(
            decision=FinalDecision.ACCEPT,
            approved_by="tester",
            approved_at=datetime.now(UTC),
        ),
    )

    approval_path = case.root / "outputs" / "final_approval.yaml"
    assert approval_path.exists()
    assert state.final_approved is True


def test_the_full_lifecycle_reaches_done(env: Path) -> None:
    case = _started(env)
    _approve_framing(case)
    _run(case)
    _accept_final(case)
    _run(case)

    assert load_case_state(case).stage is CaseStage.DONE


# --- gate protection ---------------------------------------------------------------


def test_framing_approval_at_the_wrong_stage_is_refused(env: Path) -> None:
    case = _started(env)
    _approve_framing(case)
    _run(case)  # now at the final gate

    with pytest.raises(control.WrongStage) as excinfo:
        _approve_framing(case)
    assert "framing approval" in str(excinfo.value)


def test_final_approval_at_the_wrong_stage_is_refused(env: Path) -> None:
    case = _started(env)  # at the framing gate

    with pytest.raises(control.WrongStage):
        _accept_final(case)


def test_a_revise_decision_requires_a_note(env: Path) -> None:
    with pytest.raises(ValidationError):
        FinalApproval(
            decision=FinalDecision.REVISE,
            approved_by="tester",
            approved_at=datetime.now(UTC),
        )

    accepted = FinalApproval(
        decision=FinalDecision.REVISE,
        approved_by="tester",
        approved_at=datetime.now(UTC),
        note="The downside case is not addressed.",
    )
    assert accepted.note


# --- status ------------------------------------------------------------------------


def test_status_reports_the_gate_the_case_waits_on(env: Path) -> None:
    case = _started(env)
    status = control.case_status(case)

    assert status.stage is CaseStage.AWAITING_FRAMING_APPROVAL
    assert status.awaiting == "framing approval"
    assert status.is_running is False
    assert status.is_terminal is False
    assert sum(status.task_counts.values()) >= 0


def test_status_reports_a_live_run(env: Path) -> None:
    case = _started(env)
    with case_lock(case):
        status = control.case_status(case)
        assert status.is_running is True


def test_status_reports_terminal_cases(env: Path) -> None:
    case = _started(env)
    state = load_case_state(case)
    save_case_state(case, state.model_copy(update={"stage": CaseStage.DONE}))

    assert control.case_status(case).is_terminal is True


# --- resume guards -----------------------------------------------------------------


def test_resume_is_refused_at_a_gate(env: Path) -> None:
    case = _started(env)
    with pytest.raises(control.WrongStage):
        control.resume_allowed(case)


def test_resume_is_refused_when_done(env: Path) -> None:
    case = _started(env)
    state = load_case_state(case)
    save_case_state(case, state.model_copy(update={"stage": CaseStage.DONE}))

    with pytest.raises(control.WrongStage):
        control.resume_allowed(case)


def test_resume_is_allowed_mid_run(env: Path) -> None:
    case = _started(env)
    state = load_case_state(case)
    save_case_state(case, state.model_copy(update={"stage": CaseStage.INVESTIGATION}))

    assert control.resume_allowed(case).stage is CaseStage.INVESTIGATION


def test_pause_reports_nothing_to_stop(env: Path) -> None:
    case = _started(env)
    assert control.pause(case) is False
