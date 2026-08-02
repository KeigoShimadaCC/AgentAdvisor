"""Run one case to its next halt, as a standalone process.

A full case takes tens of minutes, so anything with a user interface cannot run it inline.
The worker exists so a caller can start a run, close, and come back: the case state on disk
is the contract between them, and the case lock keeps a second writer out.

    python -m orchestrator.worker <case-id> [--cases-root DIR] [--budget-profile NAME]

Exit codes: 0 the case halted cleanly (a gate, or done), 1 the pipeline failed, 2 the case
could not be opened or was already running.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from orchestrator import control
from orchestrator.backend import AgentBackend, CursorCLIBackend
from orchestrator.budget import BudgetConfig
from orchestrator.case_store import load_case
from orchestrator.pipeline import DEFAULT_BUDGET, SMALL_BUDGET
from orchestrator.state_machine import CaseStage
from orchestrator.supervisor import CaseLocked

EXIT_OK = 0
EXIT_PIPELINE_FAILURE = 1
EXIT_UNAVAILABLE = 2

BUDGET_PROFILES: dict[str, BudgetConfig] = {
    "default": DEFAULT_BUDGET,
    "small": SMALL_BUDGET,
}


BACKEND_FACTORY_ENV = "AGENTADVISOR_BACKEND_FACTORY"


def _backend() -> AgentBackend:
    """The real harness, unless something named a different one.

    ``AGENTADVISOR_BACKEND_FACTORY=package.module:callable`` selects an alternative backend
    without the orchestrator importing test code. Tests use it to run a worker against a
    scripted backend; the default is the real Cursor CLI.
    """
    spec = os.environ.get(BACKEND_FACTORY_ENV)
    if not spec:
        return CursorCLIBackend()

    module_name, _, attr = spec.partition(":")
    if not module_name or not attr:
        raise ValueError(f"{BACKEND_FACTORY_ENV} must look like 'module:callable', got {spec!r}.")
    module = importlib.import_module(module_name)
    factory = getattr(module, attr)
    backend: AgentBackend = factory()
    return backend


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="orchestrator.worker",
        description="Run one case to its next halt.",
    )
    parser.add_argument("case_id")
    parser.add_argument("--cases-root", type=Path, default=None)
    parser.add_argument("--budget-profile", choices=sorted(BUDGET_PROFILES), default="default")
    args = parser.parse_args(argv)

    try:
        case = load_case(args.case_id, cases_root=args.cases_root)
    except (ValueError, FileNotFoundError, NotADirectoryError) as exc:
        print(f"worker: {exc}", file=sys.stderr)
        return EXIT_UNAVAILABLE

    try:
        prompt = control.raw_prompt_for(case)
    except control.MissingPrompt as exc:
        print(f"worker: {exc}", file=sys.stderr)
        return EXIT_UNAVAILABLE

    try:
        state = control.run_to_halt(
            case,
            raw_prompt=prompt,
            budget=BUDGET_PROFILES[args.budget_profile],
            backend=_backend(),
        )
    except CaseLocked as exc:
        print(f"worker: {exc}", file=sys.stderr)
        return EXIT_UNAVAILABLE

    if state.stage is CaseStage.FAILED:
        print(f"worker: case failed: {state.failure_cause}", file=sys.stderr)
        return EXIT_PIPELINE_FAILURE
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
