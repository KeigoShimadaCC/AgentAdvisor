"""Audit log tailer and SSE event stream (SPEC-033).

The audit log (``audit.jsonl``) is the engine's only live, per-event-flushed
chronology.  This module turns it into the UI's nervous system:

- :class:`AuditTailer` — a line-number-cursor tailer that survives
  append-only writes (no rotation handling is needed because the audit log is
  append-only).
- :func:`sse_event_stream` — an SSE generator that replays missed events from
  ``since`` then tails live, emitting a 15 s heartbeat.
- :func:`replay_stream` — re-emits a recorded case's audit events on recorded
  inter-event timing × speed factor (replay mode).

Cursors are audit line numbers (1-based), so "what happened while I was away"
and reconnects are the same code path.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any

from orchestrator.service.lexicon import translate_event

__all__ = [
    "AuditTailer",
    "SSE_HEARTBEAT_INTERVAL_S",
    "sse_event_stream",
    "replay_stream",
    "format_sse",
]

SSE_HEARTBEAT_INTERVAL_S = 15.0
_TAIL_POLL_INTERVAL_S = 0.5


def _parse_timestamp(ts: str | None) -> float:
    """Parse an ISO-8601 timestamp to a POSIX float, tolerant of missing tz."""
    if not ts:
        return 0.0
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return 0.0


def format_sse(data: dict[str, Any]) -> str:
    """Format one SSE ``data:`` frame.

    The payload is JSON-encoded on a single line (no embedded newlines) so it
    is a single SSE event.
    """
    payload = json.dumps(data, separators=(",", ":"), sort_keys=True)
    return f"data: {payload}\n\n"


class AuditTailer:
    """Read new audit lines past a line-number cursor.

    Line numbers are 1-based; ``since=0`` means "from the beginning".  The
    tailer is a thin wrapper over file reads so it can be used synchronously
    inside an async generator.
    """

    def __init__(self, audit_path: Path) -> None:
        self._path = audit_path

    def read_since(self, since: int) -> list[tuple[int, dict[str, Any]]]:
        """Return ``(line_number, parsed_event)`` for lines after ``since``.

        ``since`` is the last line number already delivered.  Lines are 1-based.
        Blank or unparseable lines are skipped (their line numbers are still
        counted so cursors stay aligned with file offsets).
        """
        if not self._path.exists():
            return []
        events: list[tuple[int, dict[str, Any]]] = []
        with self._path.open("r", encoding="utf-8") as fh:
            for line_number, line in enumerate(fh, start=1):
                if line_number <= since:
                    continue
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    events.append((line_number, json.loads(stripped)))
                except json.JSONDecodeError:
                    continue
        return events


async def sse_event_stream(
    audit_path: Path,
    since: int = 0,
    *,
    heartbeat_interval: float = SSE_HEARTBEAT_INTERVAL_S,
    poll_interval: float = _TAIL_POLL_INTERVAL_S,
    stop_event: asyncio.Event | None = None,
) -> AsyncIterator[str]:
    """Yield SSE frames for an audit log, starting from ``since``.

    First emits all buffered lines past ``since`` (cold catch-up), then tails
    the file for new lines.  A heartbeat comment is emitted every
    ``heartbeat_interval`` seconds of inactivity.
    """
    tailer = AuditTailer(audit_path)
    cursor = since
    last_emit = time.monotonic()

    while True:
        if stop_event is not None and stop_event.is_set():
            return

        new_events = tailer.read_since(cursor)
        for line_number, raw_event in new_events:
            cursor = line_number
            translated = translate_event(raw_event, line_cursor=line_number)
            yield format_sse(translated.model_dump(mode="json"))
            last_emit = time.monotonic()

        if not new_events:
            idle = time.monotonic() - last_emit
            if idle >= heartbeat_interval:
                yield ": heartbeat\n\n"
                last_emit = time.monotonic()
            await asyncio.sleep(poll_interval)
        # else: loop immediately in case more lines are available.


async def replay_stream(
    audit_path: Path,
    since: int = 0,
    *,
    speed: float = 60.0,
    stop_event: asyncio.Event | None = None,
) -> AsyncIterator[str]:
    """Re-emit a recorded case's audit events on recorded inter-event timing.

    Inter-event delays are taken from the recorded timestamps and divided by
    ``speed`` so a 30-minute case can be replayed in seconds.  Events before
    ``since`` are skipped, but their timing anchor is preserved so delays are
    measured relative to the original wall clock.
    """
    tailer = AuditTailer(audit_path)
    events = tailer.read_since(since)

    prev_ts: float | None = None
    for line_number, raw_event in events:
        if stop_event is not None and stop_event.is_set():
            return

        ts = _parse_timestamp(raw_event.get("ts"))
        if prev_ts is not None and ts > 0:
            delay = max(0.0, (ts - prev_ts) / speed)
            await asyncio.sleep(delay)
        prev_ts = ts if ts > 0 else prev_ts

        translated = translate_event(raw_event, line_cursor=line_number)
        yield format_sse(translated.model_dump(mode="json"))


def read_all_events(audit_path: Path) -> list[tuple[int, dict[str, Any]]]:
    """Convenience: read every parseable audit line with its 1-based number."""
    return AuditTailer(audit_path).read_since(0)
