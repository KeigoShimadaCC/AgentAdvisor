#!/usr/bin/env python3
"""Attach a realized outcome to a completed case in cross-case memory.

Calibration is the only honest check on the system's probabilities, and it cannot be
computed from anything the system produces on its own. The user has to come back later
and say what actually happened.

Usage:
    uv run python scripts/record_outcome.py --list
    uv run python scripts/record_outcome.py \\
        --case-id case-001-nvidia \\
        --summary "Bought the ETF; up 11% at the 12-month mark." \\
        --followed \\
        --realized
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.artifacts import OutcomeRecord, PriorCaseEntry  # noqa: E402
from orchestrator.memory import MemoryStore  # noqa: E402
from orchestrator.monitoring import MonitoringStore  # noqa: E402


def _list_cases(store: MemoryStore) -> int:
    entries = store.prior_cases()
    if not entries:
        print(f"No cases recorded in {store.root}.")
        return 0

    print(f"{'Case':<32} {'Outcome':<10} {'Forecast':>9}  Question")
    print("-" * 100)
    for entry in entries:
        forecast = (
            f"{entry.headline_outcome_probability:.2f}"
            if entry.headline_outcome_probability is not None
            else "-"
        )
        status = "recorded" if entry.outcome is not None else "open"
        print(f"{entry.case_id:<32} {status:<10} {forecast:>9}  {entry.decision_question}")

    summary = store.calibration()
    brier = f"{summary.brier_score:.3f}" if summary.brier_score is not None else "n/a"
    print(f"\nCalibration: n={summary.sample_size}, Brier={brier}. {summary.interpretation}")

    # SPEC-042: a breached indicator is the strongest available signal that a case's
    # outcome is now knowable. Surfacing it here is the whole point of tracking them —
    # a breach is not itself an outcome, but it is the moment to go and record one.
    _print_breached_prompts(store, entries)
    return 0


def _print_breached_prompts(store: MemoryStore, entries: list[PriorCaseEntry]) -> None:
    """Nudge toward cases whose monitoring fired and whose outcome is still unrecorded."""
    monitoring = MonitoringStore(store.root / "monitoring")
    open_cases = {entry.case_id for entry in entries if entry.outcome is None}

    nudges: list[tuple[str, list[str]]] = []
    for plan in monitoring.plans():
        if plan.case_id not in open_cases:
            continue
        breached = sorted(
            {check.indicator_id for check in monitoring.checks(plan.case_id) if check.breached}
        )
        if breached:
            nudges.append((plan.case_id, breached))

    if not nudges:
        return
    print("\nThese cases have breached indicators and no recorded outcome yet:")
    for case_id, breached in nudges:
        print(f"  {case_id}  ({', '.join(breached)})")
    print("  A breach is not an outcome, but it usually means one is now knowable.")
    print(
        "  Record it with --case-id <id> --summary ... --followed/--no-followed "
        "--realized/--no-realized"
    )


def _resolve_forecast(
    store: MemoryStore, case_id: str, name: str | None, probability: float | None
) -> tuple[str, float]:
    """Use the case's own recorded forecast unless the user overrides it.

    Re-stating the forecast by hand is how calibration records quietly become
    self-serving, so the stored value is the default.
    """
    entry = next((item for item in store.prior_cases() if item.case_id == case_id), None)
    if entry is None:
        raise SystemExit(f"No prior case recorded for '{case_id}'. Run --list to see options.")

    resolved_name = name or entry.headline_outcome_name
    resolved_probability = (
        probability if probability is not None else entry.headline_outcome_probability
    )
    if resolved_name is None or resolved_probability is None:
        raise SystemExit(
            f"Case '{case_id}' has no stored headline forecast. "
            "Pass --forecast-name and --forecast-probability explicitly."
        )
    return resolved_name, resolved_probability


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a realized outcome for a prior case")
    parser.add_argument("--list", action="store_true", help="List recorded cases and exit")
    parser.add_argument("--case-id", help="Case ID as stored in memory (see --list)")
    parser.add_argument("--summary", help="What actually happened, in one or two sentences")
    parser.add_argument(
        "--followed",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Whether the recommendation was actually followed",
    )
    parser.add_argument(
        "--realized",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Whether the forecast outcome occurred",
    )
    parser.add_argument("--forecast-name", help="Override the stored forecast outcome name")
    parser.add_argument(
        "--forecast-probability",
        type=float,
        help="Override the stored forecast probability (0-1)",
    )
    parser.add_argument(
        "--memory-root",
        type=Path,
        help="Memory directory (defaults to AGENTADVISOR_MEMORY_ROOT or <repo>/memory)",
    )
    args = parser.parse_args()

    store = MemoryStore(root=args.memory_root)

    if args.list:
        return _list_cases(store)

    missing = [
        flag
        for flag, value in (
            ("--case-id", args.case_id),
            ("--summary", args.summary),
            ("--followed/--no-followed", args.followed),
            ("--realized/--no-realized", args.realized),
        )
        if value is None
    ]
    if missing:
        parser.error(f"Missing required arguments: {', '.join(missing)}")

    forecast_name, forecast_probability = _resolve_forecast(
        store, args.case_id, args.forecast_name, args.forecast_probability
    )

    updated = store.record_outcome(
        args.case_id,
        OutcomeRecord(
            recorded_at=datetime.now(UTC),
            outcome_summary=args.summary,
            recommendation_followed=bool(args.followed),
            forecast_outcome_name=forecast_name,
            forecast_probability=forecast_probability,
            realized=bool(args.realized),
        ),
    )

    print(f"Recorded outcome for {updated.case_id}.")
    summary = store.calibration()
    brier = f"{summary.brier_score:.3f}" if summary.brier_score is not None else "n/a"
    print(f"Calibration now: n={summary.sample_size}, Brier={brier}. {summary.interpretation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
