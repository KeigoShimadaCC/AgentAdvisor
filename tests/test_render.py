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


def test_no_bullet_carries_the_full_shared_citation_list() -> None:
    """SPEC-031: individual bullets must not append the case-wide citation list."""
    rendered = _render_sample(with_disclosure=True)
    # The key reasons section should not contain shared citations
    key_reasons_section = rendered.split("## Key reasons")[1].split("##")[0]
    assert "[E-101]" not in key_reasons_section
    assert "[E-102]" not in key_reasons_section
    # The alternatives section should not contain shared citations
    alt_section = rendered.split("## Alternatives considered")[1].split("##")[0]
    assert "[E-101]" not in alt_section
    assert "[E-102]" not in alt_section


def test_sentinel_model_stability_renders_as_not_assessed() -> None:
    """SPEC-031: placeholder model stability renders as 'not assessed' not '0.0%'."""
    from orchestrator.artifacts.sentinels import model_stability_render_label
    from orchestrator.artifacts.stability import ModelStability

    placeholder = ModelStability(
        share_of_sensitivity_runs_supporting_recommendation=0.0,
        runs_total=1,
        runs_supporting=0,
    )
    label = model_stability_render_label(placeholder)
    assert "not assessed" in label
    assert "0.0%" not in label


def test_sentinel_confidence_renders_without_percentage() -> None:
    """SPEC-031: coercion-default confidence renders without a percentage."""
    from orchestrator.artifacts.confidence import ConfidenceAssessment
    from orchestrator.artifacts.sentinels import confidence_render_label

    placeholder = ConfidenceAssessment(value=0.5, basis="Not independently assessed")
    label = confidence_render_label(placeholder)
    assert "Not assessed" in label
    assert "50.0%" not in label


def test_independence_group_label_strips_question_prefix() -> None:
    """SPEC-031: independence group labels should be human-readable."""
    from orchestrator.render import _independence_group_label

    assert _independence_group_label("invest-public-equity-publisher-bloomberg") == "Bloomberg"
    assert _independence_group_label("question-origin-nyt-com") == "Nyt Com"
    assert _independence_group_label("wire-associated-press") == "Associated Press"
    assert _independence_group_label("uncertain-source-cluster") == "Uncertain source"
