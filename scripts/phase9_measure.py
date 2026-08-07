"""Phase 9's measured claims (SPEC-056).

Phase 9's central complaint was that a three-hour run showed nothing while it
ran.  The claim that this changed is the one a screenshot cannot settle and an
opinion should not, so this computes it.

**The measure.**  Walk the run second by second and ask, at each second,
whether the interface could name the role that is running *right now*.  It can
if a role-naming event landed within :data:`PROGRESS_INTERVAL_S` and no newer
invocation has started since — an event older than the heartbeat cadence, or
one describing an invocation that has already been superseded, means the screen
is guessing.

**Why it is computed from durations rather than from event kinds.**  A
before/after claim needs a "before" measured on a run that predates the change.
Filtering SPEC-046's events out of an after-log would answer a different and
much easier question, because such a log only exists for runs that already had
the fix.  Every log ever written carries ``role_invocation_attempt`` with a
``duration_ms``, and that is enough to place both timelines exactly:

  - *before* — one mark per invocation, at the instant it **returned**;
  - *after*  — a mark when it **started**, one every ``PROGRESS_INTERVAL_S``
    while it ran, and one when it returned.

So the two figures are computed from the same log, and the "before" figure is
what the old interface really had.

Usage::

    uv run python scripts/phase9_measure.py <case-dir> [<case-dir> ...]
    uv run python scripts/phase9_measure.py --profile 45 178.4 191   # N, in-flight min, wall min
    uv run python scripts/phase9_measure.py --self-check <case-dir>
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# SPEC-046's heartbeat cadence.  An interface can name the running role
# accurately for this long after an event before it is guessing.
PROGRESS_INTERVAL_S = 20.0


@dataclass(frozen=True)
class Invocation:
    """One backend call, placed on the run's timeline."""

    role: str
    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


# ── Reading ──────────────────────────────────────────────────────────────────


def read_events(case_dir: Path) -> list[dict]:
    path = case_dir / "audit.jsonl"
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def ts(event: dict) -> datetime | None:
    raw = event.get("ts")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def timeline(events: list[dict]) -> tuple[float, list[Invocation]]:
    """The run's wall clock, and every invocation placed on it.

    An invocation's end is the timestamp of its ``role_invocation_attempt``;
    its start is that instant minus the ``duration_ms`` the backend reported.
    """
    stamps = [t for t in (ts(e) for e in events) if t is not None]
    if len(stamps) < 2:
        return 0.0, []
    origin = min(stamps)
    wall_s = (max(stamps) - origin).total_seconds()

    invocations = []
    for event in events:
        if event.get("event_type") != "role_invocation_attempt":
            continue
        end = ts(event)
        if end is None:
            continue
        end_s = (end - origin).total_seconds()
        duration_s = float(event.get("duration_ms") or 0) / 1000.0
        invocations.append(
            Invocation(
                role=str(event.get("actor") or "?"),
                start_s=max(0.0, end_s - duration_s),
                end_s=end_s,
            )
        )
    return wall_s, sorted(invocations, key=lambda i: i.start_s)


# ── The measure ──────────────────────────────────────────────────────────────


def covered_seconds(
    wall_s: float,
    invocations: list[Invocation],
    *,
    live_marks: bool,
) -> float:
    """Seconds of the run during which the screen could name the running role.

    ``live_marks`` is the difference between the two worlds.  With it, an
    invocation reports itself throughout: the whole of its duration is covered.
    Without it, the only mark is the one it leaves on returning, which covers
    the ``PROGRESS_INTERVAL_S`` that follows — and stops the moment the next
    invocation begins, because from then on the named role is the wrong one.
    """
    if wall_s <= 0 or not invocations:
        return 0.0

    covered = 0.0
    for index, invocation in enumerate(invocations):
        next_start = invocations[index + 1].start_s if index + 1 < len(invocations) else wall_s
        if live_marks:
            # Started, then a heartbeat every interval, then the attempt: the
            # call describes itself for as long as it runs.
            covered += min(invocation.end_s, wall_s) - invocation.start_s
        # Either way the returning attempt names a real, current activity for
        # the cadence that follows — until the next call starts, after which
        # it names something that is no longer running.
        trailing_end = min(invocation.end_s + PROGRESS_INTERVAL_S, next_start, wall_s)
        covered += max(0.0, trailing_end - invocation.end_s)
    return covered


def coverage(wall_s: float, invocations: list[Invocation], *, live_marks: bool) -> float:
    if wall_s <= 0:
        return 0.0
    return covered_seconds(wall_s, invocations, live_marks=live_marks) / wall_s


def profile_coverage(
    invocation_count: int, in_flight_s: float, wall_s: float
) -> tuple[float, float]:
    """The same measure for a run recorded as totals rather than as a log.

    The real case of SPEC-020 is gitignored and no longer on disk; what survives
    is its ``case_metrics.py`` table — invocation count, summed in-flight time,
    wall clock.  Individual gaps are unrecoverable, so this returns the pair of
    figures those totals *bound*, spreading the idle time evenly:

      - **before** is at most ``min(N × interval, idle)`` — one cadence window
        per invocation, and never more than the idle time there is to fill;
      - **after** is at least ``in_flight / wall`` — every second of every call
        is covered, before counting any trailing window.

    Both are stated as bounds in the report, because that is what the surviving
    record supports.
    """
    if wall_s <= 0 or invocation_count <= 0:
        return 0.0, 0.0
    idle_s = max(0.0, wall_s - in_flight_s)
    before = min(invocation_count * PROGRESS_INTERVAL_S, idle_s) / wall_s
    after = min(1.0, in_flight_s / wall_s)
    return before, after


# ── Self-check ───────────────────────────────────────────────────────────────


def self_check(events: list[dict]) -> tuple[int, int, str]:
    """Does the reconstruction agree with the events the run actually emitted?

    On a post-SPEC-046 log both exist: a real ``role_invocation_started`` and a
    start reconstructed from the attempt's ``duration_ms``.  They must describe
    the same instant, or the "before" figure computed from durations is not
    measuring the same timeline as the "after" figure.
    """
    real = sum(1 for e in events if e.get("event_type") == "role_invocation_started")
    _, invocations = timeline(events)
    if real == 0:
        return 0, len(invocations), "log predates SPEC-046: nothing to check against"
    if real != len(invocations):
        return real, len(invocations), "MISMATCH: started events and attempts do not pair"
    return real, len(invocations), "every invocation pairs a started event with an attempt"


# ── Loops ────────────────────────────────────────────────────────────────────


def loops(events: list[dict]) -> dict[str, int]:
    """Rounds that repeat a stage — the ones a linear progress bar cannot show."""
    counts = {"repair": 0, "resynthesis": 0, "rescope": 0}
    for event in events:
        kind = event.get("event_type")
        payload = event.get("payload") or {}
        if kind == "stop_decision_evaluated" and payload.get("outcome") == "repair":
            counts["repair"] += 1
        elif kind == "review_evaluated" and payload.get("outcome") not in {
            "accept",
            "accepted",
            None,
        }:
            counts["resynthesis"] += 1
        elif kind == "framing_revision_requested":
            counts["rescope"] += 1
    return counts


# ── CLI ──────────────────────────────────────────────────────────────────────


def report(case_dir: Path, *, check: bool) -> None:
    events = read_events(case_dir)
    if not events:
        print(f"{case_dir.name}: no audit events")
        return

    wall_s, invocations = timeline(events)
    in_flight = sum(i.duration_s for i in invocations)
    before = coverage(wall_s, invocations, live_marks=False)
    after = coverage(wall_s, invocations, live_marks=True)
    loop_counts = loops(events)

    print(f"{case_dir.name}")
    print(f"  events                     {len(events)}")
    print(f"  wall clock                 {wall_s:.1f}s")
    print(f"  invocations                {len(invocations)}")
    print(
        f"  in flight                  {in_flight:.1f}s ({in_flight / wall_s:.1%})"
        if wall_s
        else "  in flight                  0.0s"
    )
    print(f"  activity coverage, before  {before:.1%}")
    print(f"  activity coverage, after   {after:.1%}")
    print(
        f"  loops (repair/resynth/rescope) "
        f"{loop_counts['repair']}/{loop_counts['resynthesis']}/{loop_counts['rescope']}"
    )
    if check:
        real, reconstructed, note = self_check(events)
        print(f"  self-check                 {real} started / {reconstructed} attempts — {note}")


def main(argv: list[str]) -> int:
    args = argv[1:]
    if not args:
        print(__doc__)
        return 2

    if args[0] == "--profile":
        if len(args) != 4:
            print("usage: --profile <invocations> <in-flight-minutes> <wall-minutes>")
            return 2
        count = int(args[1])
        in_flight_s = float(args[2]) * 60
        wall_s = float(args[3]) * 60
        before, after = profile_coverage(count, in_flight_s, wall_s)
        print(
            f"recorded profile: {count} invocations, "
            f"{in_flight_s / 60:.1f} min in flight, {wall_s / 60:.1f} min wall clock"
        )
        print(f"  activity coverage, before  at most  {before:.1%}")
        print(f"  activity coverage, after   at least {after:.1%}")
        return 0

    check = args[0] == "--self-check"
    if check:
        args = args[1:]
    if not args:
        print("usage: --self-check <case-dir> [...]")
        return 2

    for arg in args:
        report(Path(arg), check=check)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
