from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import (
    AnalysisResult,
    AnalysisScenario,
    AssumptionRecord,
    AuditFinding,
    AuditStopInput,
    BreakEvenThreshold,
    ConfidenceAssessment,
    DecisionSpec,
    DisclosureRecord,
    EvidenceRecord,
    FinalRecommendation,
    FramingApproval,
    FramingDecision,
    IntakeRecord,
    Level,
    ModelStability,
    ObjectionRecord,
    ObjectionResolutionStatus,
    PlanningMode,
    PreliminaryRecommendation,
    ProbabilityEstimate,
    ProbabilityMethod,
    Reversibility,
    ReviewOutcome,
    ReviewReport,
    RiskTolerance,
    ScenarioAssessment,
    SensitivityRow,
    SourceType,
    StopReason,
    TaskProposalBatch,
    TaskRecord,
)
from orchestrator.artifacts.common import (
    AssumptionStatus,
    AssumptionType,
    Depth,
    PriorityLevel,
    TaskRole,
    TaskStatus,
)
from orchestrator.case_store import create_case
from orchestrator.projection import ProjectionError, project


def _probability(point: float) -> ProbabilityEstimate:
    return ProbabilityEstimate(method=ProbabilityMethod.STRUCTURED_SUBJECTIVE, point=point)


def _confidence(value: float, basis: str = "Calibrated from evidence set.") -> ConfidenceAssessment:
    return ConfidenceAssessment(value=value, basis=basis)


def _stability() -> ModelStability:
    return ModelStability(
        share_of_sensitivity_runs_supporting_recommendation=0.75,
        runs_total=4,
        runs_supporting=3,
    )


def _evidence(evidence_id: str, claim: str = "Revenue grew year-over-year.") -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        claim=claim,
        source_title="Annual report",
        publisher="AAA Corp",
        source_url=f"https://example.com/{evidence_id.lower()}",
        source_type=SourceType.REPUTABLE_SECONDARY,
        publication_date=date(2026, 1, 1),
        retrieval_date=date(2026, 1, 2),
        excerpt="Revenue increased by 18%.",
        reliability=Level.HIGH,
        directness=Level.MEDIUM,
        independence_group=f"group-{evidence_id.lower()}",
        limitations=["Company-defined segment reporting."],
        retrieved_by="researcher",
    )


def _assumption(assumption_id: str = "A-001") -> AssumptionRecord:
    return AssumptionRecord(
        assumption_id=assumption_id,
        claim="Market demand remains resilient.",
        type=AssumptionType.FORECAST,
        estimate=_probability(0.62),
        confidence=Level.MEDIUM,
        materiality=Level.HIGH,
        status=AssumptionStatus.UNRESOLVED,
    )


def _objection(objection_id: str = "O-001") -> ObjectionRecord:
    return ObjectionRecord(
        objection_id=objection_id,
        target_section="Recommended timing",
        claim="Entry timing could be too early.",
        materiality=Level.MEDIUM,
        reasoning="Macro indicators remain mixed.",
        reversal_evidence="Sustained demand growth in independent indicators.",
        resolution_status=ObjectionResolutionStatus.OPEN,
    )


def _task(task_id: str, question: str, status: TaskStatus = TaskStatus.PLANNED) -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        role=TaskRole.RESEARCHER,
        question=question,
        why_it_matters="Could materially change recommendation quality.",
        expected_information_gain=Level.HIGH,
        materiality=Level.HIGH,
        inputs=["decision_spec"],
        required_output="evidence_batch",
        completion_criteria="At least one high-quality source",
        status=status,
        priority=PriorityLevel.HIGH,
        priority_score=90,
        priority_rationale="Top uncertainty driver.",
    )


def _analysis(task_id: str = "T-001") -> AnalysisResult:
    return AnalysisResult(
        task_id=task_id,
        script_path=f"analysis/{task_id}/model.py",
        results_path=f"analysis/{task_id}/results.json",
        scenarios=[AnalysisScenario(scenario_name="base", probability=_probability(0.7))],
        expected_values_by_alternative={"invest": 1.5, "wait": 1.1},
        sensitivity_table=[
            SensitivityRow(
                parameter="growth",
                parameter_value=0.1,
                resulting_expected_values={"invest": 1.4, "wait": 1.2},
                preferred_alternative="invest",
            )
        ],
        break_even_thresholds=[
            BreakEvenThreshold(
                parameter="growth",
                threshold_value=0.07,
                favored_alternative_below="wait",
                favored_alternative_above="invest",
            )
        ],
        assumption_ids=["A-001"],
        evidence_ids=["E-001"],
    )


def _preliminary_recommendation() -> PreliminaryRecommendation:
    return PreliminaryRecommendation(
        preferred_alternative="invest",
        rationale=["Expected value leads across tested scenarios."],
        key_assumptions=["A-001"],
        outcome_probabilities={"invest_success": _probability(0.58)},
        evidence_confidence=_confidence(0.7),
        recommendation_confidence=_confidence(0.66),
        model_stability=_stability(),
        unresolved_evidence_gaps=["Demand contraction tail-risk estimate."],
        major_risks=["Macro slowdown could reduce upside."],
    )


def _final_recommendation() -> FinalRecommendation:
    return FinalRecommendation(
        recommended_action="Proceed with a staged initial allocation.",
        timing="Within current quarter after final diligence update.",
        decision_confidence_summary="Moderate confidence with explicit downside triggers.",
        alternatives_considered=[
            {
                "alternative": "wait",
                "rank": 2,
                "rationale": "Lower downside but lower expected return.",
            }
        ],
        key_reasons=["Scenario-weighted EV is highest for staged entry."],
        scenario_analysis=[
            ScenarioAssessment(
                scenario_name="base",
                summary="Base case supports staged entry.",
                probability=_probability(0.7),
            )
        ],
        next_actions=[
            {
                "action_id": "N-001",
                "action": "Monitor demand indicators monthly",
                "owner": "user",
                "by_date": "2026-08-15",
                "first_step": "Block 30 minutes and open the tracking sheet",
                "why_now": "Carries the recommendation into execution",
            }
        ],
        outcome_probabilities={"success": _probability(0.6)},
        evidence_confidence=_confidence(0.72),
        recommendation_confidence=_confidence(0.67),
        model_stability=_stability(),
    )


def _write_state_with_budget(case_root: Path) -> None:
    state_payload = {
        "case_id": case_root.name,
        "stage": "investigation",
        "repair_cycle": 0,
        "budget_counters": {
            "agent_invocations": 5,
            "high_tier_calls": 2,
        },
        "framing_approved": False,
        "final_approved": False,
        "failure_cause": None,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
        "updated_at": datetime(2026, 1, 2, tzinfo=UTC).isoformat(),
    }
    (case_root / "state.yaml").write_text(
        yaml.safe_dump(state_payload, sort_keys=False), encoding="utf-8"
    )


def test_unknown_include_key_raises_helpful_error(tmp_path: Path) -> None:
    case = create_case("projection-unknown", cases_root=tmp_path)

    with pytest.raises(ProjectionError, match="Unknown projection include key 'not_a_real_key'"):
        project(case, include=["not_a_real_key"], budget_chars=10_000)


def test_valid_empty_include_key_returns_empty_without_error(tmp_path: Path) -> None:
    case = create_case("projection-empty", cases_root=tmp_path)

    projected = project(case, include=["analysis_result"], budget_chars=10_000)

    assert projected == []


def test_projection_uses_case_store_canonical_paths_for_artifacts(tmp_path: Path) -> None:
    case = create_case("projection-paths", cases_root=tmp_path)
    case.write_artifact(
        IntakeRecord(raw_prompt="Should I invest now?", decision_question="Invest in AAA now?")
    )
    case.write_artifact(
        FramingApproval(
            decision=FramingDecision.APPROVE,
            approved_by="owner",
            approved_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    case.write_artifact(
        DecisionSpec(
            decision_id=case.root.name,
            question="Invest in AAA now?",
            owner="owner",
            deadline=date(2026, 12, 31),
            alternatives=["invest", "wait"],
            objectives=["maximize risk-adjusted returns"],
            constraints=["stay liquid"],
            risk_tolerance=RiskTolerance.MODERATE,
            reversibility=Reversibility.PARTIALLY_REVERSIBLE,
            depth=Depth.STANDARD,
        )
    )
    case.write_artifact(_preliminary_recommendation())
    case.write_artifact(_final_recommendation())
    case.write_artifact(_analysis("T-001"))
    case.write_artifact(
        DisclosureRecord(
            stop_reasons=(StopReason.INVESTIGATION_BUDGET_EXHAUSTED,),
            exhausted_dimensions=("agent_invocations",),
        )
    )
    case.write_artifact(ReviewReport(outcome=ReviewOutcome.PASS))
    case.write_artifact(TaskProposalBatch(mode=PlanningMode.INITIAL, proposals=[]))
    case.write_artifact(
        AuditFinding(
            findings=[],
            stop_input=AuditStopInput(
                open_critical_evidence_gaps=False,
                unresolved_material_objections=False,
                recommendation_stable=True,
                expected_value_of_more_research_low=True,
                open_critical_evidence_gaps_reason="Core uncertainty addressed.",
                unresolved_material_objections_reason="No unresolved material objections.",
                recommendation_stable_reason="Stable under sensitivity checks.",
                expected_value_of_more_research_low_reason="Marginal expected value is low.",
            ),
        )
    )
    case.write_artifact(_evidence("E-001"))
    case.write_artifact(_assumption("A-001"))
    case.write_artifact(_objection("O-001"))
    case.write_artifact(_task("T-001", "Find updated demand projections."))

    projected = project(
        case,
        include=[
            "intake_record",
            "framing_approval",
            "decision_spec",
            "preliminary_recommendation",
            "final_recommendation",
            "analysis_result",
            "disclosure_record",
            "review_report",
            "task_proposal_batch",
            "audit_finding",
            "evidence_records",
            "assumptions",
            "objections",
            "task_records",
        ],
        budget_chars=200_000,
    )

    names = {artifact.filename for artifact in projected}
    assert "intake_record.yaml" in names
    assert "framing_approval.yaml" in names
    assert "decision_spec.yaml" in names
    assert "preliminary_recommendation.yaml" in names
    assert "final_recommendation.yaml" in names
    assert "analysis_result--T-001.yaml" in names
    assert "disclosure_record.yaml" in names
    assert "review_report.yaml" in names
    assert "task_proposal_batch.yaml" in names
    assert "audit_finding.yaml" in names
    assert "evidence_record--E-001.yaml" in names
    assert "assumption_record--A-001.yaml" in names
    assert "objection_record--O-001.yaml" in names
    assert "task_record--T-001.yaml" in names


def test_derived_summaries_have_expected_shape(tmp_path: Path) -> None:
    case = create_case("projection-derived", cases_root=tmp_path)
    task_1 = _task("T-001", "Map demand-side evidence.", status=TaskStatus.ACTIVE)
    task_2 = _task("T-002", "Quantify downside scenarios.", status=TaskStatus.PLANNED)
    case.write_artifact(task_1)
    case.write_artifact(task_2)
    case.write_artifact(_evidence("E-001", claim="Demand trend remains positive."))
    case.write_artifact(_assumption("A-001"))
    case.write_artifact(
        DecisionSpec(
            decision_id=case.root.name,
            question="Invest in AAA now?",
            owner="owner",
            deadline=date(2026, 12, 31),
            alternatives=["invest", "wait"],
            objectives=["maximize risk-adjusted returns"],
            constraints=["stay liquid"],
            risk_tolerance=RiskTolerance.MODERATE,
            reversibility=Reversibility.PARTIALLY_REVERSIBLE,
            depth=Depth.STANDARD,
        )
    )
    (case.root / "shared" / "task_graph.yaml").write_text(
        yaml.safe_dump({"task_ids": ["T-001", "T-002"], "edges": {"T-002": ["T-001"]}}),
        encoding="utf-8",
    )
    _write_state_with_budget(case.root)

    projected = project(
        case,
        include=["task_graph", "artifact_index", "budget_snapshot"],
        budget_chars=200_000,
    )
    by_name = {item.filename: yaml.safe_load(item.yaml_text) for item in projected}

    task_graph = by_name["task_graph.yaml"]
    assert task_graph["kind"] == "task_graph_summary"
    assert sorted(task["task_id"] for task in task_graph["tasks"]) == ["T-001", "T-002"]
    t2 = next(task for task in task_graph["tasks"] if task["task_id"] == "T-002")
    assert t2["dependencies"] == ["T-001"]
    assert "question" in t2

    artifact_index = by_name["artifact_index.yaml"]
    assert artifact_index["kind"] == "artifact_index"
    indexed_ids = {entry["id"] for entry in artifact_index["artifacts"]}
    assert "E-001" in indexed_ids
    assert "A-001" in indexed_ids

    budget_snapshot = by_name["budget_snapshot.yaml"]
    assert budget_snapshot["kind"] == "budget_snapshot"
    assert budget_snapshot["budget_counters"]["agent_invocations"] == 5


def test_projection_budget_truncation_notice_behavior(tmp_path: Path) -> None:
    case = create_case("projection-truncate", cases_root=tmp_path)
    case.write_artifact(_evidence("E-001", claim="A" * 200))
    case.write_artifact(_evidence("E-002", claim="B" * 200))

    full = project(case, include=["evidence_records"], budget_chars=100_000)
    assert len([item for item in full if item.filename.startswith("evidence_record--")]) == 2

    limited = project(case, include=["evidence_records"], budget_chars=350)
    names = [item.filename for item in limited]
    assert "_truncation_notice.yaml" in names
    assert len([name for name in names if name.startswith("evidence_record--")]) < 2
    notice = next(item for item in limited if item.filename == "_truncation_notice.yaml")
    assert "omitted_count:" in notice.yaml_text
