"""Worker process entry point.

Run as ``python -m orchestrator.worker <case-id>``.

The worker loads the case, builds the configured backend (Cursor CLI by
default; ``AGENTADVISOR_BACKEND=stub`` for tests), acquires the run lock, and
calls :func:`orchestrator.pipeline.run` with ``auto_approve=False`` so the
pipeline halts at the next approval gate or completion.  It exits 0 on a clean
halt (gate or done) and nonzero on failure.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import IntakeRecord
from orchestrator.backend import AgentBackend, CursorCLIBackend
from orchestrator.budget import BudgetConfig
from orchestrator.case_store import Case, load_case
from orchestrator.invoke_role import clear_cross_field_validation_hooks
from orchestrator.pipeline import DEFAULT_BUDGET, SMALL_BUDGET, run
from orchestrator.state_machine import CaseStage
from orchestrator.stub_backend import PipelineStubBackend
from orchestrator.supervisor import RunLock

_BUDGET_PROFILES: dict[str, BudgetConfig] = {
    "default": DEFAULT_BUDGET,
    "small": SMALL_BUDGET,
}

_META_FILENAME = "control_meta.yaml"


def _build_backend(case: Case) -> AgentBackend:
    backend_env = os.getenv("AGENTADVISOR_BACKEND", "").lower()
    if backend_env == "stub":
        return PipelineStubBackend(case)
    return CursorCLIBackend()


def _load_meta(case_root: Path) -> dict[str, str]:
    meta_path = case_root / "shared" / _META_FILENAME
    if not meta_path.exists():
        return {}
    try:
        loaded = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    return loaded


def _resolve_raw_prompt(case: Case, meta: dict[str, str]) -> str:
    raw_prompt = meta.get("raw_prompt", "")
    if raw_prompt:
        return raw_prompt
    # Fall back to the intake record (resume after first halt).
    records = case.list_artifacts(IntakeRecord)
    if records:
        return records[0].raw_prompt
    raise RuntimeError(f"No raw_prompt in control_meta and no IntakeRecord for {case.root.name}")


def _resolve_budget(meta: dict[str, str]) -> BudgetConfig:
    profile = meta.get("budget_profile", "default")
    return _BUDGET_PROFILES.get(profile, DEFAULT_BUDGET)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m orchestrator.worker <case-id>", file=sys.stderr)
        return 2

    case_id = sys.argv[1]
    case = load_case(case_id)
    lock = RunLock(case.root)

    try:
        lock.acquire()
    except Exception as exc:  # noqa: BLE001
        print(f"Cannot acquire lock for {case_id}: {exc}", file=sys.stderr)
        return 1

    clear_cross_field_validation_hooks()
    try:
        meta = _load_meta(case.root)
        raw_prompt = _resolve_raw_prompt(case, meta)
        budget = _resolve_budget(meta)
        backend = _build_backend(case)

        state = run(
            case,
            raw_prompt=raw_prompt,
            backend=backend,
            budget_config=budget,
            auto_approve=False,
        )

        if state.stage is CaseStage.FAILED:
            print(
                f"Worker for {case_id} FAILED: {state.failure_cause}",
                file=sys.stderr,
            )
            return 1
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Worker for {case_id} crashed: {exc}", file=sys.stderr)
        return 1
    finally:
        lock.release()
        clear_cross_field_validation_hooks()


if __name__ == "__main__":
    raise SystemExit(main())
