"""Single-writer enforcement and interrupted-run detection (SPEC-027)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from orchestrator.case_store import Case, create_case
from orchestrator.state_machine import CaseStage, load_case_state, save_case_state
from orchestrator.supervisor import (
    CaseLocked,
    case_lock,
    interrupted_cases,
    is_running,
    lock_path,
    release,
    running_pid,
    stop,
)


@pytest.fixture
def case(tmp_path: Path) -> Case:
    return create_case("supervisor", cases_root=tmp_path)


def _set_stage(case: Case, stage: CaseStage) -> None:
    state = load_case_state(case)
    save_case_state(case, state.model_copy(update={"stage": stage}))


def _write_lock(case: Case, pid: int, *, age_s: float = 0.0) -> None:
    started = datetime.now(UTC) - timedelta(seconds=age_s)
    lock_path(case).write_text(
        json.dumps({"pid": pid, "started_at": started.isoformat()}), encoding="utf-8"
    )


def test_lock_is_taken_and_released(case: Case) -> None:
    assert not is_running(case)
    with case_lock(case):
        assert lock_path(case).exists()
        assert running_pid(case) == os.getpid()
    assert not lock_path(case).exists()
    assert not is_running(case)


def test_second_holder_is_refused_and_told_who_holds_it(case: Case) -> None:
    with case_lock(case), pytest.raises(CaseLocked) as excinfo:
        with case_lock(case):
            pass

    assert excinfo.value.holder_pid == os.getpid()
    assert str(os.getpid()) in str(excinfo.value)


def test_lock_survives_an_exception_inside_the_block(case: Case) -> None:
    with pytest.raises(RuntimeError), case_lock(case):
        raise RuntimeError("boom")
    assert not lock_path(case).exists()


def test_a_dead_holder_is_reclaimed(case: Case) -> None:
    """A killed run must not wedge a case forever."""
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    _write_lock(case, dead.pid, age_s=42.0)

    assert running_pid(case) is None
    assert not is_running(case)

    with case_lock(case):
        assert running_pid(case) == os.getpid()


def test_a_malformed_lock_counts_as_absent(case: Case) -> None:
    lock_path(case).write_text("not json at all", encoding="utf-8")
    assert running_pid(case) is None
    with case_lock(case):
        assert running_pid(case) == os.getpid()


def test_stop_returns_false_when_nothing_runs(case: Case) -> None:
    assert stop(case) is False


def test_stop_kills_the_live_holder_and_clears_the_lock(case: Case) -> None:
    child = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", "import time; time.sleep(30)"],
        start_new_session=True,
    )
    try:
        _write_lock(case, child.pid)
        assert is_running(case)

        assert stop(case, timeout_s=5.0) is True
        assert not lock_path(case).exists()

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and child.poll() is None:
            time.sleep(0.05)
        assert child.poll() is not None
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


def test_release_is_idempotent(case: Case) -> None:
    release(case)
    release(case)
    assert not lock_path(case).exists()


def test_an_active_stage_with_no_worker_is_interrupted(case: Case, tmp_path: Path) -> None:
    _set_stage(case, CaseStage.INVESTIGATION)
    assert interrupted_cases(tmp_path) == [case.root.name]


def test_a_gate_parked_case_is_waiting_not_interrupted(case: Case, tmp_path: Path) -> None:
    _set_stage(case, CaseStage.AWAITING_FRAMING_APPROVAL)
    assert interrupted_cases(tmp_path) == []

    _set_stage(case, CaseStage.AWAITING_FINAL_APPROVAL)
    assert interrupted_cases(tmp_path) == []


def test_terminal_cases_are_not_interrupted(case: Case, tmp_path: Path) -> None:
    for stage in (CaseStage.DONE, CaseStage.FAILED):
        _set_stage(case, stage)
        assert interrupted_cases(tmp_path) == []


def test_a_running_case_is_not_interrupted(case: Case, tmp_path: Path) -> None:
    _set_stage(case, CaseStage.INVESTIGATION)
    with case_lock(case):
        assert interrupted_cases(tmp_path) == []


def test_interrupted_cases_tolerates_a_missing_root(tmp_path: Path) -> None:
    assert interrupted_cases(tmp_path / "nope") == []
