#!/usr/bin/env python3
"""Extract resource and process metrics for a completed case from its audit log.

North star 13 asks what a decision actually costs and whether the spend bought
anything. That question is only answerable if the numbers come out of the audit log
mechanically, so this reads `audit.jsonl` and nothing else. Anything it cannot find
there is reported as missing rather than estimated.

Usage:
    uv run python scripts/case_metrics.py cases/case-001-nvidia
    uv run python scripts/case_metrics.py cases/case-001-nvidia --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

RETRYABLE_TERMINAL_STATUSES = {"schema_invalid", "empty_output", "backend_error", "timeout"}


@dataclass
class RoleUsage:
    role: str
    models: Counter[str] = field(default_factory=Counter)
    attempts: int = 0
    successes: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def success_rate(self) -> float:
        return self.successes / self.attempts if self.attempts else 0.0


def _read_events(case_dir: Path) -> list[dict[str, Any]]:
    audit_path = case_dir / "audit.jsonl"
    if not audit_path.exists():
        raise FileNotFoundError(f"No audit log at {audit_path}")

    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(audit_path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            events.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            print(f"warning: {audit_path}:{line_number} is not valid JSON ({exc})", file=sys.stderr)
    return events


def _deduplicate_invocations(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One physical call can be logged twice (per-attempt and per-task rollup).

    Attempts are identified by timestamp plus actor, which is what the backend stamps
    when the subprocess returns.
    """
    seen: set[tuple[str, str, int]] = set()
    unique: list[dict[str, Any]] = []
    for event in events:
        if event.get("event_type") != "role_invocation_attempt":
            continue
        payload = event.get("payload") or {}
        key = (str(event.get("ts")), str(event.get("actor")), int(payload.get("attempt") or 0))
        if key in seen:
            continue
        seen.add(key)
        unique.append(event)
    return unique


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def collect(case_dir: Path) -> dict[str, Any]:
    events = _read_events(case_dir)
    invocations = _deduplicate_invocations(events)

    roles: dict[str, RoleUsage] = {}
    for event in invocations:
        actor = str(event.get("actor") or "unknown")
        payload = event.get("payload") or {}
        usage = event.get("usage") or {}
        entry = roles.setdefault(actor, RoleUsage(role=actor))
        entry.attempts += 1
        if payload.get("status") == "ok":
            entry.successes += 1
        if event.get("model"):
            entry.models[str(event["model"])] += 1
        entry.input_tokens += int(usage.get("input_tokens") or 0)
        entry.output_tokens += int(usage.get("output_tokens") or 0)
        entry.duration_ms += int(event.get("duration_ms") or 0)

    timestamps = [ts for ts in (_parse_ts(event.get("ts")) for event in events) if ts is not None]
    wall_clock_s = (
        (max(timestamps) - min(timestamps)).total_seconds() if len(timestamps) >= 2 else None
    )

    retries_by_role: Counter[str] = Counter()
    failure_causes: Counter[str] = Counter()
    for event in invocations:
        payload = event.get("payload") or {}
        if int(payload.get("attempt") or 1) > 1:
            retries_by_role[str(event.get("actor"))] += 1
        if payload.get("status") != "ok":
            failure_causes[str(payload.get("status") or "unknown")] += 1

    event_counts = Counter(str(event.get("event_type")) for event in events)
    stages = [
        str((event.get("payload") or {}).get("stage"))
        for event in events
        if event.get("event_type") == "stage_completed"
    ]

    gate_findings = 0
    gate_blocks = 0
    for event in events:
        if event.get("event_type") != "stage_gate_evaluated":
            continue
        payload = event.get("payload") or {}
        gate_findings += int(payload.get("finding_count") or 0)
        gate_blocks += len(payload.get("blocking_checks") or [])

    stop_decisions = [
        (event.get("payload") or {})
        for event in events
        if event.get("event_type") == "stop_decision_evaluated"
    ]
    reviews = [
        (event.get("payload") or {})
        for event in events
        if event.get("event_type") == "review_evaluated"
    ]
    thesis = [
        (event.get("payload") or {})
        for event in events
        if event.get("event_type") == "thesis_revision_recorded"
    ]

    records: dict[str, int] = defaultdict(int)
    for event in events:
        payload = event.get("payload") or {}
        if event.get("event_type") == "evidence_batch_unpacked":
            records["evidence"] += int(payload.get("record_count") or 0)
        elif event.get("event_type") == "assumption_batch_unpacked":
            records["assumptions"] += int(payload.get("record_count") or 0)
        elif event.get("event_type") == "objection_batch_unpacked":
            records["objections"] += int(payload.get("objection_count") or 0)

    total_attempts = sum(role.attempts for role in roles.values())
    total_successes = sum(role.successes for role in roles.values())

    return {
        "case_id": case_dir.name,
        "wall_clock_s": wall_clock_s,
        "stages_completed": stages,
        # DONE and FAILED emit no stage_completed event, so this trails the real stage.
        "last_completed_stage": stages[-1] if stages else None,
        "invocations": {
            "attempts": total_attempts,
            "successes": total_successes,
            "success_rate": total_successes / total_attempts if total_attempts else 0.0,
            "retries": sum(retries_by_role.values()),
            "retries_by_role": dict(retries_by_role.most_common()),
            "failure_causes": dict(failure_causes.most_common()),
        },
        "tokens": {
            "input": sum(role.input_tokens for role in roles.values()),
            "output": sum(role.output_tokens for role in roles.values()),
            "total": sum(role.total_tokens for role in roles.values()),
        },
        "by_role": {
            role.role: {
                "attempts": role.attempts,
                "successes": role.successes,
                "success_rate": role.success_rate,
                "models": dict(role.models.most_common()),
                "input_tokens": role.input_tokens,
                "output_tokens": role.output_tokens,
                "total_tokens": role.total_tokens,
                "duration_s": role.duration_ms / 1000,
            }
            for role in sorted(roles.values(), key=lambda item: -item.total_tokens)
        },
        "records": dict(records),
        "process": {
            "gate_findings": gate_findings,
            "gate_blocking_checks": gate_blocks,
            "stop_decisions": [payload.get("action") for payload in stop_decisions],
            "repair_cycles": max(
                (int(payload.get("repair_cycle") or 0) for payload in stop_decisions),
                default=0,
            ),
            "thesis_revisions": len(thesis),
            "thesis_changes": sum(1 for payload in thesis if payload.get("changed")),
            "review_outcomes": [payload.get("outcome") for payload in reviews],
            "synthesis_retries": max(
                (int(payload.get("synthesis_retries") or 0) for payload in reviews),
                default=0,
            ),
            "dual_track": (
                "compared"
                if event_counts.get("dual_track_compared")
                else "skipped"
                if event_counts.get("dual_track_skipped")
                else "absent"
            ),
        },
        "event_counts": dict(event_counts.most_common()),
    }


def _budget_headroom(case_dir: Path) -> dict[str, Any] | None:
    """Budget caps are a config choice, so headroom needs the persisted counters."""
    from orchestrator.case_store import Case  # noqa: PLC0415
    from orchestrator.state_machine import load_case_state  # noqa: PLC0415

    try:
        state = load_case_state(Case(root=case_dir))
    except Exception:  # noqa: BLE001
        return None
    return dict(state.budget_counters)


def _format_text(metrics: dict[str, Any], counters: dict[str, Any] | None) -> str:
    lines: list[str] = []
    invocations = metrics["invocations"]
    tokens = metrics["tokens"]
    process = metrics["process"]

    wall = metrics["wall_clock_s"]
    wall_text = f"{wall / 60:.0f} min" if wall else "unknown"

    lines.append(f"Case:        {metrics['case_id']}")
    lines.append(
        f"Last stage:  {metrics['last_completed_stage']} "
        f"({len(metrics['stages_completed'])} completed)"
    )
    lines.append(f"Wall clock:  {wall_text}")
    lines.append(
        f"Invocations: {invocations['attempts']} attempts, "
        f"{invocations['successes']} ok ({invocations['success_rate']:.0%}), "
        f"{invocations['retries']} retries"
    )
    lines.append(
        f"Tokens:      {tokens['total']:,} total "
        f"({tokens['input']:,} in / {tokens['output']:,} out)"
    )

    records = metrics["records"]
    lines.append(
        "Records:     "
        f"{records.get('evidence', 0)} evidence, "
        f"{records.get('assumptions', 0)} assumptions, "
        f"{records.get('objections', 0)} objections"
    )

    lines.append("")
    lines.append(f"{'Role':<22}{'Att':>5}{'OK':>5}{'Rate':>7}{'Tokens':>11}{'Time':>9}  Model")
    lines.append("-" * 92)
    for role, data in metrics["by_role"].items():
        model = next(iter(data["models"]), "-")
        if len(data["models"]) > 1:
            model += f" (+{len(data['models']) - 1})"
        lines.append(
            f"{role:<22}{data['attempts']:>5}{data['successes']:>5}"
            f"{data['success_rate']:>6.0%}{data['total_tokens']:>11,}"
            f"{data['duration_s'] / 60:>8.1f}m  {model}"
        )

    if invocations["failure_causes"]:
        lines.append("")
        lines.append("Failure causes:")
        for cause, count in invocations["failure_causes"].items():
            lines.append(f"  {count:>4}  {cause}")

    lines.append("")
    lines.append("Process:")
    blocking = process["gate_blocking_checks"]
    lines.append(f"  gate findings       {process['gate_findings']} ({blocking} blocking)")
    lines.append(f"  repair cycles       {process['repair_cycles']}")
    lines.append(f"  synthesis retries   {process['synthesis_retries']}")
    lines.append(
        f"  thesis revisions    {process['thesis_revisions']} "
        f"({process['thesis_changes']} changed the preferred alternative)"
    )
    lines.append(
        f"  stop decisions      {', '.join(str(a) for a in process['stop_decisions']) or '-'}"
    )
    lines.append(
        f"  review outcomes     {', '.join(str(o) for o in process['review_outcomes']) or '-'}"
    )
    lines.append(f"  dual track          {process['dual_track']}")

    if counters:
        lines.append("")
        lines.append("Budget consumed:")
        for name, value in sorted(counters.items()):
            lines.append(f"  {name:<20}{value}")
    elif counters is not None:
        lines.append("")
        lines.append("Budget consumed: nothing recorded in state.yaml.")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("case_dir", type=Path, help="Path to a case directory under cases/")
    parser.add_argument("--json", action="store_true", help="Emit the full metrics as JSON")
    args = parser.parse_args()

    case_dir: Path = args.case_dir
    if not case_dir.is_dir():
        print(f"error: {case_dir} is not a directory", file=sys.stderr)
        return 2

    try:
        metrics = collect(case_dir)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    counters = _budget_headroom(case_dir)
    if args.json:
        print(json.dumps({**metrics, "budget_counters": counters}, indent=2))
    else:
        print(_format_text(metrics, counters))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
