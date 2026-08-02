"""Synchronous control layer over the case store and pipeline (SPEC-027).

Every function is lock-guarded: a mutation attempted while a worker holds the
lock raises :class:`~orchestrator.supervisor.CaseLocked`.  Approval writes go
through ``save_case_state`` (atomic) after the artifact write, so a crash
between the two leaves an artifact without a flag — recoverable — never a flag
without a record.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel

from orchestrator.artifacts import (
    AuditEvent,
    FinalApproval,
    FramingApproval,
    TaskRecord,
    TaskStatus,
)
from orchestrator.budget import BudgetConfig
from orchestrator.case_store import Case, create_case, default_cases_root, load_case
from orchestrator.pipeline import DEFAULT_BUDGET, SMALL_BUDGET
from orchestrator.state_machine import (
    CaseStage,
    CaseState,
    load_case_state,
    save_case_state,
)
from orchestrator.supervisor import CaseLocked, RunLock
from orchestrator.supervisor import stop as supervisor_stop

_BUDGET_PROFILES: dict[str, BudgetConfig] = {
    "default": DEFAULT_BUDGET,
    "small": SMALL_BUDGET,
}

_META_FILENAME = "control_meta.yaml"


class ControlStatus(BaseModel):
    """Snapshot of a case's control-plane state."""

    case_id: str
    stage: CaseStage
    awaiting_approval: str | None
    worker_running: bool
    failure_cause: str | None


class WorkerFailed(RuntimeError):
    """Raised when the worker subprocess exits with a nonzero code."""

    def __init__(self, case_id: str, exit_code: int, stderr: str) -> None:
        self.case_id = case_id
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(f"Worker for {case_id} exited with code {exit_code}. stderr:\n{stderr}")


class ResumeBlocked(RuntimeError):
    """Raised when resume is refused due to orphaned active tasks."""

    def __init__(self, case_id: str, active_task_ids: list[str]) -> None:
        self.case_id = case_id
        self.active_task_ids = active_task_ids
        super().__init__(
            f"Cannot resume {case_id}: {len(active_task_ids)} orphaned active task(s) "
            f"remain ({', '.join(active_task_ids)}). Safe-resume reconciliation is SPEC-030."
        )


# ── helpers ──────────────────────────────────────────────────────────────────


def _resolve_root(cases_root: Path | None) -> Path:
    return cases_root or default_cases_root()


def _audit(case: Case, event_type: str, payload: dict[str, object]) -> None:
    case.audit(
        AuditEvent(
            ts=datetime.now(UTC),
            actor="control",
            event_type=event_type,
            payload=payload,
        )
    )


def _write_meta(case: Case, raw_prompt: str, budget_profile: str, depth: str | None) -> None:
    meta_path = case.root / "shared" / _META_FILENAME
    payload = {"raw_prompt": raw_prompt, "budget_profile": budget_profile}
    if depth is not None:
        payload["depth"] = depth
    meta_path.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")


def _spawn_worker(case_id: str, cases_root: Path) -> subprocess.Popen[str]:
    """Start ``python -m orchestrator.worker <case-id>`` in a new session."""
    env = os.environ.copy()
    env["AGENTADVISOR_CASES_ROOT"] = str(cases_root)
    return subprocess.Popen(
        [sys.executable, "-m", "orchestrator.worker", case_id],
        start_new_session=True,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _run_worker_to_halt(case_id: str, cases_root: Path) -> None:
    """Start a worker and block until it exits.

    Raises :class:`WorkerFailed` on nonzero exit.
    """
    process = _spawn_worker(case_id, cases_root)
    _stdout, stderr = process.communicate()
    if process.returncode != 0:
        raise WorkerFailed(case_id, process.returncode, stderr)


def _awaiting(state: CaseState) -> str | None:
    if state.stage is CaseStage.AWAITING_FRAMING_APPROVAL:
        return "framing"
    if state.stage is CaseStage.AWAITING_FINAL_APPROVAL:
        return "final"
    return None


def _has_active_tasks(case: Case) -> list[str]:
    """Return task_ids of tasks in 'active' status (orphaned after a kill)."""
    return [
        record.task_id
        for record in case.list_artifacts(TaskRecord)
        if record.status is TaskStatus.ACTIVE
    ]


# ── public control functions ─────────────────────────────────────────────────


def new_case(
    raw_prompt: str,
    *,
    slug: str,
    budget_profile: str = "default",
    depth: str | None = None,
    cases_root: Path | None = None,
) -> str:
    """Create a case, start a worker, and block until the first halt.

    Returns the case_id.  The case will be parked at
    ``awaiting_framing_approval`` when this function returns.
    """
    root = _resolve_root(cases_root)
    case = create_case(slug, cases_root=root)
    case_id = case.root.name

    _write_meta(case, raw_prompt, budget_profile, depth)
    _audit(case, "control_case_created", {"case_id": case_id, "slug": slug})
    _audit(case, "control_run_started", {"case_id": case_id, "pid": None})
    _run_worker_to_halt(case_id, root)

    return case_id


def case_status(
    case_id: str,
    *,
    cases_root: Path | None = None,
) -> ControlStatus:
    """Return the current control-plane status of a case."""
    root = _resolve_root(cases_root)
    case = load_case(case_id, cases_root=root)
    state = load_case_state(case)
    lock = RunLock(case.root)

    return ControlStatus(
        case_id=case_id,
        stage=state.stage,
        awaiting_approval=_awaiting(state),
        worker_running=lock.is_held(),
        failure_cause=state.failure_cause,
    )


def approve_framing(
    case_id: str,
    approval: FramingApproval,
    *,
    cases_root: Path | None = None,
) -> None:
    """Write the framing approval, set the flag, and restart the worker.

    Only ``decision: approve`` is handled here; revision decisions are SPEC-028.
    """
    root = _resolve_root(cases_root)
    case = load_case(case_id, cases_root=root)
    state = load_case_state(case)

    if state.stage is not CaseStage.AWAITING_FRAMING_APPROVAL:
        raise ValueError(
            f"Case {case_id} is at stage '{state.stage.value}', not 'awaiting_framing_approval'."
        )

    lock = RunLock(case.root)
    lock.acquire()
    try:
        case.write_artifact(approval)
        state = state.model_copy(update={"framing_approved": True})
        save_case_state(case, state)
        _audit(
            case,
            "control_checkpoint_signed",
            {
                "gate": "framing",
                "decision": approval.decision.value,
                "approved_by": approval.approved_by,
            },
        )
    finally:
        lock.release()

    _audit(case, "control_run_started", {"case_id": case_id})
    _run_worker_to_halt(case_id, root)


def approve_final(
    case_id: str,
    approval: FinalApproval,
    *,
    cases_root: Path | None = None,
) -> None:
    """Write the final approval, set the flag, and restart the worker to completion."""
    root = _resolve_root(cases_root)
    case = load_case(case_id, cases_root=root)
    state = load_case_state(case)

    if state.stage is not CaseStage.AWAITING_FINAL_APPROVAL:
        raise ValueError(
            f"Case {case_id} is at stage '{state.stage.value}', not 'awaiting_final_approval'."
        )

    lock = RunLock(case.root)
    lock.acquire()
    try:
        case.write_artifact(approval)
        state = state.model_copy(update={"final_approved": True})
        save_case_state(case, state)
        _audit(
            case,
            "control_checkpoint_signed",
            {
                "gate": "final",
                "decision": approval.decision.value,
                "approved_by": approval.approved_by,
            },
        )
    finally:
        lock.release()

    _audit(case, "control_run_started", {"case_id": case_id})
    _run_worker_to_halt(case_id, root)


def pause(
    case_id: str,
    *,
    cases_root: Path | None = None,
) -> None:
    """Stop the worker process group and remove the lock."""
    root = _resolve_root(cases_root)
    case = load_case(case_id, cases_root=root)
    supervisor_stop(case_id, root)
    _audit(case, "control_run_stopped", {"case_id": case_id})


def resume(
    case_id: str,
    *,
    cases_root: Path | None = None,
) -> None:
    """Restart a worker for a parked or interrupted case.

    Refuses cases with orphaned ``active`` tasks (safe-resume is SPEC-030).
    """
    root = _resolve_root(cases_root)
    case = load_case(case_id, cases_root=root)
    state = load_case_state(case)

    if state.stage in (CaseStage.DONE, CaseStage.FAILED):
        raise ValueError(f"Case {case_id} is at terminal stage '{state.stage.value}'.")

    orphaned = _has_active_tasks(case)
    if orphaned:
        _audit(
            case,
            "control_interrupted_detected",
            {"case_id": case_id, "orphaned_tasks": orphaned},
        )
        raise ResumeBlocked(case_id, orphaned)

    # Reclaim a stale lock if present.
    lock = RunLock(case.root)
    if lock.is_stale():
        lock.release()
    if lock.is_held():
        raise CaseLocked(case_id, lock.holder_pid() or -1, lock.age_s())

    _audit(case, "control_run_started", {"case_id": case_id})
    _run_worker_to_halt(case_id, root)
