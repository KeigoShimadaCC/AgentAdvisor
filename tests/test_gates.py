from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from orchestrator.artifacts import (
    AlternativeAssessment,
    AssumptionRecord,
    AssumptionStatus,
    AssumptionType,
    ConfidenceAssessment,
    EvidenceRecord,
    FinalRecommendation,
    GateSeverity,
    Level,
    ModelStability,
    ObjectionRecord,
    ObjectionResolutionStatus,
    PreliminaryRecommendation,
    PriorityLevel,
    ProbabilityEstimate,
    ProbabilityMethod,
    ScenarioAssessment,
    SourceType,
    TaskRecord,
    TaskRole,
    TaskStatus,
)
from orchestrator.case_store import Case, create_case
from orchestrator.evidence_critic import critique_case_evidence
from orchestrator.gates import blocking_findings, run_stage_gate


@pytest.fixture
def case(tmp_path: Path) -> Case:
    return create_case("gates", cases_root=tmp_path)


def _prob(point: float) -> ProbabilityEstimate:
    return ProbabilityEstimate(method=ProbabilityMethod.SCENARIO_MODEL, point=point)


def _evidence(case: Case, evidence_id: str, group: str = "sec-filings") -> EvidenceRecord:
    record = EvidenceRecord(
        evidence_id=evidence_id,
        claim=f"Claim {evidence_id}",
        source_title="Filing",
        publisher="Publisher",
        source_url=f"https://example.com/{evidence_id}",
        source_type=SourceType.REGULATORY_FILING,
        publication_date=date(2026, 7, 1),
        retrieval_date=date(2026, 8, 1),
        excerpt="Excerpt",
        reliability=Level.HIGH,
        directness=Level.HIGH,
        independence_group=group,
        limitations=["Scope"],
        retrieved_by="researcher",
    )
    case.write_artifact(record)
    return record


def _recommendation(*, rationale: list[str], rec: float = 0.6, evi: float = 0.6):
    return PreliminaryRecommendation(
        preferred_alternative="staged_entry",
        rationale=rationale,
        key_assumptions=[],
        outcome_probabilities={"positive_return_12m": _prob(0.5)},
        evidence_confidence=ConfidenceAssessment(value=evi, basis="Mixed sources"),
        recommendation_confidence=ConfidenceAssessment(value=rec, basis="Balanced"),
        model_stability=ModelStability(
            share_of_sensitivity_runs_supporting_recommendation=1.0,
            runs_total=2,
            runs_supporting=2,
        ),
        unresolved_evidence_gaps=[],
        major_risks=["drawdown"],
    )


def _task(case: Case, task_id: str, *, status: TaskStatus, materiality: Level) -> TaskRecord:
    record = TaskRecord(
        task_id=task_id,
        role=TaskRole.RESEARCHER,
        question="Question",
        why_it_matters="It matters.",
        expected_information_gain=Level.HIGH,
        materiality=materiality,
        probability_of_changing_conclusion=0.5,
        estimated_cost=1.0,
        inputs=["decision_spec"],
        required_output="evidence_batch",
        completion_criteria="Done",
        status=status,
        priority=PriorityLevel.HIGH,
        priority_score=50,
        priority_rationale="Material",
    )
    case.write_artifact(record)
    return record


def test_uncited_claim_blocks_when_citable_records_exist(case: Case) -> None:
    _evidence(case, "E-001")
    case.write_artifact(_recommendation(rationale=["Growth is strong and will continue"]))

    report = run_stage_gate(case, "preliminary_recommendation")

    assert report.outcome is GateSeverity.BLOCK
    assert not report.passed
    assert any(
        finding.check_id == "citation_integrity.uncited_claim" for finding in report.findings
    )


def test_citation_to_a_nonexistent_id_blocks(case: Case) -> None:
    _evidence(case, "E-001")
    case.write_artifact(_recommendation(rationale=["Growth is strong [E-404]"]))

    report = run_stage_gate(case, "preliminary_recommendation")

    assert any(
        finding.check_id == "citation_integrity.dangling_only" for finding in report.findings
    )


def test_properly_cited_claim_passes_citation_integrity(case: Case) -> None:
    _evidence(case, "E-001")
    case.write_artifact(_recommendation(rationale=["Growth is strong [E-001]"]))

    report = run_stage_gate(case, "preliminary_recommendation")

    assert report.passed
    assert not [
        finding for finding in report.findings if finding.check_id.startswith("citation_integrity")
    ]


def test_confidence_overclaim_is_warned_not_blocked(case: Case) -> None:
    _evidence(case, "E-001")
    case.write_artifact(_recommendation(rationale=["Growth is strong [E-001]"], rec=0.95, evi=0.30))

    report = run_stage_gate(case, "preliminary_recommendation")

    overclaim = [f for f in report.findings if f.check_id == "confidence.overclaim"]
    assert len(overclaim) == 1
    assert overclaim[0].severity is GateSeverity.WARN
    assert report.passed


def test_single_origin_corpus_blocks_at_the_evidence_gate(case: Case) -> None:
    for index in range(1, 4):
        _evidence(case, f"E-00{index}", group="one-press-release")
    critique_case_evidence(case, as_of=date(2026, 8, 1))

    report = run_stage_gate(case, "evidence_critique")

    assert report.outcome is GateSeverity.BLOCK
    assert any(
        finding.check_id == "evidence.independence_concentration" for finding in report.findings
    )


def test_empty_evidence_corpus_blocks(case: Case) -> None:
    critique_case_evidence(case, as_of=date(2026, 8, 1))

    report = run_stage_gate(case, "evidence_critique")

    assert any(finding.check_id == "evidence.absent" for finding in report.findings)
    assert report.outcome is GateSeverity.BLOCK


def test_missing_assumption_ledger_warns(case: Case) -> None:
    report = run_stage_gate(case, "assumption_ledger")

    assert any(finding.check_id == "assumption_ledger.empty" for finding in report.findings)
    assert report.passed


def test_unsupported_high_materiality_assumption_warns(case: Case) -> None:
    case.write_artifact(
        AssumptionRecord(
            assumption_id="A-001",
            claim="Growth continues above 50%",
            type=AssumptionType.FORECAST,
            estimate=_prob(0.6),
            confidence=Level.MEDIUM,
            materiality=Level.HIGH,
            evidence_for=[],
            evidence_against=[],
            status=AssumptionStatus.UNRESOLVED,
        )
    )
    report = run_stage_gate(case, "assumption_ledger")

    assert any(
        finding.check_id == "assumption_ledger.unsupported_high_materiality"
        for finding in report.findings
    )


def test_failed_material_task_blocks_and_failed_immaterial_task_only_warns(case: Case) -> None:
    _task(case, "T-001", status=TaskStatus.FAILED, materiality=Level.HIGH)
    _task(case, "T-002", status=TaskStatus.FAILED, materiality=Level.LOW)

    report = run_stage_gate(case, "investigation")

    by_id = {finding.check_id: finding for finding in report.findings}
    assert by_id["tasks.material_failure"].severity is GateSeverity.BLOCK
    assert by_id["tasks.immaterial_failure_cancelled"].severity is GateSeverity.WARN


def test_open_high_materiality_objection_warns_at_challenge(case: Case) -> None:
    case.write_artifact(
        ObjectionRecord(
            objection_id="O-001",
            target_section="preliminary_recommendation.rationale[0]",
            claim="The growth extrapolation is unsupported.",
            materiality=Level.HIGH,
            reasoning="No source establishes forward growth.",
            reversal_evidence="Forward guidance from the company.",
            referenced_evidence_ids=[],
            referenced_assumption_ids=[],
            resolution_status=ObjectionResolutionStatus.OPEN,
            commissioned_tasks=[],
        )
    )
    report = run_stage_gate(case, "challenge")

    assert any(
        finding.check_id == "objections.open_high_materiality" for finding in report.findings
    )


def test_blocking_findings_accumulate_across_stage_gates(case: Case) -> None:
    critique_case_evidence(case, as_of=date(2026, 8, 1))
    run_stage_gate(case, "evidence_critique")
    _evidence(case, "E-001")
    case.write_artifact(_recommendation(rationale=["Uncited assertion about growth"]))
    run_stage_gate(case, "preliminary_recommendation")

    check_ids = {finding.check_id for finding in blocking_findings(case)}
    assert "evidence.absent" in check_ids
    assert "citation_integrity.uncited_claim" in check_ids


def test_gate_report_is_persisted_and_audited(case: Case) -> None:
    run_stage_gate(case, "assumption_ledger")

    audit_text = (case.root / "audit.jsonl").read_text(encoding="utf-8")
    assert "stage_gate_evaluated" in audit_text


def test_unknown_stage_runs_no_checks_and_passes(case: Case) -> None:
    report = run_stage_gate(case, "intake")

    assert report.findings == []
    assert report.outcome is GateSeverity.PASS


def _final_recommendation(*, critical_assumptions: list[str]) -> FinalRecommendation:
    return FinalRecommendation(
        recommended_action="invest_in_stages",
        timing="This quarter.",
        decision_confidence_summary="Staged entry survives the tested sensitivities.",
        alternatives_considered=[
            AlternativeAssessment(alternative="invest_in_stages", rank=1, rationale="Dominates.")
        ],
        key_reasons=["Retention held through the last two quarters [E-001]."],
        scenario_analysis=[
            ScenarioAssessment(
                scenario_name="base",
                summary="Growth stays near plan.",
                probability=_prob(0.5),
            )
        ],
        critical_assumptions=critical_assumptions,
        next_actions=["Define tranche sizing."],
        citations=["E-001"],
        outcome_probabilities={"positive_return_12m": _prob(0.5)},
        evidence_confidence=ConfidenceAssessment(value=0.6, basis="Mixed sources"),
        recommendation_confidence=ConfidenceAssessment(value=0.6, basis="Balanced"),
        model_stability=ModelStability(
            share_of_sensitivity_runs_supporting_recommendation=1.0,
            runs_total=2,
            runs_supporting=2,
        ),
    )


def _high_materiality_assumption(case: Case, assumption_id: str) -> None:
    case.write_artifact(
        AssumptionRecord(
            assumption_id=assumption_id,
            claim="Retention stays above 115% for four quarters.",
            type=AssumptionType.FORECAST,
            estimate=_prob(0.6),
            confidence=Level.MEDIUM,
            materiality=Level.HIGH,
            evidence_for=["E-001"],
            evidence_against=[],
            status=AssumptionStatus.UNRESOLVED,
        )
    )


def test_empty_critical_assumptions_against_a_populated_ledger_warns_at_synthesis(
    case: Case,
) -> None:
    _evidence(case, "E-001")
    _high_materiality_assumption(case, "A-001")
    case.write_artifact(_final_recommendation(critical_assumptions=[]))

    report = run_stage_gate(case, "synthesis")

    finding = next(
        item
        for item in report.findings
        if item.check_id == "synthesis.missing_critical_assumptions"
    )
    assert finding.severity is GateSeverity.WARN
    assert finding.target_ids == ["A-001"]
    assert report.passed


def test_listed_critical_assumptions_keep_the_gate_silent(case: Case) -> None:
    _evidence(case, "E-001")
    _high_materiality_assumption(case, "A-001")
    case.write_artifact(_final_recommendation(critical_assumptions=["A-001"]))

    report = run_stage_gate(case, "synthesis")

    assert not [
        item
        for item in report.findings
        if item.check_id == "synthesis.missing_critical_assumptions"
    ]


def test_an_empty_ledger_does_not_warn_about_missing_critical_assumptions(case: Case) -> None:
    _evidence(case, "E-001")
    case.write_artifact(_final_recommendation(critical_assumptions=[]))

    report = run_stage_gate(case, "synthesis")

    assert not [
        item
        for item in report.findings
        if item.check_id == "synthesis.missing_critical_assumptions"
    ]
