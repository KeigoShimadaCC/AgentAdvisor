"""The one way to drive a case: create it, sign its gates, run it, read its status.

Every caller goes through this module — the `advisor` CLI today, a web service later — so
gate mechanics exist once. It holds no decision logic: it composes the case store, the
state machine and the pipeline, and records what the user decided.

Two ordering rules matter here. Approval writes the artifact *before* setting the flag, so
a crash between them leaves a recoverable record rather than an unexplained flag. And every
operation that mutates a case takes the case lock, so a CLI and a service can never write
the same case at once.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orchestrator.artifacts import (
    AuditEvent,
    FinalApproval,
    FinalDecision,
    FramingApproval,
    FramingDecision,
    IntakeRecord,
    TaskRecord,
    TaskStatus,
)
from orchestrator.backend import AgentBackend
from orchestrator.budget import BudgetConfig
from orchestrator.case_store import Case, create_case
from orchestrator.pipeline import DEFAULT_BUDGET
from orchestrator.pipeline import run as run_pipeline
from orchestrator.state_machine import (
    MAX_FINAL_REVISIONS,
    MAX_FRAMING_REVISIONS,
    CaseStage,
    CaseState,
    load_case_state,
    save_case_state,
)
from orchestrator.supervisor import case_lock, running_pid

CONTROL_ACTOR = "control"

_GATE_STAGES = {
    CaseStage.AWAITING_FRAMING_APPROVAL: "framing approval",
    CaseStage.AWAITING_FINAL_APPROVAL: "final approval",
}


class ControlError(Exception):
    """A caller mistake: the case cannot do what was asked of it right now."""


class WrongStage(ControlError):
    """The operation needs a stage the case is not in."""

    def __init__(self, case_id: str, stage: CaseStage, expected: str) -> None:
        super().__init__(f"Case {case_id} is at stage '{stage.value}', not {expected}.")
        self.case_id = case_id
        self.stage = stage


class RevisionLimitReached(ControlError):
    """The user has already used every revision this gate allows."""


class MissingPrompt(ControlError):
    """The case has no intake record, so its original prompt is unrecoverable."""


@dataclass(frozen=True)
class ControlStatus:
    """A snapshot of a case, in the terms a caller needs to decide what to do next."""

    case_id: str
    stage: CaseStage
    awaiting: str | None
    running_pid: int | None
    repair_cycle: int
    synthesis_retries: int
    framing_approved: bool
    final_approved: bool
    failure_cause: str | None
    updated_at: datetime
    budget_counters: dict[str, int]
    task_counts: dict[str, int]

    @property
    def is_running(self) -> bool:
        return self.running_pid is not None

    @property
    def is_terminal(self) -> bool:
        return self.stage in (CaseStage.DONE, CaseStage.FAILED)


def awaiting_label(state: CaseState) -> str | None:
    """What the case is waiting for a person to do, in words."""
    return _GATE_STAGES.get(state.stage)


def _audit(case: Case, event_type: str, payload: dict[str, Any]) -> None:
    case.audit(
        AuditEvent(
            ts=datetime.now(UTC),
            actor=CONTROL_ACTOR,
            event_type=event_type,
            payload=payload,
        )
    )


def new_case(
    prompt: str,
    *,
    slug: str = "case",
    cases_root: Path | None = None,
) -> Case:
    """Create a case directory for a decision prompt. Does not run anything."""
    cleaned = prompt.strip()
    if not cleaned:
        raise ControlError("The decision prompt is empty.")

    case = create_case(slug, cases_root=cases_root)
    _audit(case, "control_case_created", {"case_id": case.root.name, "slug": slug})
    return case


def raw_prompt_for(case: Case) -> str:
    """Recover the prompt a case was started with.

    The intake record is the only place the user's words survive verbatim, which is why a
    case cannot be resumed before intake has produced one.
    """
    records = case.list_artifacts(IntakeRecord)
    if not records:
        raise MissingPrompt(
            f"Case {case.root.name} has no intake record yet, so there is nothing to resume."
        )
    return records[0].raw_prompt


def case_status(case: Case) -> ControlStatus:
    state = load_case_state(case)
    counts = {status.value: 0 for status in TaskStatus}
    for record in case.list_artifacts(TaskRecord):
        counts[record.status.value] += 1

    return ControlStatus(
        case_id=state.case_id,
        stage=state.stage,
        awaiting=awaiting_label(state),
        running_pid=running_pid(case),
        repair_cycle=state.repair_cycle,
        synthesis_retries=state.synthesis_retries,
        framing_approved=state.framing_approved,
        final_approved=state.final_approved,
        failure_cause=state.failure_cause,
        updated_at=state.updated_at,
        budget_counters=dict(state.budget_counters),
        task_counts=counts,
    )


def _sign(
    case: Case,
    *,
    expected_stage: CaseStage,
    artifact: FramingApproval | FinalApproval,
    flag: str,
    decision: str,
    extra_updates: dict[str, object] | None = None,
) -> CaseState:
    with case_lock(case):
        state = load_case_state(case)
        if state.stage is not expected_stage:
            raise WrongStage(state.case_id, state.stage, _GATE_STAGES[expected_stage])

        # Artifact first, flag second: a crash in between leaves a record without a flag,
        # which is recoverable, rather than a flag no one can account for.
        case.write_artifact(artifact)
        updates: dict[str, object] = {flag: True}
        updates.update(extra_updates or {})
        state = state.model_copy(update=updates)
        save_case_state(case, state)

        _audit(
            case,
            "control_checkpoint_signed",
            {
                "gate": _GATE_STAGES[expected_stage],
                "decision": decision,
                "approved_by": artifact.approved_by,
            },
        )
        return state


def approve_framing(case: Case, approval: FramingApproval) -> CaseState:
    """Record the user's framing-gate decision and clear the gate."""
    return _sign(
        case,
        expected_stage=CaseStage.AWAITING_FRAMING_APPROVAL,
        artifact=approval,
        flag="framing_approved",
        decision=approval.decision.value,
    )


def approve_final(case: Case, approval: FinalApproval) -> CaseState:
    """Record the user's final-gate decision and clear the gate."""
    return _sign(
        case,
        expected_stage=CaseStage.AWAITING_FINAL_APPROVAL,
        artifact=approval,
        flag="final_approved",
        decision=approval.decision.value,
    )


def request_framing_revision(case: Case, approval: FramingApproval) -> CaseState:
    """Record the user's framing edits and send the case back to be re-framed.

    The gate is released so the pipeline moves, but ``pending_framing_revision`` tells the
    reducer to route backwards to framing rather than onwards to structuring.
    """
    if approval.decision is FramingDecision.APPROVE:
        raise ControlError(
            "A framing revision needs edits or clarification answers. Use approve_framing "
            "to accept the framing as it stands."
        )

    state = load_case_state(case)
    if state.framing_revisions >= MAX_FRAMING_REVISIONS:
        raise RevisionLimitReached(
            f"Case {state.case_id} has already been re-framed {state.framing_revisions} times "
            f"(limit {MAX_FRAMING_REVISIONS}). Approve the framing, or start a new decision."
        )

    return _sign(
        case,
        expected_stage=CaseStage.AWAITING_FRAMING_APPROVAL,
        artifact=approval,
        flag="framing_approved",
        decision=approval.decision.value,
        extra_updates={"pending_framing_revision": True},
    )


def request_final_revision(case: Case, approval: FinalApproval) -> CaseState:
    """Record a send-back at the final gate and route the case through synthesis again."""
    if approval.decision is not FinalDecision.REVISE:
        raise ControlError(
            "A final revision needs decision='revise' and a note saying what to address."
        )

    state = load_case_state(case)
    if state.final_revisions >= MAX_FINAL_REVISIONS:
        raise RevisionLimitReached(
            f"Case {state.case_id} has already been revised {state.final_revisions} time(s) "
            f"(limit {MAX_FINAL_REVISIONS}). Accept the recommendation, or start a new decision."
        )

    return _sign(
        case,
        expected_stage=CaseStage.AWAITING_FINAL_APPROVAL,
        artifact=approval,
        flag="final_approved",
        decision=approval.decision.value,
        extra_updates={"pending_final_revision": True},
    )


def run_to_halt(
    case: Case,
    *,
    raw_prompt: str,
    budget: BudgetConfig | None = None,
    backend: AgentBackend | None = None,
) -> CaseState:
    """Run the case in this process until it halts: a gate, completion, or failure."""
    with case_lock(case):
        state = load_case_state(case)
        _audit(case, "control_run_started", {"from_stage": state.stage.value})
        final_state = run_pipeline(
            case,
            raw_prompt=raw_prompt,
            backend=backend,
            budget_config=budget or DEFAULT_BUDGET,
            auto_approve=False,
        )
        _audit(
            case,
            "control_run_finished",
            {
                "stage": final_state.stage.value,
                "awaiting": awaiting_label(final_state),
                "failure_cause": final_state.failure_cause,
            },
        )
        return final_state


def resume_allowed(case: Case) -> CaseState:
    """Check a case can be resumed, returning its state. Raises otherwise."""
    state = load_case_state(case)
    if state.stage is CaseStage.DONE:
        raise WrongStage(state.case_id, state.stage, "resumable")
    if state.stage in _GATE_STAGES:
        raise WrongStage(state.case_id, state.stage, "resumable")
    return state


def pause(case: Case) -> bool:
    """Stop the process running this case. Returns True if a run was stopped.

    Stopping happens at the process boundary, so work already handed to an agent is lost
    and its stage will re-run on resume.
    """
    from orchestrator.supervisor import stop  # local import: avoids a cycle at module load

    stopped = stop(case)
    if stopped:
        _audit(case, "control_run_stopped", {"case_id": case.root.name})
    return stopped
