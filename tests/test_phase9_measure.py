"""The phase 9 measurement instrument, checked against known answers (SPEC-056).

A before/after report is only worth as much as the thing that computed it. Every
case here has an answer that can be worked out by hand from the timeline in its
docstring, so a change to the measure that flatters the phase fails a test
rather than producing a better-looking number.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts.phase9_measure import (
    PROGRESS_INTERVAL_S,
    Invocation,
    coverage,
    profile_coverage,
    self_check,
    timeline,
)

ORIGIN = datetime(2026, 8, 7, 12, 0, 0, tzinfo=UTC)


def _at(offset_s: float) -> str:
    return (ORIGIN + timedelta(seconds=offset_s)).isoformat().replace("+00:00", "Z")


def _attempt(role: str, end_s: float, duration_s: float) -> dict:
    return {
        "ts": _at(end_s),
        "actor": role,
        "event_type": "role_invocation_attempt",
        "payload": {"status": "ok"},
        "duration_ms": int(duration_s * 1000),
    }


def _started(role: str, start_s: float) -> dict:
    return {
        "ts": _at(start_s),
        "actor": role,
        "event_type": "role_invocation_started",
        "payload": {},
    }


def _marker(offset_s: float) -> dict:
    """A non-invocation event, present only to pin the run's wall clock."""
    return {"ts": _at(offset_s), "actor": "control", "event_type": "stage_completed", "payload": {}}


def _write(tmp_path: Path, events: list[dict]) -> Path:
    case_dir = tmp_path / "case-001-measure"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "audit.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8"
    )
    return case_dir


class TestTimeline:
    def test_places_an_invocation_by_working_back_from_its_return(self) -> None:
        """The attempt lands when the call *returns*; the call began before it.

        This is the whole reason the old interface was dark: the only event a
        60-second call produced arrived once it was already over.
        """
        wall_s, invocations = timeline([_marker(0), _attempt("analyst", 60, 60), _marker(300)])
        assert wall_s == 300
        assert invocations == [Invocation(role="analyst", start_s=0.0, end_s=60.0)]

    def test_a_missing_duration_collapses_the_call_to_an_instant(self) -> None:
        # An old log without duration_ms must not be silently credited with
        # coverage it never had.
        _, invocations = timeline([_marker(0), _attempt("analyst", 60, 0), _marker(300)])
        assert invocations[0].start_s == invocations[0].end_s == 60.0


class TestCoverage:
    """Timeline: three 60s calls at 0-60, 100-160, 200-260, over a 300s run.

    before — one mark per call, at 60, 160 and 260, each good for the 20s
             cadence that follows: 3 x 20 = 60s of 300.
    after  — every second of every call, 3 x 60 = 180s, plus the same three
             trailing windows: 240s of 300.
    """

    EVENTS = [
        _marker(0),
        _attempt("researcher", 60, 60),
        _attempt("analyst", 160, 60),
        _attempt("director", 260, 60),
        _marker(300),
    ]

    def test_before(self) -> None:
        wall_s, invocations = timeline(self.EVENTS)
        assert coverage(wall_s, invocations, live_marks=False) == 60 / 300

    def test_after(self) -> None:
        wall_s, invocations = timeline(self.EVENTS)
        assert coverage(wall_s, invocations, live_marks=True) == 240 / 300

    def test_the_gap_between_them_is_the_time_spent_inside_calls(self) -> None:
        # Which is the claim: the phase did not make the waiting shorter, it
        # made the waiting legible.
        wall_s, invocations = timeline(self.EVENTS)
        before = coverage(wall_s, invocations, live_marks=False)
        after = coverage(wall_s, invocations, live_marks=True)
        in_flight = sum(i.duration_s for i in invocations)
        assert after - before == pytest.approx(in_flight / wall_s)


class TestSupersession:
    def test_a_finished_role_stops_counting_once_the_next_one_starts(self) -> None:
        """Naming a role that has already handed over is not coverage.

        Call A ends at 60, call B starts at 65. A's mark is accurate for five
        seconds, not for the full cadence — after 65 the screen names a role
        that is no longer the one running.
        """
        events = [_marker(0), _attempt("a", 60, 60), _attempt("b", 125, 60), _marker(300)]
        wall_s, invocations = timeline(events)
        # A contributes 5s of trailing coverage, B the full 20s: 25s of 300.
        assert coverage(wall_s, invocations, live_marks=False) == 25 / 300

    def test_back_to_back_calls_leave_the_old_interface_at_zero(self) -> None:
        # The pathological case the phase existed to fix: a run that is always
        # inside some call shows nothing at all under the old event set.
        events = [_marker(0), _attempt("a", 150, 150), _attempt("b", 300, 150), _marker(300)]
        wall_s, invocations = timeline(events)
        assert coverage(wall_s, invocations, live_marks=False) == 0.0
        assert coverage(wall_s, invocations, live_marks=True) == 1.0


class TestEdges:
    def test_a_run_with_no_invocations_is_zero_both_ways(self) -> None:
        wall_s, invocations = timeline([_marker(0), _marker(300)])
        assert coverage(wall_s, invocations, live_marks=False) == 0.0
        assert coverage(wall_s, invocations, live_marks=True) == 0.0

    def test_coverage_never_exceeds_the_run(self) -> None:
        # A trailing window that runs off the end of the log must be clipped,
        # or a short run reports more than 100%.
        events = [_marker(0), _attempt("a", 95, 90), _marker(100)]
        wall_s, invocations = timeline(events)
        assert coverage(wall_s, invocations, live_marks=True) <= 1.0
        assert coverage(wall_s, invocations, live_marks=False) <= 1.0

    def test_the_cadence_is_the_one_the_orchestrator_emits(self) -> None:
        # If SPEC-046's interval changes and this constant does not, the
        # measure silently starts describing an interface that does not exist.
        from orchestrator.invoke_role import PROGRESS_INTERVAL_S as EMITTED

        assert PROGRESS_INTERVAL_S == EMITTED


class TestProfile:
    def test_bounds_a_run_recorded_only_as_totals(self) -> None:
        """SPEC-020's real case: 45 invocations, 178.4 min in flight, 191 min.

        Idle time is 12.6 min = 756s, which is less than 45 x 20s = 900s, so
        the old interface's ceiling is the idle time itself.
        """
        before, after = profile_coverage(45, 178.4 * 60, 191 * 60)
        assert before == pytest.approx((191 - 178.4) / 191)
        assert round(before, 3) == 0.066
        assert round(after, 3) == 0.934

    def test_the_ceiling_is_the_cadence_when_idle_time_is_plentiful(self) -> None:
        # Few, short calls in a long run: the limit is what the marks cover,
        # not how much idle time there is.
        before, _ = profile_coverage(2, 10, 1_000)
        assert before == 2 * PROGRESS_INTERVAL_S / 1_000


class TestSelfCheck:
    def test_pairs_every_reconstructed_start_with_a_real_one(self, tmp_path: Path) -> None:
        events = [
            _marker(0),
            _started("a", 0),
            _attempt("a", 60, 60),
            _started("b", 100),
            _attempt("b", 160, 60),
            _marker(300),
        ]
        real, reconstructed, note = self_check(events)
        assert (real, reconstructed) == (2, 2)
        assert "MISMATCH" not in note

    def test_says_so_when_a_log_predates_the_change(self) -> None:
        real, reconstructed, note = self_check([_marker(0), _attempt("a", 60, 60), _marker(300)])
        assert real == 0
        assert reconstructed == 1
        assert "predates" in note

    def test_flags_a_log_where_they_do_not_pair(self) -> None:
        # A dropped start event would make the after-figure describe a timeline
        # the run never had.
        events = [_marker(0), _started("a", 0), _attempt("a", 60, 60), _attempt("b", 160, 60)]
        _, _, note = self_check(events)
        assert "MISMATCH" in note

    def test_reads_a_case_directory_from_disk(self, tmp_path: Path) -> None:
        from scripts.phase9_measure import read_events

        case_dir = _write(tmp_path, [_marker(0), _attempt("a", 60, 60), _marker(300)])
        assert len(read_events(case_dir)) == 3
        assert read_events(tmp_path / "case-999-absent") == []
