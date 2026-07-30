from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import DisclosureRecord, EvidenceRecord, FinalRecommendation
from orchestrator.artifacts.yaml_io import load_model_from_yaml_path
from orchestrator.render import render_final_recommendation_markdown


def _fixture_root() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "roles" / "synthesis" / "replay"


def _load_evidence_records(path: Path) -> list[EvidenceRecord]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError("evidence fixture must be a list")
    return [EvidenceRecord.model_validate(item) for item in payload]


def _load_user_inputs() -> tuple[str, ...]:
    return (
        "User requires downside protection over maximum upside.",
        "User deadline for initial action is this quarter.",
    )


def _render_sample(with_disclosure: bool) -> str:
    fixture_root = _fixture_root()
    recommendation = load_model_from_yaml_path(
        FinalRecommendation, fixture_root / "final_recommendation.yaml"
    )
    evidence_records = _load_evidence_records(fixture_root / "evidence_records.yaml")
    disclosure = (
        load_model_from_yaml_path(DisclosureRecord, fixture_root / "disclosure_record.yaml")
        if with_disclosure
        else None
    )
    return render_final_recommendation_markdown(
        recommendation,
        evidence_records,
        disclosure_record=disclosure,
        user_supplied_inputs=_load_user_inputs(),
    )


def test_render_golden_is_byte_identical_across_runs() -> None:
    rendered_first = _render_sample(with_disclosure=True)
    rendered_second = _render_sample(with_disclosure=True)
    golden_path = _fixture_root() / "final_recommendation.md"
    golden_text = golden_path.read_text(encoding="utf-8")

    assert rendered_first == rendered_second
    assert rendered_first == golden_text


def test_disclosure_section_is_present_iff_disclosure_record_exists() -> None:
    with_disclosure = _render_sample(with_disclosure=True)
    without_disclosure = _render_sample(with_disclosure=False)

    assert "## Budget/depth stop disclosure" in with_disclosure
    assert "## Budget/depth stop disclosure" not in without_disclosure


def test_provenance_labels_present() -> None:
    rendered = _render_sample(with_disclosure=True)
    expected_labels = (
        "[sourced_fact]",
        "[assumption]",
        "[calculation]",
        "[user_input]",
        "[interpretation]",
        "[recommendation]",
    )

    assert all(label in rendered for label in expected_labels)
