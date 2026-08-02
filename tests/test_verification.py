from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from orchestrator.artifacts import (
    AlternativeAssessment,
    CitationVerdict,
    ConfidenceAssessment,
    Counterargument,
    EvidenceRecord,
    FinalRecommendation,
    GateFinding,
    GateSeverity,
    Level,
    ModelStability,
    ObjectionRecord,
    ObjectionResolutionStatus,
    ProbabilityEstimate,
    ProbabilityMethod,
    ReviewDefect,
    ReviewDefectType,
    ReviewOutcome,
    ReviewReport,
    ScenarioAssessment,
    SourceType,
    VerificationWorksheet,
)
from orchestrator.case_store import Case, create_case
from orchestrator.verification import (
    WORKSHEET_INSTRUCTIONS,
    build_verification_worksheet,
    review_is_acceptable,
)


@pytest.fixture
def case(tmp_path: Path) -> Case:
    return create_case("verification", cases_root=tmp_path)


def _prob(point: float) -> ProbabilityEstimate:
    return ProbabilityEstimate(method=ProbabilityMethod.SCENARIO_MODEL, point=point)


def _evidence(case: Case, evidence_id: str, excerpt: str) -> None:
    case.write_artifact(
        EvidenceRecord(
            evidence_id=evidence_id,
            claim=f"Claim {evidence_id}",
            source_title="Filing",
            publisher="NVIDIA Corporation",
            source_url=f"https://example.com/{evidence_id}",
            source_type=SourceType.REGULATORY_FILING,
            publication_date=date(2026, 5, 20),
            retrieval_date=date(2026, 8, 1),
            excerpt=excerpt,
            reliability=Level.HIGH,
            directness=Level.HIGH,
            independence_group="sec-filings",
            limitations=["Quarterly"],
            retrieved_by="researcher",
        )
    )


def _final(
    *,
    key_reasons: list[str],
    outcome_point: float = 0.58,
    rec: float = 0.60,
    evi: float = 0.55,
    runs_total: int = 3,
    runs_supporting: int = 2,
    counterargument_claim: str = "Timing risk was accepted in exchange for lower concentration",
    change_triggers: list[str] | None = None,
) -> FinalRecommendation:
    return FinalRecommendation(
        recommended_action="Enter in three tranches over 90 days",
        timing="Begin this week",
        decision_confidence_summary="Moderate confidence on mixed evidence",
        alternatives_considered=[
            AlternativeAssessment(alternative="staged_entry", rank=1, rationale="Balanced"),
        ],
        key_reasons=key_reasons,
        scenario_analysis=[
            ScenarioAssessment(
                scenario_name="base_case", summary="In-line earnings", probability=_prob(0.45)
            ),
        ],
        quantitative_findings=[],
        strongest_counterarguments=[
            Counterargument(
                claim=counterargument_claim,
                resolution="Accepted deliberately",
                resolved=True,
            ),
        ],
        critical_assumptions=[],
        recommendation_change_triggers=change_triggers or ["Earnings miss above 10%"],
        next_actions=["Place the first tranche"],
        citations=["E-001"],
        outcome_probabilities={"positive_return_12m": _prob(outcome_point)},
        evidence_confidence=ConfidenceAssessment(value=evi, basis="Mixed"),
        recommendation_confidence=ConfidenceAssessment(value=rec, basis="Balanced"),
        model_stability=ModelStability(
            share_of_sensitivity_runs_supporting_recommendation=runs_supporting / runs_total,
            runs_total=runs_total,
            runs_supporting=runs_supporting,
        ),
    )


def test_worksheet_pairs_each_claim_with_the_excerpts_it_cites(case: Case) -> None:
    _evidence(case, "E-001", "Revenue $26B, up 120% year over year")
    case.write_artifact(_final(key_reasons=["Revenue grew 120% year over year [E-001]"]))

    worksheet = build_verification_worksheet(case)

    assert worksheet.instructions == WORKSHEET_INSTRUCTIONS
    assert len(worksheet.items) == 1
    item = worksheet.items[0]
    assert item.item_id == "VC-1"
    assert item.cited_ids == ["E-001"]
    assert item.dangling_ids == []
    assert "120%" in item.evidence_excerpts[0]


def test_uncited_claim_produces_a_blocking_finding(case: Case) -> None:
    _evidence(case, "E-001", "Revenue $26B")
    case.write_artifact(_final(key_reasons=["Growth will continue at this pace"]))

    worksheet = build_verification_worksheet(case)

    blocks = [
        finding
        for finding in worksheet.deterministic_findings
        if finding.check_id == "verification.uncited_claim"
    ]
    assert len(blocks) == 1
    assert blocks[0].severity is GateSeverity.BLOCK


def test_dangling_citation_is_recorded_on_the_item_and_warned(case: Case) -> None:
    _evidence(case, "E-001", "Revenue $26B")
    case.write_artifact(_final(key_reasons=["Growth is strong [E-001] and broad [E-404]"]))

    worksheet = build_verification_worksheet(case)

    assert worksheet.items[0].dangling_ids == ["E-404"]
    assert any(
        finding.check_id == "verification.dangling_citation"
        for finding in worksheet.deterministic_findings
    )


def test_false_precision_in_probabilities_is_flagged(case: Case) -> None:
    _evidence(case, "E-001", "Revenue $26B")
    case.write_artifact(_final(key_reasons=["Growth is strong [E-001]"], outcome_point=0.5834))

    worksheet = build_verification_worksheet(case)

    assert any(
        finding.check_id == "verification.false_precision"
        for finding in worksheet.deterministic_findings
    )


def test_confidence_inversion_blocks(case: Case) -> None:
    _evidence(case, "E-001", "Revenue $26B")
    case.write_artifact(_final(key_reasons=["Growth is strong [E-001]"], rec=0.95, evi=0.30))

    worksheet = build_verification_worksheet(case)

    inversion = [
        finding
        for finding in worksheet.deterministic_findings
        if finding.check_id == "verification.confidence_inversion"
    ]
    assert inversion and inversion[0].severity is GateSeverity.BLOCK


def test_single_run_stability_is_warned_as_untested(case: Case) -> None:
    _evidence(case, "E-001", "Revenue $26B")
    case.write_artifact(
        _final(key_reasons=["Growth is strong [E-001]"], runs_total=1, runs_supporting=1)
    )

    worksheet = build_verification_worksheet(case)

    assert any(
        finding.check_id == "verification.stability_untested"
        for finding in worksheet.deterministic_findings
    )


def test_open_material_objection_missing_from_the_recommendation_blocks(case: Case) -> None:
    _evidence(case, "E-001", "Revenue $26B")
    case.write_artifact(
        ObjectionRecord(
            objection_id="O-001",
            target_section="final_recommendation.key_reasons[0]",
            claim="Customer concentration among three hyperscalers is unaddressed",
            materiality=Level.HIGH,
            reasoning="Three buyers dominate revenue.",
            reversal_evidence="Customer breakdown from the filing.",
            referenced_evidence_ids=[],
            referenced_assumption_ids=[],
            resolution_status=ObjectionResolutionStatus.OPEN,
            commissioned_tasks=[],
        )
    )
    case.write_artifact(_final(key_reasons=["Growth is strong [E-001]"]))

    worksheet = build_verification_worksheet(case)

    undisclosed = [
        finding
        for finding in worksheet.deterministic_findings
        if finding.check_id == "verification.undisclosed_open_objection"
    ]
    assert undisclosed and undisclosed[0].target_ids == ["O-001"]


def test_disclosed_open_objection_does_not_block(case: Case) -> None:
    _evidence(case, "E-001", "Revenue $26B")
    case.write_artifact(
        ObjectionRecord(
            objection_id="O-001",
            target_section="final_recommendation.key_reasons[0]",
            claim="Customer concentration among hyperscalers is unaddressed",
            materiality=Level.HIGH,
            reasoning="Three buyers dominate revenue.",
            reversal_evidence="Customer breakdown from the filing.",
            referenced_evidence_ids=[],
            referenced_assumption_ids=[],
            resolution_status=ObjectionResolutionStatus.OPEN,
            commissioned_tasks=[],
        )
    )
    case.write_artifact(
        _final(
            key_reasons=["Growth is strong [E-001]"],
            counterargument_claim="Customer concentration among hyperscalers remains unresolved",
        )
    )

    worksheet = build_verification_worksheet(case)

    assert not [
        finding
        for finding in worksheet.deterministic_findings
        if finding.check_id == "verification.undisclosed_open_objection"
    ]


def _worksheet(items: int = 2, findings: list[GateFinding] | None = None):
    from orchestrator.artifacts import CitationCheckItem

    return VerificationWorksheet(
        items=[
            CitationCheckItem(
                item_id=f"VC-{index}",
                claim=f"Claim {index}",
                cited_ids=["E-001"],
                evidence_excerpts=["Excerpt"],
            )
            for index in range(1, items + 1)
        ],
        deterministic_findings=findings or [],
        instructions=WORKSHEET_INSTRUCTIONS,
    )


def _verdict(item_id: str, supported: bool) -> CitationVerdict:
    return CitationVerdict(
        item_id=item_id, supported=supported, justification="Checked against the excerpt."
    )


def test_review_passing_every_item_is_accepted() -> None:
    report = ReviewReport(
        outcome=ReviewOutcome.PASS,
        citation_verdicts=[_verdict("VC-1", True), _verdict("VC-2", True)],
    )
    assert review_is_acceptable(report, _worksheet())


def test_review_that_skips_worksheet_items_is_rejected() -> None:
    report = ReviewReport(outcome=ReviewOutcome.PASS, citation_verdicts=[_verdict("VC-1", True)])
    assert not review_is_acceptable(report, _worksheet())


def test_review_with_no_verdicts_at_all_is_rejected() -> None:
    report = ReviewReport(outcome=ReviewOutcome.PASS, citation_verdicts=[])
    assert not review_is_acceptable(report, _worksheet())


def test_failing_review_is_rejected() -> None:
    report = ReviewReport(
        outcome=ReviewOutcome.FAIL,
        defects=[
            ReviewDefect(
                defect_type=ReviewDefectType.UNSUPPORTED_CITATION,
                target_id="E-001",
                explanation="The excerpt does not contain the figure.",
            )
        ],
        citation_verdicts=[_verdict("VC-1", False), _verdict("VC-2", True)],
    )
    assert not review_is_acceptable(report, _worksheet())


def test_reviewer_cannot_overrule_a_deterministic_block() -> None:
    findings = [
        GateFinding(
            check_id="verification.confidence_inversion",
            severity=GateSeverity.BLOCK,
            message="Recommendation confidence far exceeds evidence confidence.",
        )
    ]
    report = ReviewReport(
        outcome=ReviewOutcome.PASS,
        citation_verdicts=[_verdict("VC-1", True), _verdict("VC-2", True)],
    )
    assert not review_is_acceptable(report, _worksheet(findings=findings))


def test_warning_level_finding_does_not_block_acceptance() -> None:
    findings = [
        GateFinding(
            check_id="verification.false_precision",
            severity=GateSeverity.WARN,
            message="Too many decimals.",
        )
    ]
    report = ReviewReport(
        outcome=ReviewOutcome.PASS,
        citation_verdicts=[_verdict("VC-1", True), _verdict("VC-2", True)],
    )
    assert review_is_acceptable(report, _worksheet(findings=findings))
