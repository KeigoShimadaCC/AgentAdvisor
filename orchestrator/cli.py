"""The `advisor` command line: commission a decision, answer its gates, read the report.

The CLI is a thin adapter over the case store and the pipeline. It parses arguments,
calls one orchestrator function, and prints. No decision logic lives here, and no state
transition happens except through the state machine.

Exit codes: 0 success, 2 user error (bad case id, wrong stage), 3 pipeline failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from orchestrator import control
from orchestrator.artifacts import (
    EvidenceRecord,
    FinalApproval,
    FinalDecision,
    FramingApproval,
    FramingDecision,
    ObjectionRecord,
)
from orchestrator.backend import AgentBackend
from orchestrator.budget import BudgetConfig
from orchestrator.case_store import Case, default_cases_root, load_case
from orchestrator.control import ControlError, ControlStatus
from orchestrator.pipeline import DEFAULT_BUDGET, SMALL_BUDGET
from orchestrator.state_machine import CaseStage, CaseState, load_case_state
from orchestrator.supervisor import CaseLocked

EXIT_OK = 0
EXIT_USER_ERROR = 2
EXIT_PIPELINE_FAILURE = 3

BUDGET_PROFILES: dict[str, BudgetConfig] = {
    "default": DEFAULT_BUDGET,
    "small": SMALL_BUDGET,
}

_APPROVAL_STAGES = {
    CaseStage.AWAITING_FRAMING_APPROVAL,
    CaseStage.AWAITING_FINAL_APPROVAL,
}


class UserError(Exception):
    """A mistake the operator can fix, as opposed to a pipeline failure."""


def _cases_root(args: argparse.Namespace) -> Path | None:
    root: Path | None = getattr(args, "cases_root", None)
    return root


def _open_case(args: argparse.Namespace) -> Case:
    try:
        return load_case(args.case_id, cases_root=_cases_root(args))
    except (ValueError, FileNotFoundError, NotADirectoryError) as exc:
        raise UserError(str(exc)) from exc


def _raw_prompt(case: Case) -> str:
    """Recover the original prompt so a resumed case runs with the same input."""
    try:
        return control.raw_prompt_for(case)
    except control.MissingPrompt as exc:
        raise UserError(f"{exc} Start it with `advisor new`.") from exc


def _awaiting(state: CaseState) -> str | None:
    return control.awaiting_label(state)


def _status_payload(case: Case, status: ControlStatus, budget: BudgetConfig) -> dict[str, Any]:
    counters = status.budget_counters
    return {
        "case_id": status.case_id,
        "stage": status.stage.value,
        "awaiting": status.awaiting,
        "repair_cycle": status.repair_cycle,
        "synthesis_retries": status.synthesis_retries,
        "framing_approved": status.framing_approved,
        "final_approved": status.final_approved,
        "failure_cause": status.failure_cause,
        "updated_at": status.updated_at.isoformat(),
        "tasks": status.task_counts,
        "budget": {
            "agent_invocations": [
                counters.get("agent_invocations", 0),
                budget.max_agent_invocations,
            ],
            "high_tier_calls": [
                counters.get("high_tier_calls", 0),
                budget.max_high_tier_calls,
            ],
            "research_tasks": [
                counters.get("research_tasks", 0),
                budget.max_research_tasks,
            ],
            "repair_cycles": [status.repair_cycle, budget.max_repair_cycles],
        },
        "artifacts": {
            "evidence": len(case.list_artifacts(EvidenceRecord)),
            "objections": len(case.list_artifacts(ObjectionRecord)),
        },
        "report_path": str(_report_path(case)) if _report_path(case).exists() else None,
    }


def _report_path(case: Case) -> Path:
    return case.root / "outputs" / "final_recommendation.md"


def _print_status(payload: dict[str, Any]) -> None:
    print(f"Case:    {payload['case_id']}")
    print(f"Stage:   {payload['stage']}")
    if payload["awaiting"]:
        print(f"Waiting: {payload['awaiting']} (run `advisor approve {payload['case_id']}`)")
    if payload["failure_cause"]:
        print(f"Failure: {payload['failure_cause']}")
    print(f"Updated: {payload['updated_at']}")

    tasks = {name: count for name, count in payload["tasks"].items() if count}
    print("Tasks:   " + (", ".join(f"{name} {count}" for name, count in tasks.items()) or "none"))
    print(
        f"Records: {payload['artifacts']['evidence']} evidence, "
        f"{payload['artifacts']['objections']} objections"
    )

    print("Budget:")
    for name, (used, cap) in payload["budget"].items():
        print(f"  {name:<20} {used} / {cap}")

    if payload["report_path"]:
        print(f"Report:  {payload['report_path']}")


def _run(
    case: Case,
    *,
    raw_prompt: str,
    budget: BudgetConfig,
    backend: AgentBackend | None,
) -> CaseState:
    try:
        return control.run_to_halt(
            case,
            raw_prompt=raw_prompt,
            budget=budget,
            backend=backend,
        )
    except CaseLocked as exc:
        raise UserError(str(exc)) from exc


def _report_outcome(case: Case, state: CaseState) -> int:
    if state.stage is CaseStage.FAILED:
        print(f"Case {state.case_id} FAILED: {state.failure_cause}", file=sys.stderr)
        return EXIT_PIPELINE_FAILURE

    awaiting = _awaiting(state)
    if awaiting:
        print(f"Case {state.case_id} is waiting for {awaiting}.")
        print(f"  Review: {case.root}")
        print(f"  Then:   advisor approve {state.case_id}")
        return EXIT_OK

    if state.stage is CaseStage.DONE:
        print(f"Case {state.case_id} is done.")
        report = _report_path(case)
        if report.exists():
            print(f"  Report: {report}")
        return EXIT_OK

    print(f"Case {state.case_id} halted at stage {state.stage.value}.")
    return EXIT_OK


def cmd_new(args: argparse.Namespace, backend: AgentBackend | None = None) -> int:
    prompt = args.prompt.strip()
    if not prompt:
        raise UserError("The decision prompt is empty.")

    try:
        case = control.new_case(prompt, slug=args.slug, cases_root=_cases_root(args))
    except (ControlError, ValueError) as exc:
        raise UserError(str(exc)) from exc

    print(f"Created {case.root.name} at {case.root}")
    state = _run(
        case,
        raw_prompt=prompt,
        budget=BUDGET_PROFILES[args.budget_profile],
        backend=backend,
    )
    return _report_outcome(case, state)


def cmd_status(args: argparse.Namespace, backend: AgentBackend | None = None) -> int:
    del backend
    case = _open_case(args)
    status = control.case_status(case)
    payload = _status_payload(case, status, BUDGET_PROFILES[args.budget_profile])

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _print_status(payload)
    return EXIT_OK


def _load_mapping(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UserError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise UserError(f"{path} must contain a YAML mapping.")
    return loaded


def _build_framing_approval(args: argparse.Namespace) -> FramingApproval:
    now = datetime.now(UTC)
    if args.edit is not None:
        return FramingApproval(
            decision=FramingDecision.EDIT,
            approved_by="user",
            approved_at=now,
            edits=_load_mapping(args.edit),
        )
    if args.answers is not None:
        return FramingApproval(
            decision=FramingDecision.ANSWER_CLARIFICATIONS,
            approved_by="user",
            approved_at=now,
            clarification_answers={
                str(key): str(value) for key, value in _load_mapping(args.answers).items()
            },
        )
    return FramingApproval(decision=FramingDecision.APPROVE, approved_by="user", approved_at=now)


def cmd_approve(args: argparse.Namespace, backend: AgentBackend | None = None) -> int:
    case = _open_case(args)
    state = load_case_state(case)

    if state.stage not in _APPROVAL_STAGES:
        raise UserError(
            f"Case {state.case_id} is at stage '{state.stage.value}', which is not an approval "
            "gate. Nothing to approve."
        )

    try:
        if state.stage is CaseStage.AWAITING_FRAMING_APPROVAL:
            framing = _build_framing_approval(args)
            state = control.approve_framing(case, framing)
            print(f"Recorded framing {framing.decision.value} for {state.case_id}.")
        else:
            if args.edit is not None or args.answers is not None:
                raise UserError(
                    "--edit and --answers apply to the framing gate only. The final gate is a "
                    "plain approve or reject."
                )
            final = FinalApproval(
                decision=FinalDecision.ACCEPT,
                approved_by="user",
                approved_at=datetime.now(UTC),
            )
            state = control.approve_final(case, final)
            print(f"Approved the final recommendation for {state.case_id}.")
    except (ControlError, CaseLocked) as exc:
        raise UserError(str(exc)) from exc

    state = _run(
        case,
        raw_prompt=_raw_prompt(case),
        budget=BUDGET_PROFILES[args.budget_profile],
        backend=backend,
    )
    return _report_outcome(case, state)


def cmd_resume(args: argparse.Namespace, backend: AgentBackend | None = None) -> int:
    case = _open_case(args)
    state = load_case_state(case)

    if state.stage is CaseStage.DONE:
        print(f"Case {state.case_id} is already done.")
        return EXIT_OK
    if state.stage in _APPROVAL_STAGES:
        raise UserError(
            f"Case {state.case_id} is waiting for {_awaiting(state)}. "
            f"Run `advisor approve {state.case_id}` instead."
        )

    state = _run(
        case,
        raw_prompt=_raw_prompt(case),
        budget=BUDGET_PROFILES[args.budget_profile],
        backend=backend,
    )
    return _report_outcome(case, state)


def cmd_report(args: argparse.Namespace, backend: AgentBackend | None = None) -> int:
    del backend
    case = _open_case(args)
    report = _report_path(case)
    if not report.exists():
        state = load_case_state(case)
        raise UserError(
            f"Case {state.case_id} has no report yet; it is at stage '{state.stage.value}'."
        )
    print(f"# {report}\n")
    print(report.read_text(encoding="utf-8"))
    return EXIT_OK


def cmd_list(args: argparse.Namespace, backend: AgentBackend | None = None) -> int:
    del backend
    root = _cases_root(args) or default_cases_root()
    if not root.exists():
        print(f"No cases yet (looked in {root}).")
        return EXIT_OK

    rows: list[dict[str, Any]] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or not (entry / "state.yaml").exists():
            continue
        try:
            state = load_case_state(Case(root=entry))
        except Exception:  # noqa: BLE001 - a corrupt case must not hide the healthy ones
            rows.append({"case_id": entry.name, "stage": "unreadable", "updated_at": None})
            continue
        rows.append(
            {
                "case_id": state.case_id,
                "stage": state.stage.value,
                "awaiting": _awaiting(state),
                "updated_at": state.updated_at.isoformat(),
            }
        )

    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
        return EXIT_OK

    if not rows:
        print(f"No cases yet (looked in {root}).")
        return EXIT_OK

    width = max(len(row["case_id"]) for row in rows)
    for row in rows:
        updated = (row["updated_at"] or "")[:19].replace("T", " ")
        print(f"{row['case_id']:<{width}}  {row['stage']:<26}  {updated}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="advisor",
        description="Commission a structured decision analysis and read its report.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "--cases-root",
            type=Path,
            default=None,
            help="Directory holding cases (defaults to AGENTADVISOR_CASES_ROOT or ./cases)",
        )
        sub.add_argument(
            "--budget-profile",
            choices=sorted(BUDGET_PROFILES),
            default="default",
            help="Resource caps for the run (default: default)",
        )

    new = subparsers.add_parser("new", help="Start a new decision case")
    new.add_argument("prompt", help="The decision, in your own words")
    new.add_argument("--slug", default="case", help="Short name used in the case directory")
    add_common(new)
    new.set_defaults(func=cmd_new)

    status = subparsers.add_parser("status", help="Show a case's stage, tasks and budget")
    status.add_argument("case_id")
    status.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    add_common(status)
    status.set_defaults(func=cmd_status)

    approve = subparsers.add_parser("approve", help="Clear the gate a case is waiting on")
    approve.add_argument("case_id")
    approve.add_argument(
        "--edit",
        type=Path,
        default=None,
        help="YAML mapping of framing edits to record instead of a plain approval",
    )
    approve.add_argument(
        "--answers",
        type=Path,
        default=None,
        help="YAML mapping of question_id to answer for intake clarifications",
    )
    add_common(approve)
    approve.set_defaults(func=cmd_approve)

    resume = subparsers.add_parser("resume", help="Continue a case after an interruption")
    resume.add_argument("case_id")
    add_common(resume)
    resume.set_defaults(func=cmd_resume)

    report = subparsers.add_parser("report", help="Print the final recommendation")
    report.add_argument("case_id")
    add_common(report)
    report.set_defaults(func=cmd_report)

    listing = subparsers.add_parser("list", help="List known cases")
    listing.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    add_common(listing)
    listing.set_defaults(func=cmd_list)

    return parser


def main(argv: Sequence[str] | None = None, *, backend: AgentBackend | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        exit_code: int = args.func(args, backend)
    except UserError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
