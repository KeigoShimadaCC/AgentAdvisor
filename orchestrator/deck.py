"""Deterministic deck deliverable for a completed case (SPEC-057).

Renders a completed case's ``FinalRecommendation`` and its supporting artifacts
into a board-ready deck: an editable PowerPoint and the authored HTML always,
plus a print PDF and per-slide PNGs when the render toolchain is present. Reads
artifacts through the typed ``Case`` API, so it is unaffected by whether an
artifact lives under ``shared/`` or ``outputs/``.

Two entry points:

* :func:`build_deck` does the work and may raise (used by ``advisor deck``).
* :func:`generate_deck_for_case` wraps it non-fatally for the pipeline: any
  failure is audited and swallowed, because a delivered case must never be
  downgraded to failed by deck tooling. This mirrors ``_record_into_memory``.

The toolchain is layered and degrades rather than failing:

1. ``slides.html`` + ``deck.pptx.html`` (+ ``deck.preview.html``) come from the
   skill's standard-library-only ``build_deck.py`` and must always succeed.
2. Chart PNGs need matplotlib; absent it, the template renders table exhibits.
3. ``deck.pdf`` + PNGs + ``report.json`` come from ``render_deck.mjs`` (Node +
   Playwright Chromium); absent that, the tier is skipped.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from orchestrator.artifacts import (
    AssumptionRecord,
    AuditEvent,
    DecisionSpec,
    DisclosureRecord,
    EvidenceRecord,
    FinalRecommendation,
    PreMortemReport,
)
from orchestrator.case_store import Case, atomic_write_text
from orchestrator.deck_charts import SKILL_DIR, render_charts
from orchestrator.deck_template import render_slides_html

_BUILD_DECK = SKILL_DIR / "scripts" / "build_deck.py"
_RENDER_DECK = SKILL_DIR / "scripts" / "render_deck.mjs"
_REPO_ROOT = Path(__file__).resolve().parents[1]

#: How long the render subprocess may run before we give up and skip that tier.
_RENDER_TIMEOUT_S = 180


class DeckError(Exception):
    """A tier-1 failure: the HTML/PowerPoint could not be produced at all."""


@dataclass(slots=True)
class DeckResult:
    """What a deck build produced, and which tiers degraded."""

    deck_dir: Path
    html: Path | None = None
    preview: Path | None = None
    pptx: Path | None = None
    pdf: Path | None = None
    pngs: list[Path] = field(default_factory=list)
    report_json: Path | None = None
    #: tier name -> reason, for tiers that did not run fully ("charts", "render").
    degradations: dict[str, str] = field(default_factory=dict)

    @property
    def degraded(self) -> bool:
        return bool(self.degradations)

    def paths(self) -> list[Path]:
        out = [p for p in (self.html, self.pptx, self.pdf) if p is not None]
        return out


def _read_optional(case: Case, model_type: type) -> object | None:
    try:
        return case.read_artifact(model_type)
    except FileNotFoundError:
        return None


def build_deck(case: Case, *, present: bool = False, run_date: str | None = None) -> DeckResult:
    """Build the deck for a completed case. Raises :class:`DeckError` on tier-1 failure.

    Requires a ``FinalRecommendation``; without one the case has not reached
    synthesis and there is nothing to summarise.
    """
    try:
        rec = case.read_artifact(FinalRecommendation)
    except FileNotFoundError as exc:
        raise DeckError("Case has no final recommendation yet; there is no deck to build.") from exc

    spec = _read_optional(case, DecisionSpec)
    premortem = _read_optional(case, PreMortemReport)
    disclosure = _read_optional(case, DisclosureRecord)
    evidence = case.list_artifacts(EvidenceRecord)
    assumptions = case.list_artifacts(AssumptionRecord)
    case_id = case.root.name
    when = run_date or date.today().isoformat()

    deck_dir = case.root / "outputs" / "deck"
    # The deck is derived and regenerable: clear and rewrite on each run.
    shutil.rmtree(deck_dir, ignore_errors=True)
    deck_dir.mkdir(parents=True, exist_ok=True)

    result = DeckResult(deck_dir=deck_dir)

    charts = render_charts(rec, deck_dir / "charts")
    if not charts.available:
        result.degradations["charts"] = charts.reason or "matplotlib unavailable"

    slides_html = render_slides_html(
        rec,
        spec=spec,  # type: ignore[arg-type]
        evidence=evidence,
        assumptions=assumptions,
        premortem=premortem,  # type: ignore[arg-type]
        disclosure=disclosure,  # type: ignore[arg-type]
        charts=charts,
        case_id=case_id,
        run_date=when,
        present=present,
    )
    slides_path = deck_dir / "slides.html"
    atomic_write_text(slides_path, slides_html)
    result.html = slides_path

    # Tier 1: inline into the editable PowerPoint and the render-ready preview.
    proc = subprocess.run(
        [
            sys.executable,
            str(_BUILD_DECK),
            str(slides_path),
            "--name",
            "deck",
            "--out-dir",
            str(deck_dir),
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise DeckError(f"build_deck.py failed: {proc.stderr.strip() or proc.stdout.strip()}")
    pptx = deck_dir / "deck.pptx.html"
    preview = deck_dir / "deck.preview.html"
    if not pptx.exists() or not preview.exists():
        raise DeckError("build_deck.py did not produce the expected PowerPoint/preview files.")
    result.pptx = pptx
    result.preview = preview

    # Tier 3: render PDF + PNGs + geometry report, if Node + Playwright are present.
    _render(preview, deck_dir, result)
    return result


def _render(preview: Path, deck_dir: Path, result: DeckResult) -> None:
    node = shutil.which("node")
    if node is None:
        result.degradations["render"] = "node not on PATH"
        return
    render_out = deck_dir / "render"
    try:
        subprocess.run(
            [node, str(_RENDER_DECK), str(preview), "--out", str(render_out)],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=_RENDER_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        result.degradations["render"] = f"render invocation failed: {exc}"
        return

    report = render_out / "report.json"
    if not report.exists():
        # No report means Chromium/Playwright never ran (e.g. not installed).
        result.degradations["render"] = "render produced no report (Playwright likely missing)"
        return
    result.report_json = report
    result.pngs = sorted(render_out.glob("slide-*.png"))
    pdf = deck_dir / "deck.pdf"
    if pdf.exists():
        result.pdf = pdf


def generate_deck_for_case(case: Case) -> DeckResult | None:
    """Non-fatal pipeline entry point: build the deck, audit the outcome, never raise.

    Returns the :class:`DeckResult` on success (even if some tiers degraded), or
    ``None`` if deck generation failed outright. A failure here must not affect the
    delivered case.
    """
    try:
        result = build_deck(case)
    except Exception as exc:  # noqa: BLE001 — deck failure must never fail a case.
        case.audit(
            AuditEvent(
                ts=datetime.now(UTC),
                actor="deck",
                event_type="deck_generation_failed",
                payload={"error": str(exc)},
            )
        )
        return None

    event = "deck_generation_degraded" if result.degraded else "deck_generated"
    case.audit(
        AuditEvent(
            ts=datetime.now(UTC),
            actor="deck",
            event_type=event,
            payload={
                "deck_dir": str(result.deck_dir),
                "pptx": str(result.pptx) if result.pptx else None,
                "pdf": str(result.pdf) if result.pdf else None,
                "slides": len(result.pngs),
                "degradations": result.degradations,
            },
        )
    )
    return result
