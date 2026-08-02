"""One writer per case, enforced across processes.

``case_store`` guarantees thread safety within a process and explicitly leaves
cross-process coordination out of scope. That was fine while a case only ever ran from a
single blocking ``advisor`` invocation. Once a web service can start a run while a CLI is
open on the same case, two writers would interleave ``audit.jsonl`` and race
``counters.yaml``, so the case directory carries an advisory lock.

The lock is self-healing: a lockfile whose recorded pid is no longer alive is stale and is
reclaimed, because a killed run must not wedge a case forever.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from orchestrator.case_store import Case, default_cases_root
from orchestrator.state_machine import CaseStage, load_case_state

LOCK_FILENAME = ".run.lock"

#: Stages where a case is legitimately idle: waiting for a person, or over.
_IDLE_STAGES = frozenset(
    {
        CaseStage.AWAITING_FRAMING_APPROVAL,
        CaseStage.AWAITING_FINAL_APPROVAL,
        CaseStage.DONE,
        CaseStage.FAILED,
    }
)

_STOP_POLL_S = 0.05


class CaseLocked(Exception):
    """Another process holds the case lock."""

    def __init__(self, case_id: str, holder_pid: int, age_s: float) -> None:
        super().__init__(
            f"Case {case_id} is already being run by process {holder_pid} "
            f"(started {age_s:.0f}s ago). Wait for it to finish, or stop it first."
        )
        self.case_id = case_id
        self.holder_pid = holder_pid
        self.age_s = age_s


@dataclass(frozen=True)
class LockHolder:
    pid: int
    started_at: datetime

    @property
    def age_s(self) -> float:
        return (datetime.now(UTC) - self.started_at).total_seconds()


def lock_path(case: Case) -> Path:
    return case.root / LOCK_FILENAME


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # The process exists but belongs to someone else.
        return True
    return True


def _read_holder(case: Case) -> LockHolder | None:
    path = lock_path(case)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return LockHolder(
            pid=int(payload["pid"]),
            started_at=datetime.fromisoformat(str(payload["started_at"])),
        )
    except (KeyError, TypeError, ValueError):
        return None


def running_pid(case: Case) -> int | None:
    """The pid of the live process running this case, if any.

    A lockfile that is unreadable, malformed, or owned by a dead pid counts as absent: it
    is the residue of a crash, not a running worker.
    """
    holder = _read_holder(case)
    if holder is None:
        return None
    if not _pid_alive(holder.pid):
        return None
    return holder.pid


def is_running(case: Case) -> bool:
    return running_pid(case) is not None


def _write_lock(case: Case, pid: int) -> None:
    payload = json.dumps({"pid": pid, "started_at": datetime.now(UTC).isoformat()})
    lock_path(case).write_text(payload, encoding="utf-8")


def _claim(case: Case, pid: int) -> None:
    """Create the lockfile, reclaiming it if the recorded holder is gone."""
    path = lock_path(case)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        holder = _read_holder(case)
        if holder is not None and _pid_alive(holder.pid):
            raise CaseLocked(case.root.name, holder.pid, holder.age_s) from None
        # Stale: the writer died without releasing. Take it over.
        _write_lock(case, pid)
        return
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"pid": pid, "started_at": datetime.now(UTC).isoformat()}, fh)


def release(case: Case) -> None:
    lock_path(case).unlink(missing_ok=True)


@contextmanager
def case_lock(case: Case, *, pid: int | None = None) -> Iterator[None]:
    """Hold the case's single-writer lock for the duration of the block."""
    _claim(case, pid if pid is not None else os.getpid())
    try:
        yield
    finally:
        release(case)


def start_worker(
    case: Case,
    *,
    budget_profile: str = "default",
    cases_root: Path | None = None,
) -> int:
    """Run the case in a detached worker process and return its pid.

    The worker takes the lock itself, so a caller that wants to know whether the run
    actually started should poll :func:`is_running` rather than assume the spawn implies
    ownership.
    """
    argv = [
        sys.executable,
        "-m",
        "orchestrator.worker",
        case.root.name,
        "--budget-profile",
        budget_profile,
    ]
    root = cases_root if cases_root is not None else case.root.parent
    argv += ["--cases-root", str(root)]
    process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
        argv,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return process.pid


def stop(case: Case, *, timeout_s: float = 10.0) -> bool:
    """Stop the process running this case. Returns True if something was stopped.

    The whole process group is signalled, because a run's real work happens in
    ``cursor-agent`` subprocesses that would otherwise outlive their parent.
    """
    pid = running_pid(case)
    if pid is None:
        release(case)
        return False

    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        release(case)
        return False

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            break
        time.sleep(_STOP_POLL_S)
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    release(case)
    return True


def interrupted_cases(cases_root: Path | None = None) -> list[str]:
    """Case ids that were mid-run when their process disappeared.

    A case parked at an approval gate is waiting, not interrupted, and a finished or
    failed case is neither.
    """
    root = cases_root if cases_root is not None else default_cases_root()
    if not root.exists():
        return []

    interrupted: list[str] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or not (entry / "state.yaml").exists():
            continue
        case = Case(root=entry)
        try:
            state = load_case_state(case)
        except Exception:  # noqa: BLE001 - a corrupt case must not hide the healthy ones
            continue
        if state.stage in _IDLE_STAGES:
            continue
        if is_running(case):
            continue
        interrupted.append(state.case_id)
    return interrupted
