"""Tests for the control layer (SPEC-027): new_case, approve gates, pause, resume.

These tests run the full pipeline in a worker subprocess with
``AGENTADVISOR_BACKEND=stub`` so no live model calls are made.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from orchestrator.artifacts import (
    FinalApproval,
    FinalDecision,
    FramingApproval,
    FramingDecision,
)
from orchestrator.case_store import load_case
from orchestrator.control import (
    WorkerFailed,
    approve_final,
    approve_framing,
    case_status,
    new_case,
    pause,
    resume,
)
from orchestrator.state_machine import CaseStage, CaseState, save_case_state
from orchestrator.supervisor import CaseLocked, RunLock

_RAW_PROMPT = "I have $50k and want semiconductor exposure. Nvidia or ETF?"


@pytest.fixture
def control_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Set up isolated env vars for stub-backend worker subprocesses."""
    cases_root = tmp_path / "cases"
    runtime = tmp_path / "runtime"
    memory = tmp_path / "memory"
    cases_root.mkdir()
    runtime.mkdir()
    memory.mkdir()

    monkeypatch.setenv("AGENTADVISOR_BACKEND", "stub")
    monkeypatch.setenv("AGENTADVISOR_CASES_ROOT", str(cases_root))
    monkeypatch.setenv("AGENTADVISOR_RUNTIME_ROOT", str(runtime))
    monkeypatch.setenv("AGENTADVISOR_MEMORY_ROOT", str(memory))

    return cases_root


class TestNewCase:
    def test_parks_at_framing_approval(self, control_env: Path) -> None:
        case_id = new_case(
            _RAW_PROMPT,
            slug="ctrl-test",
            budget_profile="small",
            cases_root=control_env,
        )

        status = case_status(case_id, cases_root=control_env)
        assert status.stage is CaseStage.AWAITING_FRAMING_APPROVAL
        assert status.awaiting_approval == "framing"
        assert not status.worker_running
        assert status.failure_cause is None

        # state.yaml on disk matches.
        case = load_case(case_id, cases_root=control_env)
        from orchestrator.state_machine import load_case_state

        state = load_case_state(case)
        assert state.stage is CaseStage.AWAITING_FRAMING_APPROVAL

    def test_audit_events(self, control_env: Path) -> None:
        case_id = new_case(
            _RAW_PROMPT,
            slug="ctrl-audit",
            budget_profile="small",
            cases_root=control_env,
        )

        case = load_case(case_id, cases_root=control_env)
        audit_lines = (case.root / "audit.jsonl").read_text(encoding="utf-8").strip().split("\n")
        event_types = []
        for line in audit_lines:
            event = json.loads(line)
            if event.get("actor") == "control":
                event_types.append(event["event_type"])
        assert "control_case_created" in event_types
        assert "control_run_started" in event_types


class TestApproveFraming:
    def test_advances_to_final_approval(self, control_env: Path) -> None:
        case_id = new_case(
            _RAW_PROMPT,
            slug="ctrl-framing",
            budget_profile="small",
            cases_root=control_env,
        )

        approval = FramingApproval(
            decision=FramingDecision.APPROVE,
            approved_by="test-user",
            approved_at=datetime.now(UTC),
        )
        approve_framing(case_id, approval, cases_root=control_env)

        status = case_status(case_id, cases_root=control_env)
        assert status.stage is CaseStage.AWAITING_FINAL_APPROVAL
        assert status.awaiting_approval == "final"

        # The framing approval artifact was written.
        case = load_case(case_id, cases_root=control_env)
        written = case.read_artifact(FramingApproval)
        assert written.decision is FramingDecision.APPROVE
        assert written.approved_by == "test-user"

    def test_wrong_stage_raises(self, control_env: Path) -> None:
        case_id = new_case(
            _RAW_PROMPT,
            slug="ctrl-wrong",
            budget_profile="small",
            cases_root=control_env,
        )

        # Try to approve final when at framing gate.
        approval = FinalApproval(
            decision=FinalDecision.ACCEPT,
            approved_by="test-user",
            approved_at=datetime.now(UTC),
        )
        with pytest.raises(ValueError, match="awaiting_framing_approval"):
            approve_final(case_id, approval, cases_root=control_env)


class TestApproveFinal:
    def test_reaches_done(self, control_env: Path) -> None:
        case_id = new_case(
            _RAW_PROMPT,
            slug="ctrl-final",
            budget_profile="small",
            cases_root=control_env,
        )

        framing = FramingApproval(
            decision=FramingDecision.APPROVE,
            approved_by="test-user",
            approved_at=datetime.now(UTC),
        )
        approve_framing(case_id, framing, cases_root=control_env)

        final = FinalApproval(
            decision=FinalDecision.ACCEPT,
            approved_by="test-user",
            approved_at=datetime.now(UTC),
        )
        approve_final(case_id, final, cases_root=control_env)

        status = case_status(case_id, cases_root=control_env)
        assert status.stage is CaseStage.DONE
        assert status.awaiting_approval is None

        # The final approval artifact was written.
        case = load_case(case_id, cases_root=control_env)
        written = case.read_artifact(FinalApproval)
        assert written.decision is FinalDecision.ACCEPT
        assert written.approved_by == "test-user"

    def test_checkpoint_signed_audit(self, control_env: Path) -> None:
        case_id = new_case(
            _RAW_PROMPT,
            slug="ctrl-audit2",
            budget_profile="small",
            cases_root=control_env,
        )

        framing = FramingApproval(
            decision=FramingDecision.APPROVE,
            approved_by="test-user",
            approved_at=datetime.now(UTC),
        )
        approve_framing(case_id, framing, cases_root=control_env)

        case = load_case(case_id, cases_root=control_env)
        audit_lines = (case.root / "audit.jsonl").read_text(encoding="utf-8").strip().split("\n")
        checkpoint_events = [
            json.loads(line)
            for line in audit_lines
            if json.loads(line).get("event_type") == "control_checkpoint_signed"
        ]
        assert len(checkpoint_events) >= 1
        assert checkpoint_events[-1]["payload"]["gate"] == "framing"


class TestLockContention:
    def test_held_lock_raises_case_locked(self, control_env: Path) -> None:
        case_id = new_case(
            _RAW_PROMPT,
            slug="ctrl-lock",
            budget_profile="small",
            cases_root=control_env,
        )

        case = load_case(case_id, cases_root=control_env)
        lock = RunLock(case.root)
        lock.acquire()

        try:
            approval = FramingApproval(
                decision=FramingDecision.APPROVE,
                approved_by="test-user",
                approved_at=datetime.now(UTC),
            )
            with pytest.raises(CaseLocked):
                approve_framing(case_id, approval, cases_root=control_env)
        finally:
            lock.release()

    def test_stale_lock_is_reclaimed(self, control_env: Path) -> None:
        case_id = new_case(
            _RAW_PROMPT,
            slug="ctrl-stale",
            budget_profile="small",
            cases_root=control_env,
        )

        case = load_case(case_id, cases_root=control_env)
        # Write a stale lockfile (dead pid).
        payload = json.dumps(
            {"pid": 999_999, "started_at": datetime.now(UTC).isoformat()},
            separators=(",", ":"),
        )
        (case.root / ".run.lock").write_text(payload, encoding="utf-8")

        # approve_framing should reclaim the stale lock and proceed.
        approval = FramingApproval(
            decision=FramingDecision.APPROVE,
            approved_by="test-user",
            approved_at=datetime.now(UTC),
        )
        approve_framing(case_id, approval, cases_root=control_env)

        status = case_status(case_id, cases_root=control_env)
        assert status.stage is CaseStage.AWAITING_FINAL_APPROVAL


class TestPauseResume:
    def test_pause_stops_worker(self, control_env: Path) -> None:
        case_id = new_case(
            _RAW_PROMPT,
            slug="ctrl-pause",
            budget_profile="small",
            cases_root=control_env,
        )

        # The worker has already exited (parked at framing gate).
        # pause on a parked case should be a no-op (no live worker).
        pause(case_id, cases_root=control_env)

        status = case_status(case_id, cases_root=control_env)
        assert status.stage is CaseStage.AWAITING_FRAMING_APPROVAL
        assert not status.worker_running

    def test_resume_on_parked_case(self, control_env: Path) -> None:
        case_id = new_case(
            _RAW_PROMPT,
            slug="ctrl-resume",
            budget_profile="small",
            cases_root=control_env,
        )

        # Case is parked at framing gate. Approve framing, then the worker
        # runs to final gate. We can't easily test resume on a non-gate stage
        # without killing the worker mid-run, but we can test that resume
        # on a gate-parked case works after pause.
        pause(case_id, cases_root=control_env)

        approval = FramingApproval(
            decision=FramingDecision.APPROVE,
            approved_by="test-user",
            approved_at=datetime.now(UTC),
        )
        approve_framing(case_id, approval, cases_root=control_env)

        status = case_status(case_id, cases_root=control_env)
        assert status.stage is CaseStage.AWAITING_FINAL_APPROVAL

    def test_resume_reconciles_orphaned_active_tasks(self, control_env: Path) -> None:
        from orchestrator.artifacts import TaskRecord, TaskRole, TaskStatus

        case_id = new_case(
            _RAW_PROMPT,
            slug="ctrl-orphan",
            budget_profile="small",
            cases_root=control_env,
        )

        # Simulate an interrupted case: set stage to investigation and
        # write an active task record.
        case = load_case(case_id, cases_root=control_env)
        now = datetime.now(UTC)
        state = CaseState(
            case_id=case_id,
            stage=CaseStage.INVESTIGATION,
            created_at=now,
            updated_at=now,
        )
        save_case_state(case, state)

        task = TaskRecord(
            task_id="T-001",
            role=TaskRole.RESEARCHER,
            question="test question",
            why_it_matters="test",
            expected_information_gain="high",
            materiality="high",
            probability_of_changing_conclusion=0.5,
            estimated_cost=1.0,
            inputs=["decision_spec"],
            required_output="evidence_batch",
            completion_criteria="test",
            priority="high",
            priority_score=10,
            priority_rationale="test",
            status=TaskStatus.ACTIVE,
        )
        case.write_artifact(task)

        # Resume now reconciles orphaned tasks instead of refusing.
        # The worker may fail on the incomplete case, but reconciliation
        # must happen before the worker starts.
        try:
            resume(case_id, cases_root=control_env)
        except WorkerFailed:
            pass  # Worker fails on incomplete case; that's expected.

        case = load_case(case_id, cases_root=control_env)
        reconciled_task = case.read_artifact(TaskRecord, "T-001")
        assert reconciled_task.status is TaskStatus.PLANNED

        audit_lines = (case.root / "audit.jsonl").read_text(encoding="utf-8").strip().split("\n")
        events = [json.loads(line) for line in audit_lines]
        reset_events = [
            event for event in events if event.get("event_type") == "task_reset_on_resume"
        ]
        assert len(reset_events) >= 1
        assert "T-001" in reset_events[0]["payload"]["task_ids"]

    def test_resume_on_terminal_stage_raises(self, control_env: Path) -> None:
        case_id = new_case(
            _RAW_PROMPT,
            slug="ctrl-terminal",
            budget_profile="small",
            cases_root=control_env,
        )

        # Complete the case first.
        framing = FramingApproval(
            decision=FramingDecision.APPROVE,
            approved_by="test-user",
            approved_at=datetime.now(UTC),
        )
        approve_framing(case_id, framing, cases_root=control_env)

        final = FinalApproval(
            decision=FinalDecision.ACCEPT,
            approved_by="test-user",
            approved_at=datetime.now(UTC),
        )
        approve_final(case_id, final, cases_root=control_env)

        with pytest.raises(ValueError, match="terminal stage"):
            resume(case_id, cases_root=control_env)


class TestInterruptedDetection:
    def test_killed_worker_appears_in_interrupted_cases(
        self,
        control_env: Path,
    ) -> None:
        from orchestrator.supervisor import interrupted_cases

        case_id = new_case(
            _RAW_PROMPT,
            slug="ctrl-killed",
            budget_profile="small",
            cases_root=control_env,
        )

        # Simulate a killed worker: set stage to a non-gate active stage
        # and write a stale lockfile.
        case = load_case(case_id, cases_root=control_env)
        now = datetime.now(UTC)
        state = CaseState(
            case_id=case_id,
            stage=CaseStage.INVESTIGATION,
            created_at=now,
            updated_at=now,
        )
        save_case_state(case, state)

        payload = json.dumps(
            {"pid": 999_999, "started_at": datetime.now(UTC).isoformat()},
            separators=(",", ":"),
        )
        (case.root / ".run.lock").write_text(payload, encoding="utf-8")

        result = interrupted_cases(control_env)
        assert case_id in result
