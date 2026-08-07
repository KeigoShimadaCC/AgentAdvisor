"""Chart exhibits for the case deck (SPEC-057).

matplotlib is an optional dependency (the ``deck`` group). When it is importable
this module renders the deck's chart PNGs through the consulting-deck skill's
``chart_style`` helpers, so deck charts match the hand-built decks exactly. When
it is absent, :func:`render_charts` reports ``available=False`` and the template
falls back to HTML/CSS table exhibits — a default install still yields a complete
deck, only with tables where the charts would be.

Nothing here raises on a missing toolchain; absence is a return value, not an
exception, because deck generation must never be able to fail a delivered case.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from orchestrator.artifacts import FinalRecommendation

#: The repo-local skill that owns the chart theme and slot sizes.
SKILL_DIR = Path(__file__).resolve().parents[1] / ".factory" / "skills" / "consulting-deck"
_SKILL_SCRIPTS = SKILL_DIR / "scripts"


@dataclass(slots=True)
class ChartResult:
    """Which chart PNGs were produced, and why any were not."""

    available: bool
    #: Logical name -> filename (relative to the charts dir), for produced charts.
    files: dict[str, str] = field(default_factory=dict)
    reason: str | None = None


def _scenario_labels_and_probs(rec: FinalRecommendation) -> tuple[list[str], list[float]]:
    labels: list[str] = []
    probs: list[float] = []
    for scenario in rec.scenario_analysis:
        estimate = scenario.probability
        if estimate.point is None:
            continue
        labels.append(scenario.scenario_name.replace("_", " ").title())
        probs.append(estimate.point)
    return labels, probs


def render_charts(rec: FinalRecommendation, charts_dir: Path) -> ChartResult:
    """Render the deck's chart PNGs into ``charts_dir``.

    Returns a :class:`ChartResult`; ``available=False`` means matplotlib could not
    be imported (or the skill theme was unavailable) and the caller should render
    table exhibits instead.
    """
    if str(_SKILL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SKILL_SCRIPTS))
    try:
        # chart_style imports matplotlib at module load, so this import is the
        # single point that decides whether charts are available.
        from chart_style import (  # type: ignore[import-not-found]
            save,
            scenario_bars,
            use_deck_style,
        )
    except Exception as exc:  # noqa: BLE001 — any import failure means "no charts".
        return ChartResult(available=False, reason=f"matplotlib unavailable: {exc}")

    try:
        use_deck_style()
        charts_dir.mkdir(parents=True, exist_ok=True)
        files: dict[str, str] = {}

        labels, probs = _scenario_labels_and_probs(rec)
        if labels:
            focus = _base_case_label(labels)
            fig, _ax = scenario_bars(labels, probs, focus=focus, slot="split")
            save(fig, charts_dir / "scenarios.png")
            files["scenarios"] = "scenarios.png"

        return ChartResult(available=True, files=files)
    except Exception as exc:  # noqa: BLE001 — a render failure degrades, never raises.
        return ChartResult(available=False, reason=f"chart render failed: {exc}")


def _base_case_label(labels: list[str]) -> str:
    """Pick the label to highlight: the base case if named, else the first."""
    for label in labels:
        if "base" in label.lower():
            return label
    return labels[0]
