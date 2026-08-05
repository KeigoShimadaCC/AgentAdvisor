"""Live progress events for a running invocation (SPEC-046).

The audit log records an invocation only when it *returns*, so before this the
stream was silent for the whole of the longest wait in the product — and
``LiveActivity`` inferred "running" from the last attempt whose status was not
``ok``, meaning a healthy long call rendered as the previous agent, greyed out
and marked completed.  These tests hold the two events that fix it, and the
property that matters most: a heartbeat can never outlive the call it describes.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from orchestrator.artifacts import AuditEvent
from orchestrator.backend import ResultStatus, RoleResult, StubBackend, TokenUsage
from orchestrator.invoke_role import _ProgressReporter, invoke
from orchestrator.service.lexicon import load_lexicon, translate_event
from tests.test_invocation import (
    _build_case,
    _evidence,
    _role_config,
    _task,
    _write_output,
)


def _audit(case_root: Path) -> list[AuditEvent]:
    lines = (case_root / "audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    return [AuditEvent.model_validate_json(line) for line in lines]


def _slow_result(delay_s: float) -> RoleResult:
    """A backend result that takes long enough to produce heartbeats."""
    time.sleep(delay_s)
    return RoleResult(
        status=ResultStatus.OK,
        result_text="ok",
        session_id="sess-slow",
        request_id="req-slow",
        duration_ms=int(delay_s * 1000),
        usage=TokenUsage(input_tokens=10, output_tokens=4, total_tokens=14),
        raw_stdout="{}",
        raw_stderr="",
        cli_version="test",
    )


# ── The two events ───────────────────────────────────────────────────────────


def test_started_precedes_the_attempt_it_describes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case, _ = _build_case(tmp_path, monkeypatch)
    config = _role_config(tmp_path)
    monkeypatch.setattr(
        "orchestrator.invoke_role.load_role_config", lambda _role, _variant=None: config
    )
    backend = StubBackend([_slow_result(0.0)], side_effects=[_write_output(_evidence())])

    invoke(case, "researcher", _task("T-042"), backend=backend)

    events = _audit(case.root)
    types = [e.event_type for e in events]
    assert types.index("role_invocation_started") < types.index("role_invocation_attempt")

    started = events[types.index("role_invocation_started")]
    assert started.payload["task_id"] == "T-042"
    assert started.payload["attempt"] == 1
    assert started.actor == "researcher"
    assert started.model == "composer-2.5"


def test_started_is_emitted_on_the_failure_path_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing attempt must still announce that it began.

    Otherwise the UI goes quiet exactly when a retry ladder is grinding, which
    is the moment a user most wants to know something is happening.
    """
    case, _ = _build_case(tmp_path, monkeypatch)
    config = _role_config(tmp_path)
    monkeypatch.setattr(
        "orchestrator.invoke_role.load_role_config", lambda _role, _variant=None: config
    )

    def _write_invalid(invocation) -> None:  # noqa: ANN001 — StubBackend passes RoleInvocation
        (invocation.workspace / "outputs" / "evidence_record.yaml").write_text(
            "not: valid", encoding="utf-8"
        )

    backend = StubBackend(
        [_slow_result(0.0), _slow_result(0.0)],
        side_effects=[_write_invalid, _write_output(_evidence())],
    )

    invoke(case, "researcher", _task("T-043"), backend=backend)

    started = [e for e in _audit(case.root) if e.event_type == "role_invocation_started"]
    assert [e.payload["attempt"] for e in started] == [1, 2]


def test_progress_heartbeats_while_a_call_is_in_flight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case, _ = _build_case(tmp_path, monkeypatch)
    monkeypatch.setattr("orchestrator.invoke_role.PROGRESS_INTERVAL_S", 0.05)
    config = _role_config(tmp_path)
    monkeypatch.setattr(
        "orchestrator.invoke_role.load_role_config", lambda _role, _variant=None: config
    )

    def _slow_write(invocation) -> None:  # noqa: ANN001 — StubBackend passes RoleInvocation
        time.sleep(0.3)
        _write_output(_evidence())(invocation)

    backend = StubBackend([_slow_result(0.0)], side_effects=[_slow_write])

    invoke(case, "researcher", _task("T-044"), backend=backend)

    progress = [e for e in _audit(case.root) if e.event_type == "role_invocation_progress"]
    assert progress, "a call lasting 6x the interval produced no heartbeat"
    assert all(e.payload["task_id"] == "T-044" for e in progress)
    assert all(e.payload["attempt"] == 1 for e in progress)
    assert all(e.payload["elapsed_s"] >= 0 for e in progress)


def test_no_progress_event_outlives_its_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The acceptance criterion: the last heartbeat precedes the attempt.

    A timer that survives its call would keep claiming an agent is running
    after it has finished — the same lie the old UI told, in the other
    direction.
    """
    case, _ = _build_case(tmp_path, monkeypatch)
    monkeypatch.setattr("orchestrator.invoke_role.PROGRESS_INTERVAL_S", 0.05)
    config = _role_config(tmp_path)
    monkeypatch.setattr(
        "orchestrator.invoke_role.load_role_config", lambda _role, _variant=None: config
    )

    def _slow_write(invocation) -> None:  # noqa: ANN001 — StubBackend passes RoleInvocation
        time.sleep(0.3)
        _write_output(_evidence())(invocation)

    backend = StubBackend([_slow_result(0.0)], side_effects=[_slow_write])
    before = threading.active_count()

    invoke(case, "researcher", _task("T-045"), backend=backend)
    time.sleep(0.2)  # any surviving timer would fire several times over

    events = _audit(case.root)
    types = [e.event_type for e in events]
    last_progress = max(i for i, t in enumerate(types) if t == "role_invocation_progress")
    attempt = types.index("role_invocation_attempt")
    assert last_progress < attempt, "a heartbeat was written after the attempt closed"
    assert threading.active_count() <= before, "the progress thread was not joined"


def test_a_failing_audit_write_cannot_fail_the_invocation(tmp_path: Path) -> None:
    """A broken heartbeat must not turn a healthy agent run into a retry."""

    class _ExplodingCase:
        root = tmp_path

        def audit(self, _event: AuditEvent) -> None:
            raise OSError("disk full")

    reporter = _ProgressReporter(
        case=_ExplodingCase(),  # type: ignore[arg-type]
        role="researcher",
        task_id="T-046",
        attempt=1,
        model="composer-2.5",
        interval_s=0.01,
    )
    with reporter:
        time.sleep(0.1)
    # Reaching here at all is the assertion: the reporter swallowed its error
    # and stopped cleanly instead of propagating into the invocation.


# ── Presentation ─────────────────────────────────────────────────────────────


def test_both_events_are_user_facing_in_the_lexicon() -> None:
    """They must reach the default feed, not the Method-room filter.

    An event whose entire purpose is to say "work is happening" is useless
    behind a technical filter.
    """
    lexicon = load_lexicon()
    for event_type in ("role_invocation_started", "role_invocation_progress"):
        assert event_type in lexicon, f"{event_type} has no lexicon entry"
        assert lexicon[event_type].technical is False

    translated = translate_event(
        {
            "event_type": "role_invocation_progress",
            "actor": "researcher",
            "payload": {"task_id": "T-001", "attempt": 1, "elapsed_s": 42.0},
        },
        line_cursor=7,
    )
    assert translated.technical is False
    assert "T-001" in translated.message
    assert "—" not in translated.message, "a slot went unfilled"
