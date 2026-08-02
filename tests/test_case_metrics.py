from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from case_metrics import collect  # noqa: E402


def _event(event_type: str, **kwargs: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ts": kwargs.pop("ts", "2026-08-02T10:00:00.000000Z"),
        "actor": kwargs.pop("actor", "orchestrator"),
        "event_type": event_type,
        "model": kwargs.pop("model", None),
        "duration_ms": kwargs.pop("duration_ms", None),
        "usage": kwargs.pop("usage", None),
        "payload": kwargs.pop("payload", {}),
        "schema_version": 1,
    }
    return base


def _invocation(
    actor: str,
    *,
    ts: str,
    status: str = "ok",
    attempt: int = 1,
    model: str = "composer-2.5",
    tokens: tuple[int, int] = (100, 50),
    duration_ms: int = 1000,
    coercions: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"attempt": attempt, "status": status, "task_id": f"T-{actor}"}
    if coercions:
        payload["coercions"] = coercions
    return _event(
        "role_invocation_attempt",
        actor=actor,
        ts=ts,
        model=model,
        duration_ms=duration_ms,
        usage={"input_tokens": tokens[0], "output_tokens": tokens[1]},
        payload=payload,
    )


@pytest.fixture
def case_dir(tmp_path: Path) -> Path:
    root = tmp_path / "case-001-toy"
    root.mkdir()
    return root


def _write(case_dir: Path, events: list[dict[str, Any]]) -> None:
    (case_dir / "audit.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8"
    )


def test_a_repeated_invocation_event_is_counted_once(case_dir: Path) -> None:
    """The pipeline logs some attempts twice; double counting would inflate cost."""
    duplicate = _invocation("intake", ts="2026-08-02T10:00:00.000000Z")
    _write(case_dir, [duplicate, _event("stage_completed", payload={"stage": "intake"}), duplicate])

    metrics = collect(case_dir)

    assert metrics["invocations"]["attempts"] == 1
    assert metrics["tokens"]["total"] == 150


def test_retries_and_failure_causes_are_attributed_to_their_role(case_dir: Path) -> None:
    _write(
        case_dir,
        [
            _invocation("analyst", ts="2026-08-02T10:00:00Z", status="validation_failure"),
            _invocation(
                "analyst", ts="2026-08-02T10:01:00Z", status="validation_failure", attempt=2
            ),
            _invocation("analyst", ts="2026-08-02T10:02:00Z", attempt=3),
            _invocation("intake", ts="2026-08-02T10:03:00Z"),
        ],
    )

    metrics = collect(case_dir)

    assert metrics["invocations"]["attempts"] == 4
    assert metrics["invocations"]["successes"] == 2
    assert metrics["invocations"]["retries"] == 2
    assert metrics["invocations"]["retries_by_role"] == {"analyst": 2}
    assert metrics["invocations"]["failure_causes"] == {"validation_failure": 2}
    assert metrics["by_role"]["analyst"]["success_rate"] == pytest.approx(1 / 3)


def test_wall_clock_spans_the_whole_log_not_just_invocations(case_dir: Path) -> None:
    _write(
        case_dir,
        [
            _event("stage_completed", ts="2026-08-02T10:00:00Z", payload={"stage": "intake"}),
            _invocation("intake", ts="2026-08-02T10:10:00Z"),
            _event("stage_completed", ts="2026-08-02T10:30:00Z", payload={"stage": "framing"}),
        ],
    )

    metrics = collect(case_dir)

    assert metrics["wall_clock_s"] == 1800
    assert metrics["stages_completed"] == ["intake", "framing"]
    assert metrics["last_completed_stage"] == "framing"


def test_record_counts_come_from_the_unpack_events(case_dir: Path) -> None:
    _write(
        case_dir,
        [
            _event("evidence_batch_unpacked", payload={"record_count": 5}),
            _event("evidence_batch_unpacked", payload={"record_count": 4}),
            _event("assumption_batch_unpacked", payload={"record_count": 3}),
            _event("objection_batch_unpacked", payload={"objection_count": 2}),
        ],
    )

    metrics = collect(case_dir)

    assert metrics["records"] == {"evidence": 9, "assumptions": 3, "objections": 2}


def test_process_signals_summarise_the_deliberation(case_dir: Path) -> None:
    _write(
        case_dir,
        [
            _event(
                "stage_gate_evaluated",
                payload={"finding_count": 3, "blocking_checks": ["citations"], "stage": "review"},
            ),
            _event("stage_gate_evaluated", payload={"finding_count": 1, "blocking_checks": []}),
            _event("stop_decision_evaluated", payload={"action": "repair", "repair_cycle": 1}),
            _event("thesis_revision_recorded", payload={"revision": 1, "changed": False}),
            _event("thesis_revision_recorded", payload={"revision": 2, "changed": True}),
            _event("review_evaluated", payload={"outcome": "fail", "synthesis_retries": 1}),
            _event("dual_track_compared", payload={}),
        ],
    )

    process = collect(case_dir)["process"]

    assert process["gate_findings"] == 4
    assert process["gate_blocking_checks"] == 1
    assert process["repair_cycles"] == 1
    assert process["thesis_revisions"] == 2
    assert process["thesis_changes"] == 1
    assert process["synthesis_retries"] == 1
    assert process["dual_track"] == "compared"


def test_a_skipped_dual_track_is_distinguished_from_never_running_one(case_dir: Path) -> None:
    _write(case_dir, [_event("dual_track_skipped", payload={"reason": "validation failed"})])
    assert collect(case_dir)["process"]["dual_track"] == "skipped"

    _write(case_dir, [_event("stage_completed", payload={"stage": "intake"})])
    assert collect(case_dir)["process"]["dual_track"] == "absent"


def test_a_corrupt_line_is_skipped_rather_than_aborting_the_report(
    case_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (case_dir / "audit.jsonl").write_text(
        json.dumps(_invocation("intake", ts="2026-08-02T10:00:00Z")) + "\n{ not json\n",
        encoding="utf-8",
    )

    metrics = collect(case_dir)

    assert metrics["invocations"]["attempts"] == 1
    assert "not valid JSON" in capsys.readouterr().err


def test_a_missing_audit_log_is_reported_clearly(case_dir: Path) -> None:
    with pytest.raises(FileNotFoundError, match="No audit log"):
        collect(case_dir)


def test_coercion_events_are_extracted_from_audit_log(case_dir: Path) -> None:
    """Coercion accounting: the audit log records what the coercion layer changed."""
    _write(
        case_dir,
        [
            _invocation(
                "analyst",
                ts="2026-08-02T10:00:00Z",
                coercions=[
                    {"field": "method", "type": "enum_coerce", "from": "str", "to": "str"},
                    {
                        "field": "limitations",
                        "type": "list_item_flatten",
                        "from": "dict",
                        "to": "str",
                    },
                ],
            ),
            _invocation(
                "synthesizer",
                ts="2026-08-02T10:01:00Z",
                coercions=[
                    {
                        "field": "model_stability",
                        "type": "model_stability_fix",
                        "from": "dict",
                        "to": "dict",
                    },
                ],
            ),
            _invocation("intake", ts="2026-08-02T10:02:00Z"),
        ],
    )

    coercions = collect(case_dir)["coercions"]
    assert coercions["total"] == 3
    assert coercions["by_type"]["enum_coerce"] == 1
    assert coercions["by_type"]["list_item_flatten"] == 1
    assert coercions["by_type"]["model_stability_fix"] == 1
    assert coercions["by_role"]["analyst"] == 2
    assert coercions["by_role"]["synthesizer"] == 1
    assert coercions["by_field"]["method"] == 1
    assert coercions["by_field"]["limitations"] == 1


def test_no_coercion_events_means_empty_summary(case_dir: Path) -> None:
    _write(case_dir, [_invocation("intake", ts="2026-08-02T10:00:00Z")])
    coercions = collect(case_dir)["coercions"]
    assert coercions["total"] == 0
    assert coercions["by_type"] == {}
    assert coercions["by_role"] == {}
    assert coercions["by_field"] == {}
