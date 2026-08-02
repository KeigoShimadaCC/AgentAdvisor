"""Run supervisor: lockfile-based single-writer enforcement and worker lifecycle.

Every case has at most one worker process at a time.  The lockfile
(``<case_root>/.run.lock``) is created with ``O_CREAT|O_EXCL`` and contains
``{"pid": <int>, "started_at": <iso8601>}``.  Staleness is defined as the
recorded pid no longer being alive, which happens when a worker is killed
(SIGKILL, OOM, power loss) before it can release the lock.
"""

from __future__ import annotations

import json
import os
import signal
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orchestrator.case_store import Case, default_cases_root
from orchestrator.state_machine import ACTIVE_STAGES, load_case_state

_LOCK_FILENAME = ".run.lock"
_KILL_WAIT_TIMEOUT_S = 5.0
_KILL_POLL_INTERVAL_S = 0.1


class CaseLocked(Exception):
    """Raised when a control mutation is attempted on a case with a live worker."""

    def __init__(self, case_id: str, holder_pid: int, age_s: float) -> None:
        self.case_id = case_id
        self.holder_pid = holder_pid
        self.age_s = age_s
        super().__init__(
            f"Case {case_id} is locked by worker pid {holder_pid} (held for {age_s:.0f}s)."
        )


def _lock_path(case_root: Path) -> Path:
    return case_root / _LOCK_FILENAME


def _pid_alive(pid: int) -> bool:
    """Return True if *pid* is currently running on the host."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we lack permission to signal it.
        return True
    except OSError:
        return False
    return True


class RunLock:
    """Advisory lockfile guarding a single worker per case.

    The lockfile lives at ``<case_root>/.run.lock`` and contains a JSON object
    with the holder's pid and the start timestamp.  It is created atomically
    with ``O_CREAT | O_EXCL`` so that two processes racing to acquire it cannot
    both succeed.
    """

    def __init__(self, case_root: Path) -> None:
        self._path = _lock_path(case_root)
        self._case_root = case_root

    @property
    def path(self) -> Path:
        return self._path

    # ── reading ──────────────────────────────────────────────────────────────

    def exists(self) -> bool:
        return self._path.exists()

    def _read(self) -> dict[str, Any] | None:
        if not self._path.exists():
            return None
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(data, dict):
            return None
        return data

    def holder_pid(self) -> int | None:
        data = self._read()
        if data is None:
            return None
        pid = data.get("pid")
        if not isinstance(pid, int):
            return None
        return pid

    def _started_at(self) -> datetime | None:
        data = self._read()
        if data is None:
            return None
        started = data.get("started_at")
        if not isinstance(started, str):
            return None
        try:
            return datetime.fromisoformat(started)
        except ValueError:
            return None

    def age_s(self) -> float:
        started = self._started_at()
        if started is None:
            return 0.0
        return (datetime.now(UTC) - started).total_seconds()

    # ── predicates ───────────────────────────────────────────────────────────

    def is_stale(self) -> bool:
        """True if the lockfile exists but the holder pid is dead."""
        if not self.exists():
            return False
        pid = self.holder_pid()
        if pid is None:
            return True  # corrupt lockfile
        return not _pid_alive(pid)

    def is_held(self) -> bool:
        """True if the lockfile exists and the holder is alive."""
        return self.exists() and not self.is_stale()

    # ── mutations ────────────────────────────────────────────────────────────

    def acquire(self) -> None:
        """Create the lockfile with the current pid.

        Raises :class:`CaseLocked` if a live worker already holds the lock.
        A stale lock (dead pid) is reclaimed silently.
        """
        if self.is_held():
            pid = self.holder_pid() or -1
            raise CaseLocked(self._case_root.name, pid, self.age_s())

        # Remove a stale lock if present.
        if self.exists():
            self._path.unlink(missing_ok=True)

        payload = json.dumps(
            {
                "pid": os.getpid(),
                "started_at": datetime.now(UTC).isoformat(),
            },
            separators=(",", ":"),
        )
        try:
            fd = os.open(
                str(self._path),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o644,
            )
        except FileExistsError:
            # Lost the race — another process acquired it between our check and
            # the O_EXCL open.
            pid = self.holder_pid() or -1
            raise CaseLocked(self._case_root.name, pid, 0.0) from None
        try:
            os.write(fd, payload.encode("utf-8"))
        finally:
            os.close(fd)

    def release(self) -> None:
        """Remove the lockfile (idempotent)."""
        self._path.unlink(missing_ok=True)


# ── module-level helpers ─────────────────────────────────────────────────────


def _resolve_root(cases_root: Path | None) -> Path:
    return cases_root or default_cases_root()


def is_running(case_id: str, cases_root: Path | None = None) -> bool:
    """Return True if a live worker currently holds the lock for *case_id*."""
    root = _resolve_root(cases_root)
    return RunLock(root / case_id).is_held()


def stop(case_id: str, cases_root: Path | None = None) -> bool:
    """SIGKILL the worker process group for *case_id* and remove the lock.

    Returns ``True`` if a live worker was killed, ``False`` if the lock was
    already stale or absent.
    """
    root = _resolve_root(cases_root)
    lock = RunLock(root / case_id)

    pid = lock.holder_pid()
    if pid is None or not _pid_alive(pid):
        lock.release()
        return False

    # The worker uses ``start_new_session=True`` so its pgid == pid.
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        lock.release()
        return False

    # Wait briefly for the process to actually die.
    deadline = time.monotonic() + _KILL_WAIT_TIMEOUT_S
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            break
        time.sleep(_KILL_POLL_INTERVAL_S)

    lock.release()
    return True


def interrupted_cases(cases_root: Path | None = None) -> list[str]:
    """Return case_ids whose stage is active, whose lock is stale (dead pid).

    A case qualifies when:
    - ``state.yaml`` exists and parses,
    - the stage is in :data:`~orchestrator.state_machine.ACTIVE_STAGES`,
    - a lockfile exists but the recorded pid is no longer alive.
    """
    root = _resolve_root(cases_root)
    if not root.exists():
        return []

    result: list[str] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if not (entry / "state.yaml").exists():
            continue
        try:
            state = load_case_state(Case(root=entry))
        except Exception:  # noqa: BLE001 - corrupt state must not hide others
            continue

        if state.stage not in ACTIVE_STAGES:
            continue

        lock = RunLock(entry)
        if lock.is_stale():
            result.append(entry.name)

    return result
