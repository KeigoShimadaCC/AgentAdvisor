"""Tests for the run supervisor (SPEC-027): lockfile, stale detection, stop, interrupted_cases."""

from __future__ import annotations

import json
import os
import signal
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from orchestrator.case_store import Case, create_case
from orchestrator.state_machine import CaseStage, CaseState, save_case_state
from orchestrator.supervisor import (
    CaseLocked,
    RunLock,
    interrupted_cases,
    is_running,
    stop,
)


@pytest.fixture
def cases_root(tmp_path: Path) -> Path:
    root = tmp_path / "cases"
    root.mkdir()
    return root


@pytest.fixture
def case(cases_root: Path) -> Case:
    return create_case("test-supervisor", cases_root=cases_root)


class TestRunLock:
    def test_acquire_and_release(self, case: Case) -> None:
        lock = RunLock(case.root)
        assert not lock.exists()
        lock.acquire()
        assert lock.exists()
        assert lock.is_held()
        lock.release()
        assert not lock.exists()

    def test_acquire_raises_when_held(self, case: Case) -> None:
        lock = RunLock(case.root)
        lock.acquire()
        with pytest.raises(CaseLocked) as exc_info:
            lock.acquire()
        assert exc_info.value.holder_pid == os.getpid()
        lock.release()

    def test_stale_lock_is_reclaimed(self, case: Case) -> None:
        lock = RunLock(case.root)
        # Write a lockfile with a dead pid.
        payload = json.dumps(
            {"pid": 999_999, "started_at": datetime.now(UTC).isoformat()},
            separators=(",", ":"),
        )
        (case.root / ".run.lock").write_text(payload, encoding="utf-8")
        assert lock.is_stale()
        assert not lock.is_held()
        # acquire() should reclaim the stale lock.
        lock.acquire()
        assert lock.is_held()
        lock.release()

    def test_corrupt_lockfile_is_stale(self, case: Case) -> None:
        lock = RunLock(case.root)
        (case.root / ".run.lock").write_text("not json", encoding="utf-8")
        assert lock.is_stale()
        lock.acquire()
        lock.release()

    def test_holder_pid(self, case: Case) -> None:
        lock = RunLock(case.root)
        lock.acquire()
        assert lock.holder_pid() == os.getpid()
        lock.release()
        assert lock.holder_pid() is None

    def test_age_s(self, case: Case) -> None:
        lock = RunLock(case.root)
        lock.acquire()
        age = lock.age_s()
        assert 0.0 <= age < 5.0
        lock.release()


class TestIsRunning:
    def test_not_running_when_no_lock(self, case: Case) -> None:
        assert not is_running(case.root.name, cases_root=case.root.parent)

    def test_running_when_lock_held(self, case: Case) -> None:
        lock = RunLock(case.root)
        lock.acquire()
        assert is_running(case.root.name, cases_root=case.root.parent)
        lock.release()
        assert not is_running(case.root.name, cases_root=case.root.parent)

    def test_not_running_when_stale(self, case: Case) -> None:
        payload = json.dumps(
            {"pid": 999_999, "started_at": datetime.now(UTC).isoformat()},
            separators=(",", ":"),
        )
        (case.root / ".run.lock").write_text(payload, encoding="utf-8")
        assert not is_running(case.root.name, cases_root=case.root.parent)


class TestStop:
    def test_stop_returns_false_for_no_lock(self, case: Case) -> None:
        result = stop(case.root.name, cases_root=case.root.parent)
        assert result is False
        assert not (case.root / ".run.lock").exists()

    def test_stop_returns_false_for_stale_lock(self, case: Case) -> None:
        payload = json.dumps(
            {"pid": 999_999, "started_at": datetime.now(UTC).isoformat()},
            separators=(",", ":"),
        )
        (case.root / ".run.lock").write_text(payload, encoding="utf-8")
        result = stop(case.root.name, cases_root=case.root.parent)
        assert result is False
        assert not (case.root / ".run.lock").exists()

    def test_stop_kills_live_worker(self, case: Case) -> None:
        # Start a subprocess in its own session so pgid == pid.
        proc = subprocess.Popen(
            ["sleep", "30"],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            # Write the lockfile with the subprocess's pid.
            payload = json.dumps(
                {"pid": proc.pid, "started_at": datetime.now(UTC).isoformat()},
                separators=(",", ":"),
            )
            (case.root / ".run.lock").write_text(payload, encoding="utf-8")

            result = stop(case.root.name, cases_root=case.root.parent)
            assert result is True
            assert not (case.root / ".run.lock").exists()

            # The process should be dead.
            proc.wait(timeout=5)
            assert proc.returncode == -signal.SIGKILL
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


class TestInterruptedCases:
    def test_empty_root(self, tmp_path: Path) -> None:
        root = tmp_path / "empty"
        root.mkdir()
        assert interrupted_cases(root) == []

    def test_finds_stale_lock_in_active_stage(self, case: Case) -> None:
        # Set the case to an active (non-gate, non-terminal) stage.
        now = datetime.now(UTC)
        state = CaseState(
            case_id=case.root.name,
            stage=CaseStage.INVESTIGATION,
            created_at=now,
            updated_at=now,
        )
        save_case_state(case, state)

        # Write a stale lockfile.
        payload = json.dumps(
            {"pid": 999_999, "started_at": datetime.now(UTC).isoformat()},
            separators=(",", ":"),
        )
        (case.root / ".run.lock").write_text(payload, encoding="utf-8")

        result = interrupted_cases(case.root.parent)
        assert case.root.name in result

    def test_ignores_done_case(self, case: Case) -> None:
        now = datetime.now(UTC)
        state = CaseState(
            case_id=case.root.name,
            stage=CaseStage.DONE,
            created_at=now,
            updated_at=now,
        )
        save_case_state(case, state)

        payload = json.dumps(
            {"pid": 999_999, "started_at": datetime.now(UTC).isoformat()},
            separators=(",", ":"),
        )
        (case.root / ".run.lock").write_text(payload, encoding="utf-8")

        result = interrupted_cases(case.root.parent)
        assert case.root.name not in result

    def test_ignores_case_without_stale_lock(self, case: Case) -> None:
        now = datetime.now(UTC)
        state = CaseState(
            case_id=case.root.name,
            stage=CaseStage.INVESTIGATION,
            created_at=now,
            updated_at=now,
        )
        save_case_state(case, state)
        # No lockfile at all.
        result = interrupted_cases(case.root.parent)
        assert case.root.name not in result

    def test_ignores_case_with_live_lock(self, case: Case) -> None:
        now = datetime.now(UTC)
        state = CaseState(
            case_id=case.root.name,
            stage=CaseStage.INVESTIGATION,
            created_at=now,
            updated_at=now,
        )
        save_case_state(case, state)

        lock = RunLock(case.root)
        lock.acquire()
        result = interrupted_cases(case.root.parent)
        assert case.root.name not in result
        lock.release()
