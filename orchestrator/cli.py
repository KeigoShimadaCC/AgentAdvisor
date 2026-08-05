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

from orchestrator.artifacts import (
    EvidenceRecord,
    FramingApproval,
    FramingDecision,
    IndicatorCheck,
    IntakeRecord,
    ObjectionRecord,
    TaskRecord,
    TaskStatus,
)
from orchestrator.backend import AgentBackend, BackendName, make_backend
from orchestrator.budget import BudgetConfig
from orchestrator.case_store import Case, create_case, default_cases_root, load_case
from orchestrator.monitoring import MonitoringStore, due_checks, mitigations_for
from orchestrator.pipeline import DEFAULT_BUDGET, SMALL_BUDGET
from orchestrator.pipeline import run as run_pipeline
from orchestrator.state_machine import CaseStage, CaseState, load_case_state, save_case_state

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
    """Recover the original prompt so a resumed case runs with the same input.

    The intake record is the only place the user's words survive verbatim, which is
    also why a case cannot be resumed before intake has produced one.
    """
    records = case.list_artifacts(IntakeRecord)
    if not records:
        raise UserError(
            f"Case {case.root.name} has no intake record yet, so there is nothing to resume. "
            "Start it with `advisor new`."
        )
    return records[0].raw_prompt


def _task_counts(case: Case) -> dict[str, int]:
    counts = {status.value: 0 for status in TaskStatus}
    for record in case.list_artifacts(TaskRecord):
        counts[record.status.value] += 1
    return counts


def _awaiting(state: CaseState) -> str | None:
    if state.stage is CaseStage.AWAITING_FRAMING_APPROVAL:
        return "framing approval"
    if state.stage is CaseStage.AWAITING_FINAL_APPROVAL:
        return "final approval"
    return None


def _status_payload(case: Case, state: CaseState, budget: BudgetConfig) -> dict[str, Any]:
    counters = state.budget_counters
    return {
        "case_id": state.case_id,
        "stage": state.stage.value,
        "awaiting": _awaiting(state),
        "repair_cycle": state.repair_cycle,
        "synthesis_retries": state.synthesis_retries,
        "framing_approved": state.framing_approved,
        "final_approved": state.final_approved,
        "failure_cause": state.failure_cause,
        "updated_at": state.updated_at.isoformat(),
        "tasks": _task_counts(case),
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
            "repair_cycles": [state.repair_cycle, budget.max_repair_cycles],
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
    return run_pipeline(
        case,
        raw_prompt=raw_prompt,
        backend=backend,
        budget_config=budget,
        auto_approve=False,
    )


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
        case = create_case(args.slug, cases_root=_cases_root(args))
    except ValueError as exc:
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
    state = load_case_state(case)
    payload = _status_payload(case, state, BUDGET_PROFILES[args.budget_profile])

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

    if state.stage is CaseStage.AWAITING_FRAMING_APPROVAL:
        approval = _build_framing_approval(args)
        case.write_artifact(approval)
        state = state.model_copy(update={"framing_approved": True})
        print(f"Recorded framing {approval.decision.value} for {state.case_id}.")
    else:
        if args.edit is not None or args.answers is not None:
            raise UserError(
                "--edit and --answers apply to the framing gate only. The final gate is a "
                "plain approve or reject."
            )
        state = state.model_copy(update={"final_approved": True})
        print(f"Approved the final recommendation for {state.case_id}.")

    save_case_state(case, state)
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


def cmd_watch(args: argparse.Namespace, backend: AgentBackend | None = None) -> int:
    """Report which monitoring checks are due (SPEC-042).

    A pure read over stored plans. Delivered cases are never touched: this is what
    replaces reopening a terminal case.
    """
    del backend
    store = MonitoringStore(args.monitoring_root)
    plans = store.plans()
    if args.case_id:
        plans = [plan for plan in plans if plan.case_id == args.case_id]
        if not plans:
            raise UserError(f"No monitoring plan recorded for case {args.case_id}.")

    if not plans:
        print("No monitoring plans recorded yet.")
        return EXIT_OK

    any_due = False
    for plan in plans:
        due = due_checks(plan, store.checks(plan.case_id))
        if args.due and not due:
            continue
        any_due = any_due or bool(due)
        print(f"{plan.case_id}  (delivered {plan.delivered_at.isoformat()}, {plan.horizon})")
        if not plan.concretized:
            print("  ! indicators were never made concrete; thresholds are the raw text")
        if not due:
            print("  nothing due")
        for item in due:
            last = item.last_checked.date().isoformat() if item.last_checked else "never checked"
            print(
                f"  {item.indicator.indicator_id}  {item.indicator.observable}\n"
                f"      breach: {item.indicator.threshold}\n"
                f"      last: {last}, {item.days_overdue}d overdue "
                f"(every {item.indicator.check_cadence_days}d)"
            )
        print()

    if args.due and not any_due:
        print("Nothing due.")
    return EXIT_OK


def cmd_check(args: argparse.Namespace, backend: AgentBackend | None = None) -> int:
    """Record an observation against a monitored indicator (SPEC-042)."""
    del backend
    store = MonitoringStore(args.monitoring_root)
    plan = store.read_plan(args.case_id)
    if plan is None:
        raise UserError(f"No monitoring plan recorded for case {args.case_id}.")

    known = {indicator.indicator_id for indicator in plan.indicators}
    if args.indicator_id not in known:
        raise UserError(
            f"Unknown indicator {args.indicator_id} for {args.case_id}. "
            f"Known: {', '.join(sorted(known))}"
        )

    store.record_check(
        args.case_id,
        IndicatorCheck(
            indicator_id=args.indicator_id,
            checked_at=datetime.now(UTC),
            observed=args.observed,
            breached=args.breached,
        ),
    )
    print(f"Recorded {args.indicator_id} for {args.case_id}.")

    if not args.breached:
        return EXIT_OK

    responses = mitigations_for(plan, [args.indicator_id])
    print("\nBreached. Prepared responses:")
    for mitigation in responses or []:
        print(f"  {mitigation.mitigation_id}  {mitigation.mitigation}  ({mitigation.owner})")
    if not responses:
        print("  (none were linked to this indicator)")
    print(
        "\nThis decision was made under different conditions. Open a new case rather than "
        f"reopening {args.case_id}, which stays as the record of what was decided and why."
    )
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


def cmd_ui(args: argparse.Namespace, backend: AgentBackend | None = None) -> int:
    """Start the local web UI service (SPEC-033).

    Binds to 127.0.0.1 only. In replay mode, serves a fixture case read-only
    and re-emits its audit events on scaled timing.
    """
    del backend
    import os

    import uvicorn

    if args.cases_root is not None:
        os.environ["AGENTADVISOR_CASES_ROOT"] = str(args.cases_root)
    if args.replay is not None:
        os.environ["AGENTADVISOR_REPLAY_DIR"] = str(args.replay)
    os.environ["AGENTADVISOR_REPLAY_SPEED"] = str(args.speed)

    # Import after env vars are set so the module-level app picks them up.
    from orchestrator.service.app import app

    print(f"Advisor UI on http://127.0.0.1:{args.port}")
    if args.replay:
        print(f"  Replay mode: {args.replay} (speed={args.speed}x)")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level=args.log_level)
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
        sub.add_argument(
            "--backend",
            choices=sorted(name.value for name in BackendName),
            default=None,
            help="Agent CLI to run roles on (defaults to AGENTADVISOR_BACKEND, else cursor)",
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

    watch = subparsers.add_parser("watch", help="Show monitoring checks that are due")
    watch.add_argument("case_id", nargs="?", default=None, help="Limit to one case")
    watch.add_argument("--due", action="store_true", help="Only show cases with due checks")
    watch.add_argument("--monitoring-root", type=Path, default=None)
    watch.set_defaults(func=cmd_watch)

    check = subparsers.add_parser("check", help="Record an observation for an indicator")
    check.add_argument("case_id")
    check.add_argument("indicator_id", help="e.g. M-001")
    check.add_argument("--observed", required=True, help="What you saw")
    check.add_argument("--breached", action="store_true", help="The threshold was crossed")
    check.add_argument("--monitoring-root", type=Path, default=None)
    check.set_defaults(func=cmd_check)

    ui = subparsers.add_parser("ui", help="Start the local web UI service")
    ui.add_argument("--port", type=int, default=8765, help="Port to bind (default: 8765)")
    ui.add_argument("--cases-root", type=Path, default=None, help="Directory holding cases")
    ui.add_argument(
        "--replay",
        type=Path,
        default=None,
        help="Replay a fixture case read-only at scaled timing",
    )
    ui.add_argument(
        "--speed",
        type=float,
        default=60.0,
        help="Replay speed factor (inter-event delay / speed, default: 60)",
    )
    ui.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Uvicorn log level (default: info)",
    )
    ui.set_defaults(func=cmd_ui)

    return parser


def main(argv: Sequence[str] | None = None, *, backend: AgentBackend | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if backend is None:
        try:
            backend = make_backend(getattr(args, "backend", None))
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_USER_ERROR
    try:
        exit_code: int = args.func(args, backend)
    except UserError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
