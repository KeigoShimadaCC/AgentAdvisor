"""Tests for the deck deliverable (SPEC-057).

The heavy Node/Chromium render tier is skipped in most tests (monkeypatched off)
so they stay fast and hermetic; the always-available tier-1 (HTML + PowerPoint)
and the degradation and non-fatal contracts are what these assert. The real
end-to-end hook — a pipeline run to `done` that drops a deck into the case — is
asserted in `test_pipeline_stub.py::test_pipeline_stub_e2e`.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from orchestrator import deck as deck_mod
from orchestrator.artifacts import (
    AssumptionRecord,
    DecisionSpec,
    DisclosureRecord,
    EvidenceRecord,
    FinalRecommendation,
    PreMortemReport,
)
from orchestrator.case_store import Case
from orchestrator.deck import DeckError, build_deck, generate_deck_for_case
from orchestrator.deck_charts import ChartResult
from orchestrator.deck_template import render_slides_html
from orchestrator.service.lexicon import load_lexicon

_FIXTURE = Path(__file__).parent / "fixtures" / "cases" / "case-001-fixture-001"


@pytest.fixture
def fixture_case(tmp_path: Path) -> Case:
    dest = tmp_path / "case-001-fixture-001"
    shutil.copytree(_FIXTURE, dest)
    return Case(root=dest)


def _skip_render(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the Node/Chromium render tier to be treated as absent."""
    monkeypatch.setattr(deck_mod.shutil, "which", lambda _name: None)


def _load_slides_html(case: Case, charts: ChartResult) -> str:
    rec = case.read_artifact(FinalRecommendation)
    spec = case.read_artifact(DecisionSpec)
    premortem = case.read_artifact(PreMortemReport)
    disclosure = case.read_artifact(DisclosureRecord)
    return render_slides_html(
        rec,
        spec=spec,
        evidence=case.list_artifacts(EvidenceRecord),
        assumptions=case.list_artifacts(AssumptionRecord),
        premortem=premortem,
        disclosure=disclosure,
        charts=charts,
        case_id=case.root.name,
        run_date="2026-08-07",
    )


def test_tier1_always_succeeds(fixture_case: Case, monkeypatch: pytest.MonkeyPatch) -> None:
    _skip_render(monkeypatch)
    result = build_deck(fixture_case)

    assert result.html is not None and result.html.exists()
    assert result.pptx is not None and result.pptx.exists()
    assert result.preview is not None and result.preview.exists()
    # Render tier was skipped, so no PDF and a recorded degradation.
    assert result.pdf is None
    assert "render" in result.degradations


def test_build_deck_requires_final_recommendation(tmp_path: Path) -> None:
    empty = tmp_path / "empty-case"
    (empty / "outputs").mkdir(parents=True)
    with pytest.raises(DeckError):
        build_deck(Case(root=empty))


def test_template_uses_chart_image_when_available(fixture_case: Case) -> None:
    html = _load_slides_html(
        fixture_case, ChartResult(available=True, files={"scenarios": "scenarios.png"})
    )
    assert '<img src="charts/scenarios.png"' in html


def test_template_falls_back_to_table_without_charts(fixture_case: Case) -> None:
    html = _load_slides_html(fixture_case, ChartResult(available=False, reason="forced"))
    assert "charts/scenarios.png" not in html
    # The scenario exhibit is a table instead, carrying each scenario name.
    assert "Bull Case" in html and "Base Case" in html and "Bear Case" in html


def test_four_uncertainty_measures_are_distinct(fixture_case: Case) -> None:
    html = _load_slides_html(fixture_case, ChartResult(available=False))
    assert "Evidence confidence" in html
    assert "Recommendation confidence" in html
    assert "Outcome probability" in html
    assert "Sensitivity runs supporting" in html
    # Model stability is a run count, never a percentage.
    assert '<span class="kpi__val">0/1</span>' in html
    assert "0/1%" not in html


def test_citation_markers_resolve_in_appendix(fixture_case: Case) -> None:
    html = _load_slides_html(fixture_case, ChartResult(available=False))
    markers = set(re.findall(r"\[([EA]-\d{3})\]", html))
    assert markers, "expected at least one [E-]/[A-] citation marker in the deck"
    for marker in markers:
        assert f"<td>{marker}</td>" in html, f"{marker} does not resolve in the appendix"


def test_charts_degradation_is_recorded(
    fixture_case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    _skip_render(monkeypatch)
    monkeypatch.setattr(
        deck_mod, "render_charts", lambda _rec, _dir: ChartResult(available=False, reason="forced")
    )
    result = build_deck(fixture_case)
    assert "charts" in result.degradations
    assert "forced" in result.degradations["charts"]


def test_generate_deck_for_case_is_non_fatal(
    fixture_case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(_case: Case, **_kwargs: object) -> object:
        raise RuntimeError("simulated deck failure")

    monkeypatch.setattr(deck_mod, "build_deck", _boom)
    result = generate_deck_for_case(fixture_case)

    assert result is None
    audit = (fixture_case.root / "audit.jsonl").read_text(encoding="utf-8")
    assert "deck_generation_failed" in audit


def test_generate_deck_for_case_audits_success(
    fixture_case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    _skip_render(monkeypatch)
    result = generate_deck_for_case(fixture_case)

    assert result is not None
    assert (fixture_case.root / "outputs" / "deck" / "deck.pptx.html").exists()
    audit = (fixture_case.root / "audit.jsonl").read_text(encoding="utf-8")
    # Render was skipped, so this run degrades rather than a clean success.
    assert "deck_generation_degraded" in audit or "deck_generated" in audit


def test_deck_events_have_lexicon_entries() -> None:
    lexicon = load_lexicon()
    for event in ("deck_generated", "deck_generation_degraded", "deck_generation_failed"):
        assert event in lexicon, f"{event} has no lexicon narration"
