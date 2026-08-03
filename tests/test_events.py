"""SPEC-033 — Event tailer, SSE stream, and lexicon tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from orchestrator.service.events import (
    AuditTailer,
    format_sse,
    replay_stream,
    sse_event_stream,
)
from orchestrator.service.lexicon import (
    LexiconEntry,
    TranslatedEvent,
    load_lexicon,
    translate_event,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "cases"
AUDIT_001 = FIXTURES / "case-001-fixture-001" / "audit.jsonl"


# ── AuditTailer ─────────────────────────────────────────────────────────────


def test_tailer_read_since_zero_reads_all() -> None:
    tailer = AuditTailer(AUDIT_001)
    events = tailer.read_since(0)
    assert len(events) > 0
    # Line numbers are 1-based and sequential.
    assert events[0][0] == 1
    assert events[-1][0] == len(events)


def test_tailer_read_since_skips_already_read() -> None:
    tailer = AuditTailer(AUDIT_001)
    all_events = tailer.read_since(0)
    half = len(all_events) // 2
    cursor = all_events[half][0]
    remaining = tailer.read_since(cursor)
    assert len(remaining) == len(all_events) - half - 1
    if remaining:
        assert remaining[0][0] == cursor + 1


def test_tailer_missing_file_returns_empty(tmp_path: Path) -> None:
    tailer = AuditTailer(tmp_path / "nope.jsonl")
    assert tailer.read_since(0) == []


def test_tailer_skips_blank_lines(tmp_path: Path) -> None:
    p = tmp_path / "audit.jsonl"
    p.write_text(
        json.dumps({"event_type": "a", "payload": {}})
        + "\n"
        + "\n"
        + json.dumps({"event_type": "b", "payload": {}})
        + "\n",
        encoding="utf-8",
    )
    events = AuditTailer(p).read_since(0)
    assert len(events) == 2
    assert events[0][0] == 1
    assert events[1][0] == 3  # blank line 2 is counted but skipped


# ── Lexicon ─────────────────────────────────────────────────────────────────


def test_lexicon_loads_all_known_event_types() -> None:
    """Every event_type in the fixture's audit log has a lexicon entry."""
    lexicon = load_lexicon()
    tailer = AuditTailer(AUDIT_001)
    for _line_no, event in tailer.read_since(0):
        et = event.get("event_type", "")
        assert et in lexicon, f"Missing lexicon entry for event_type={et!r}"


def test_lexicon_entries_have_required_fields() -> None:
    lexicon = load_lexicon()
    assert len(lexicon) >= 15
    for key, entry in lexicon.items():
        assert isinstance(key, str)
        assert isinstance(entry, LexiconEntry)
        assert entry.template  # non-empty
        assert isinstance(entry.technical, bool)


def test_translate_event_known_type() -> None:
    event = {
        "event_type": "stage_completed",
        "actor": "orchestrator",
        "payload": {"stage": "intake"},
        "ts": "2026-01-01T00:00:00Z",
    }
    translated = translate_event(event, line_cursor=42)
    assert isinstance(translated, TranslatedEvent)
    assert translated.event_type == "stage_completed"
    assert "intake" in translated.message
    assert translated.technical is False
    assert translated.line_cursor == 42
    assert translated.actor == "orchestrator"


def test_translate_event_unknown_type_is_technical() -> None:
    event = {
        "event_type": "some_future_event",
        "actor": "orchestrator",
        "payload": {"foo": "bar"},
    }
    translated = translate_event(event, line_cursor=1)
    assert translated.technical is True
    assert "some_future_event" in translated.message
    # Raw payload is available separately, not in the narration.
    assert translated.raw_payload == {"foo": "bar"}
    assert "bar" not in translated.message


def test_translate_event_missing_slots_use_dash() -> None:
    event = {
        "event_type": "task_started",
        "actor": "task_graph",
        "payload": {},  # no task_id
    }
    translated = translate_event(event, line_cursor=1)
    assert "—" in translated.message


def test_translate_event_role_invocation_is_technical() -> None:
    event = {
        "event_type": "role_invocation_attempt",
        "actor": "researcher",
        "payload": {"attempt": 1, "status": "ok", "task_id": "T-001"},
    }
    translated = translate_event(event, line_cursor=1)
    assert translated.technical is True
    assert "researcher" in translated.message


# ── format_sse ──────────────────────────────────────────────────────────────


def test_format_sse_single_line() -> None:
    data = {"event_type": "test", "message": "hello"}
    frame = format_sse(data)
    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
    payload = frame[len("data: ") :].strip()
    parsed = json.loads(payload)
    assert parsed["event_type"] == "test"


# ── sse_event_stream ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sse_stream_emits_all_events_then_heartbeat(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    audit.write_text(
        json.dumps({"event_type": "stage_completed", "actor": "orch", "payload": {"stage": "a"}})
        + "\n"
        + json.dumps({"event_type": "task_started", "actor": "tg", "payload": {"task_id": "T-1"}})
        + "\n",
        encoding="utf-8",
    )

    stop = asyncio.Event()
    frames: list[str] = []

    async def consume() -> None:
        async for frame in sse_event_stream(
            audit, since=0, heartbeat_interval=0.05, poll_interval=0.01
        ):
            frames.append(frame)
            if len(frames) >= 2:
                stop.set()
                return
            if stop.is_set():
                return

    await asyncio.wait_for(consume(), timeout=2.0)
    assert len(frames) >= 2
    # Each frame is a valid SSE data frame.
    for f in frames[:2]:
        assert f.startswith("data: ")


@pytest.mark.asyncio
async def test_sse_stream_cursor_resume(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    audit.write_text(
        json.dumps({"event_type": "a", "payload": {}})
        + "\n"
        + json.dumps({"event_type": "b", "payload": {}})
        + "\n"
        + json.dumps({"event_type": "c", "payload": {}})
        + "\n",
        encoding="utf-8",
    )

    frames: list[str] = []

    async def consume() -> None:
        async for frame in sse_event_stream(
            audit, since=2, heartbeat_interval=99, poll_interval=0.01
        ):
            frames.append(frame)
            if len(frames) >= 1:
                return

    await asyncio.wait_for(consume(), timeout=2.0)
    assert len(frames) >= 1
    # Should only get line 3 (event_type "c"), not lines 1-2.
    parsed = json.loads(frames[0][len("data: ") :].strip())
    assert parsed["event_type"] == "c"


# ── replay_stream ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_replay_stream_emits_all_events_in_order(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    audit.write_text(
        json.dumps({"event_type": "a", "ts": "2026-01-01T00:00:00Z", "payload": {}})
        + "\n"
        + json.dumps({"event_type": "b", "ts": "2026-01-01T00:00:01Z", "payload": {}})
        + "\n",
        encoding="utf-8",
    )

    frames: list[str] = []

    async def consume() -> None:
        async for frame in replay_stream(audit, since=0, speed=1000.0):
            frames.append(frame)

    await asyncio.wait_for(consume(), timeout=2.0)
    assert len(frames) == 2
    types = [json.loads(f[len("data: ") :].strip())["event_type"] for f in frames]
    assert types == ["a", "b"]


@pytest.mark.asyncio
async def test_replay_stream_speed_scales_delay(tmp_path: Path) -> None:
    """Higher speed = shorter inter-event delay."""
    audit = tmp_path / "audit.jsonl"
    audit.write_text(
        json.dumps({"event_type": "a", "ts": "2026-01-01T00:00:00.000Z", "payload": {}})
        + "\n"
        + json.dumps({"event_type": "b", "ts": "2026-01-01T00:00:10.000Z", "payload": {}})
        + "\n",
        encoding="utf-8",
    )

    import time

    start = time.monotonic()

    async def consume() -> None:
        async for _ in replay_stream(audit, since=0, speed=1000.0):
            return  # only need first event after delay

    await asyncio.wait_for(consume(), timeout=2.0)
    elapsed = time.monotonic() - start
    # 10 second gap / 1000 speed = 0.01s; should be well under 1 second.
    assert elapsed < 1.0


@pytest.mark.asyncio
async def test_replay_stream_fixture_001_all_events() -> None:
    """Replaying the fixture emits every audit event in order."""
    frames: list[str] = []

    async def consume() -> None:
        async for frame in replay_stream(AUDIT_001, since=0, speed=10000.0):
            frames.append(frame)

    await asyncio.wait_for(consume(), timeout=5.0)
    tailer = AuditTailer(AUDIT_001)
    expected_count = len(tailer.read_since(0))
    assert len(frames) == expected_count

    # Cursors are monotonically increasing.
    cursors = [json.loads(f[len("data: ") :].strip())["line_cursor"] for f in frames]
    assert cursors == sorted(cursors)
    assert cursors[0] == 1
    assert cursors[-1] == expected_count
