from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import (
    AlternativeAssessment,
    ConfidenceAssessment,
    Counterargument,
    DisclosureRecord,
    EvidenceRecord,
    FailureMode,
    FinalRecommendation,
    Level,
    ModelStability,
    PreMortemReport,
    ProbabilityEstimate,
    ProbabilityMethod,
    ScenarioAssessment,
    SourceType,
)
from orchestrator.artifacts.yaml_io import load_model_from_yaml_path
from orchestrator.case_store import create_case
from orchestrator.render import (
    render_final_recommendation_markdown,
    write_final_recommendation_markdown,
)

_REF_ID_RE = re.compile(r"\[([EA]-\d+)\]")


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


# --- per-bullet citations (SPEC-031) ---


def _evidence(evidence_id: str, *, group: str = "origin-example.com") -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        claim=f"Claim behind {evidence_id}.",
        source_title="Filing",
        publisher="Example Capital Research",
        source_url=f"https://example.com/{evidence_id.lower()}",
        source_type=SourceType.REGULATORY_FILING,
        publication_date=date(2026, 6, 1),
        retrieval_date=date(2026, 7, 1),
        excerpt="Excerpt.",
        reliability=Level.HIGH,
        directness=Level.HIGH,
        independence_group=group,
        limitations=["Scope"],
        retrieved_by="researcher",
    )


def _recommendation(
    *,
    key_reasons: list[str] | None = None,
    citations: list[str] | None = None,
    evidence_confidence: ConfidenceAssessment | None = None,
    recommendation_confidence: ConfidenceAssessment | None = None,
    model_stability: ModelStability | None = None,
) -> FinalRecommendation:
    return FinalRecommendation(
        recommended_action="invest_in_stages",
        timing="This quarter.",
        decision_confidence_summary="Staged entry survives the tested sensitivities.",
        alternatives_considered=[
            AlternativeAssessment(alternative="invest_in_stages", rank=1, rationale="Dominates.")
        ],
        key_reasons=key_reasons or ["Retention held through the last two quarters [E-101]."],
        scenario_analysis=[
            ScenarioAssessment(
                scenario_name="base",
                summary="Growth stays near plan.",
                probability=ProbabilityEstimate(method=ProbabilityMethod.SCENARIO_MODEL, point=0.5),
            )
        ],
        quantitative_findings=["Expected utility favors staged entry [E-102]."],
        strongest_counterarguments=[
            Counterargument(claim="Pricing pressure.", resolution="Tranche sizing.", resolved=True)
        ],
        critical_assumptions=["A-001"],
        recommendation_change_triggers=["Retention below 110%."],
        next_actions=["Define tranche sizing."],
        citations=citations if citations is not None else ["E-101", "E-102", "E-103"],
        outcome_probabilities={
            "positive_return_within_5y": ProbabilityEstimate(
                method=ProbabilityMethod.STRUCTURED_SUBJECTIVE, point=0.59
            )
        },
        evidence_confidence=evidence_confidence
        or ConfidenceAssessment(value=0.63, basis="One filing plus one comparative study."),
        recommendation_confidence=recommendation_confidence
        or ConfidenceAssessment(value=0.74, basis="Staged entry dominates the alternatives."),
        model_stability=model_stability
        or ModelStability(
            share_of_sensitivity_runs_supporting_recommendation=0.8,
            runs_total=20,
            runs_supporting=16,
        ),
    )


def _bullet_lines(rendered: str) -> list[str]:
    return [line for line in rendered.splitlines() if line.startswith("- ")]


def test_no_bullet_carries_the_full_shared_citation_list() -> None:
    rendered = _render_sample(with_disclosure=True)
    shared = {"E-101", "E-102"}

    spamming = [
        line
        for line in _bullet_lines(rendered)
        if set(_REF_ID_RE.findall(line)) == shared and "Inline evidence references" not in line
    ]

    assert spamming == []


def test_a_key_reason_line_carries_exactly_its_own_inline_ids() -> None:
    rendered = _render_sample(with_disclosure=True)
    reason_line = next(
        line
        for line in _bullet_lines(rendered)
        if "Downside concentration evidence remains material" in line
    )

    # This fixture's key reason supplies no inline id, so the rendered line must
    # supply none either; previously it carried the whole shared citation list.
    assert _REF_ID_RE.findall(reason_line) == []
    assert reason_line.endswith("challenge-and-repair.")


def test_each_bullet_keeps_only_the_citations_its_own_text_supplies() -> None:
    recommendation = _recommendation(
        key_reasons=[
            "Retention held through the last two quarters [E-101].",
            "Entry pricing stays inside the band [E-103].",
        ]
    )
    rendered = render_final_recommendation_markdown(
        recommendation, [_evidence("E-101"), _evidence("E-102"), _evidence("E-103")]
    )
    lines = _bullet_lines(rendered)

    first = next(line for line in lines if "Retention held" in line)
    second = next(line for line in lines if "Entry pricing" in line)

    assert _REF_ID_RE.findall(first) == ["E-101"]
    assert _REF_ID_RE.findall(second) == ["E-103"]


def test_the_consolidated_reference_list_and_evidence_table_still_carry_every_id() -> None:
    rendered = _render_sample(with_disclosure=True)

    assert "- [sourced_fact] Inline evidence references: [E-101] [E-102]" in rendered
    assert (
        "| E-101 | Comparable investments show downside concentration when entry pricing is "
        "aggressive. | Example Capital Research | https://example.com/venture-outcome-review | "
        "2026-03-01 | venture-outcomes-2026 |"
    ) in rendered
    assert (
        "| E-102 | AAA filed customer retention metrics above peer median in Q2. | "
        "AAA Investor Relations | https://example.com/aaa-q2-filing | 2026-06-20 | "
        "aaa-q2-filing |"
    ) in rendered


# --- sentinel rendering (SPEC-031) ---


def _stability_line(rendered: str) -> str:
    return next(line for line in rendered.splitlines() if "Model stability:" in line)


def test_single_run_stability_renders_as_not_assessed_without_a_percentage() -> None:
    recommendation = _recommendation(
        model_stability=ModelStability(
            share_of_sensitivity_runs_supporting_recommendation=0.0,
            runs_total=1,
            runs_supporting=0,
        )
    )
    rendered = render_final_recommendation_markdown(
        recommendation, [_evidence("E-101"), _evidence("E-102"), _evidence("E-103")]
    )
    line = _stability_line(rendered)

    assert line == "- [calculation] Model stability: not assessed (single run)."
    assert "0.0%" not in line
    assert "%" not in line


def test_measured_stability_still_reports_the_runs() -> None:
    rendered = _render_sample(with_disclosure=True)

    assert _stability_line(rendered) == (
        "- [calculation] Model stability: 80.0% "
        "(16/20 sensitivity runs support the recommendation)."
    )


def test_coercion_basis_confidence_renders_without_a_percentage() -> None:
    recommendation = _recommendation(
        evidence_confidence=ConfidenceAssessment(value=0.5, basis="Not independently assessed"),
        recommendation_confidence=ConfidenceAssessment(
            value=0.5,
            basis=(
                "Converted from the qualitative level 'high'; the role did not supply "
                "a calibrated assessment."
            ),
        ),
    )
    rendered = render_final_recommendation_markdown(
        recommendation, [_evidence("E-101"), _evidence("E-102"), _evidence("E-103")]
    )
    evidence_line = next(line for line in rendered.splitlines() if "Evidence confidence:" in line)
    recommendation_line = next(
        line for line in rendered.splitlines() if "Recommendation confidence:" in line
    )

    assert evidence_line == (
        "- [calculation] Evidence confidence: not assessed (basis: Not independently assessed)."
    )
    assert "50.0%" not in evidence_line
    assert "not assessed" in recommendation_line
    assert "qualitative level 'high'" in recommendation_line
    assert "%" not in recommendation_line


def test_assessed_confidence_still_reports_the_value() -> None:
    rendered = _render_sample(with_disclosure=True)

    assert "- [calculation] Evidence confidence: 63.0% (basis: One high-directness" in rendered


# --- pre-mortem section (SPEC-031) ---


def _premortem() -> PreMortemReport:
    return PreMortemReport(
        horizon="18 months",
        assumed_outcome="The staged entry was taken and lost money",
        failure_modes=[
            FailureMode(
                failure_mode="retention_collapse",
                narrative="Net retention fell below 100% two quarters after entry",
                probability=ProbabilityEstimate(method=ProbabilityMethod.SCENARIO_MODEL, point=0.3),
                severity=Level.HIGH,
                leading_indicators=["Quarterly net retention below 105%", "Rising churn in SMB"],
                preventive_action="Gate the second tranche on a retention reading",
            ),
            FailureMode(
                failure_mode="pricing_war",
                narrative="A larger competitor discounts aggressively and margins compress",
                probability=ProbabilityEstimate(
                    method=ProbabilityMethod.SCENARIO_MODEL,
                    interval_low=0.1,
                    interval_high=0.25,
                ),
                severity=Level.MEDIUM,
                leading_indicators=["Published list-price cuts by the top two vendors"],
                preventive_action="Track competitor price sheets monthly",
            ),
        ],
        most_likely_failure_mode="retention_collapse",
    )


def test_premortem_section_renders_every_failure_mode_with_the_most_likely_marker() -> None:
    rendered = render_final_recommendation_markdown(
        _recommendation(),
        [_evidence("E-101"), _evidence("E-102"), _evidence("E-103")],
        premortem_report=_premortem(),
    )

    assert "## Pre-mortem" in rendered
    assert (
        "- [interpretation] Assumed outcome over 18 months: The staged entry was taken and "
        "lost money."
    ) in rendered
    assert (
        "- [interpretation] Failure mode (most likely): `retention_collapse` — Net retention "
        "fell below 100% two quarters after entry. (probability: 30.0%; severity: high)."
    ) in rendered
    assert (
        "- [interpretation] Failure mode: `pricing_war` — A larger competitor discounts "
        "aggressively and margins compress. (probability: 10.0% to 25.0%; severity: medium)."
    ) in rendered
    assert (
        "  - [interpretation] Leading indicators: Quarterly net retention below 105%; "
        "Rising churn in SMB."
    ) in rendered
    assert (
        "  - [recommendation] Preventive action: Gate the second tranche on a retention reading."
    ) in rendered


def test_premortem_section_sits_between_counterarguments_and_critical_assumptions() -> None:
    rendered = render_final_recommendation_markdown(
        _recommendation(),
        [_evidence("E-101"), _evidence("E-102"), _evidence("E-103")],
        premortem_report=_premortem(),
    )
    headings = [line for line in rendered.splitlines() if line.startswith("## ")]

    assert headings.index("## Pre-mortem") == headings.index("## Strongest counterarguments") + 1
    assert headings.index("## Critical assumptions") == headings.index("## Pre-mortem") + 1


def test_absent_premortem_report_renders_no_premortem_section() -> None:
    rendered = render_final_recommendation_markdown(
        _recommendation(), [_evidence("E-101"), _evidence("E-102"), _evidence("E-103")]
    )

    assert "## Pre-mortem" not in rendered
    assert "## Pre-mortem" not in _render_sample(with_disclosure=True)


def test_writing_the_export_picks_up_the_premortem_report_stored_on_the_case(
    tmp_path: Path,
) -> None:
    case = create_case("render", cases_root=tmp_path)
    evidence = [_evidence("E-101"), _evidence("E-102"), _evidence("E-103")]

    without = write_final_recommendation_markdown(case.root, _recommendation(), evidence)
    assert "## Pre-mortem" not in without.read_text(encoding="utf-8")

    case.write_artifact(_premortem())
    with_report = write_final_recommendation_markdown(case.root, _recommendation(), evidence)

    assert "## Pre-mortem" in with_report.read_text(encoding="utf-8")
    assert "`retention_collapse`" in with_report.read_text(encoding="utf-8")


# --- independence group labels (SPEC-031) ---


def test_evidence_table_shows_a_human_independence_label_not_a_raw_slug() -> None:
    rendered = render_final_recommendation_markdown(
        _recommendation(citations=["E-101", "E-102"]),
        [
            _evidence("E-101", group="origin-example.com"),
            _evidence("E-102", group="wire-associated-press"),
        ],
    )

    assert "| example.com (origin) |" in rendered
    assert "| Associated Press (wire service) |" in rendered
    assert "| origin-example.com |" not in rendered
    assert "| wire-associated-press |" not in rendered
