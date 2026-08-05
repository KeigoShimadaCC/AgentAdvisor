"""Deterministic stub backend for pipeline testing and worker subprocesses.

``PipelineStubBackend`` reads the workspace's ``task.yaml`` and returns a
scripted artifact appropriate for the requested output schema.  It exists so
that ``python -m orchestrator.worker <case-id>`` can run end-to-end under
``AGENTADVISOR_BACKEND=stub`` without any live model invocations.

The artifact factories are the same ones used by ``tests/test_pipeline_stub.py``;
this module is the importable home so the worker subprocess can use them.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel

from orchestrator.artifacts import (
    ACHCell,
    ACHConsistency,
    ACHMatrix,
    AlternativeAssessment,
    AnalysisResult,
    AnalysisScenario,
    AssumptionBatch,
    AssumptionRecord,
    AssumptionStatus,
    AssumptionType,
    BreakEvenThreshold,
    CitationVerdict,
    ConfidenceAssessment,
    Counterargument,
    DecisionSpec,
    Depth,
    EvidenceBatch,
    EvidenceRecord,
    FailureMode,
    FinalRecommendation,
    IndependentReview,
    IndependentVerdict,
    IntakeRecord,
    IssueNode,
    IssueNodeType,
    IssueTree,
    Level,
    ModelStability,
    NextAction,
    ObjectionBatch,
    ObjectionMode,
    ObjectionRecord,
    ObjectionResolutionStatus,
    PlanningMode,
    PreliminaryRecommendation,
    PreMortemReport,
    PriorityLevel,
    ProbabilityAdjustment,
    ProbabilityEstimate,
    ProbabilityMethod,
    Reversibility,
    ReviewOutcome,
    ReviewReport,
    RiskTolerance,
    ScenarioAssessment,
    SensitivityRow,
    SourceType,
    TaskProposal,
    TaskProposalBatch,
    TaskProposalRecord,
    TaskRole,
    VerificationWorksheet,
)
from orchestrator.artifacts.yaml_io import dump_model_to_yaml_text, load_model_from_yaml_text
from orchestrator.backend import BackendName, ResultStatus, RoleInvocation, RoleResult, TokenUsage
from orchestrator.case_store import Case

__all__ = ["PipelineStubBackend"]


# ── artifact factories ───────────────────────────────────────────────────────


def _ok_result() -> RoleResult:
    return RoleResult(
        status=ResultStatus.OK,
        result_text=None,
        session_id="stub-session",
        request_id="stub-req",
        duration_ms=10,
        usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
        raw_stdout="{}",
        raw_stderr="",
        cli_version="stub-1.0",
    )


def _make_intake() -> IntakeRecord:
    return IntakeRecord(
        raw_prompt="I have $50k and want semiconductor exposure. Nvidia or ETF?",
        decision_question="Should I invest $50k in Nvidia vs semiconductor ETF?",
        objectives=["capital appreciation", "risk management"],
        constraints=["max 5-year horizon", "no leverage"],
        alternatives_mentioned=["invest_nvda_now", "etf_diversified"],
        risk_tolerance=RiskTolerance.MODERATE,
        reversibility=Reversibility.PARTIALLY_REVERSIBLE,
        depth=Depth.STANDARD,
        clarification_questions=[],
    )


def _make_decision_spec() -> DecisionSpec:
    return DecisionSpec(
        decision_id="case-001-stub-e2e",
        question="Should I invest $50k in Nvidia vs semiconductor ETF?",
        owner="user",
        deadline=date(2026, 12, 31),
        alternatives=["invest_nvda_now", "staged_entry", "etf_diversified"],
        objectives=["capital appreciation", "risk management"],
        constraints=["max 5-year horizon", "no leverage"],
        risk_tolerance=RiskTolerance.MODERATE,
        reversibility=Reversibility.PARTIALLY_REVERSIBLE,
        depth=Depth.STANDARD,
        objective_weights={"capital appreciation": 40.0, "risk management": 60.0},
    )


def _prob(point: float) -> ProbabilityEstimate:
    return ProbabilityEstimate(method=ProbabilityMethod.SCENARIO_MODEL, point=point, adjustments=[])


def _make_preliminary_recommendation(mode: str) -> PreliminaryRecommendation:
    if mode == "provisional_thesis":
        return PreliminaryRecommendation(
            preferred_alternative="staged_entry",
            rationale=[
                "Balances timing risk with participation",
                "Reduces concentration risk vs single stock",
            ],
            key_assumptions=[],
            outcome_probabilities={"positive_return_12m": _prob(0.58)},
            evidence_confidence=ConfidenceAssessment(
                value=0.40, basis="No evidence gathered yet; based on general market knowledge"
            ),
            recommendation_confidence=ConfidenceAssessment(
                value=0.55, basis="Provisional thesis pending investigation"
            ),
            model_stability=ModelStability(
                share_of_sensitivity_runs_supporting_recommendation=1.0,
                runs_total=1,
                runs_supporting=1,
            ),
            unresolved_evidence_gaps=["valuation metrics", "sector concentration data"],
            major_risks=["earnings miss could trigger drawdown"],
        )
    return PreliminaryRecommendation(
        preferred_alternative="staged_entry",
        rationale=[
            "Valuation is above historical average but supported by growth [E-001]",
            "Reduces concentration risk vs single stock [A-001]",
        ],
        key_assumptions=["A-001"],
        outcome_probabilities={
            "positive_return_12m": ProbabilityEstimate(
                method=ProbabilityMethod.SCENARIO_MODEL,
                point=0.58,
                adjustments=[
                    ProbabilityAdjustment(
                        delta=0.05,
                        description="strong revenue growth",
                        evidence_ids=["E-002"],
                    ),
                ],
            ),
        },
        evidence_confidence=ConfidenceAssessment(
            value=0.55, basis="Mix of primary filings and secondary analysis"
        ),
        recommendation_confidence=ConfidenceAssessment(
            value=0.68, basis="Staged entry balances risk across scenarios"
        ),
        model_stability=ModelStability(
            share_of_sensitivity_runs_supporting_recommendation=2 / 3,
            runs_total=3,
            runs_supporting=2,
        ),
        unresolved_evidence_gaps=["limited independent sources on NVDA valuation"],
        major_risks=["earnings miss could trigger 15% drawdown"],
    )


def _make_issue_tree() -> IssueTree:
    return IssueTree(
        decision_question="Should I invest $50k in Nvidia vs semiconductor ETF?",
        nodes=[
            IssueNode(
                node_id="Q-1",
                question="Should I invest $50k in Nvidia vs semiconductor ETF?",
                node_type=IssueNodeType.ROOT,
                materiality=Level.HIGH,
                resolution_criteria="A ranked recommendation with an allocation and timing.",
            ),
            IssueNode(
                node_id="Q-1.1",
                parent_id="Q-1",
                question="Is NVDA's current valuation justified by growth?",
                node_type=IssueNodeType.DRIVER,
                materiality=Level.HIGH,
                resolution_criteria="Forward multiple compared against growth and history.",
            ),
            IssueNode(
                node_id="Q-1.2",
                parent_id="Q-1",
                question="How much concentration risk does a single-stock position add?",
                node_type=IssueNodeType.DRIVER,
                materiality=Level.MEDIUM,
                resolution_criteria="Sector concentration quantified against the ETF baseline.",
            ),
        ],
        mece_justification=(
            "Valuation and concentration are the two drivers that separate the alternatives; "
            "tax treatment is excluded because it is identical across them."
        ),
    )


def _make_assumption_batch() -> AssumptionBatch:
    return AssumptionBatch(
        source_scope="preliminary evidence and analysis results",
        no_assumptions_found=False,
        extraction_notes=(
            "Checked the evidence records and the analysis inputs; the growth extrapolation "
            "is the only unestablished proposition the reasoning depends on."
        ),
        records=[
            AssumptionRecord(
                assumption_id="A-1",
                claim="NVDA revenue growth stays above 50% year over year for four quarters",
                type=AssumptionType.FORECAST,
                estimate=ProbabilityEstimate(
                    method=ProbabilityMethod.STRUCTURED_SUBJECTIVE,
                    point=0.55,
                    adjustments=[],
                ),
                confidence=Level.MEDIUM,
                materiality=Level.HIGH,
                evidence_for=["E-002"],
                evidence_against=[],
                status=AssumptionStatus.UNRESOLVED,
            ),
        ],
    )


def _make_premortem_report() -> PreMortemReport:
    return PreMortemReport(
        horizon="24 months from decision",
        assumed_outcome="The staged position lost 40% and was closed at a loss.",
        most_likely_failure_mode="growth-decelerated-faster-than-modeled",
        failure_modes=[
            FailureMode(
                failure_mode="growth-decelerated-faster-than-modeled",
                narrative=(
                    "Datacenter orders peaked two quarters after entry, growth fell to 15%, "
                    "and the multiple compressed from 45x to 22x."
                ),
                probability=_prob(0.30),
                severity=Level.HIGH,
                leading_indicators=[
                    "Sequential datacenter revenue growth below 5% in any quarter",
                    "Hyperscaler capex guidance revised down",
                ],
                preventive_action="Cap the position; review on quarterly guidance.",
                referenced_evidence_ids=["E-002"],
                referenced_assumption_ids=[],
            ),
        ],
    )


def _make_task_proposal_batch() -> TaskProposalBatch:
    return TaskProposalBatch(
        mode=PlanningMode.INITIAL,
        proposals=[
            TaskProposal(
                task=TaskProposalRecord(
                    role=TaskRole.RESEARCHER,
                    question="What is NVDA's current valuation and growth trajectory?",
                    why_it_matters="Valuation determines if the stock is fairly priced",
                    expected_information_gain=Level.HIGH,
                    materiality=Level.HIGH,
                    probability_of_changing_conclusion=0.7,
                    estimated_cost=1.0,
                    inputs=["decision_spec"],
                    required_output="evidence_batch",
                    completion_criteria="3+ sources with valuation metrics",
                    priority=PriorityLevel.HIGH,
                    priority_score=21,
                    priority_rationale="Valuation is the core driver of the timing decision",
                ),
            ),
            TaskProposal(
                task=TaskProposalRecord(
                    role=TaskRole.RESEARCHER,
                    question="What are the risks of semiconductor sector concentration?",
                    why_it_matters="Concentration risk affects portfolio stability",
                    expected_information_gain=Level.MEDIUM,
                    materiality=Level.MEDIUM,
                    probability_of_changing_conclusion=0.4,
                    estimated_cost=1.0,
                    inputs=["decision_spec"],
                    required_output="evidence_batch",
                    completion_criteria="2+ sources on sector concentration risk",
                    priority=PriorityLevel.MEDIUM,
                    priority_score=8,
                    priority_rationale="Important but not likely to change the recommendation",
                ),
            ),
            TaskProposal(
                task=TaskProposalRecord(
                    role=TaskRole.ANALYST,
                    question="Build a scenario model for NVDA vs ETF expected returns",
                    why_it_matters="Quantitative analysis drives the recommendation",
                    expected_information_gain=Level.HIGH,
                    materiality=Level.HIGH,
                    probability_of_changing_conclusion=0.6,
                    estimated_cost=2.0,
                    inputs=["decision_spec"],
                    required_output="analysis_result",
                    completion_criteria="Scenario model with probabilities and sensitivity table",
                    priority=PriorityLevel.HIGH,
                    priority_score=18,
                    priority_rationale=(
                        "Quantitative expected value comparison is decision-critical"
                    ),
                ),
            ),
        ],
    )


def _make_evidence_batch(task_id: str) -> EvidenceBatch:
    return EvidenceBatch(
        task_id=task_id,
        question="What is NVDA's current valuation and growth trajectory?",
        no_evidence_found=False,
        search_notes="Found 2 sources on NVDA valuation",
        records=[
            EvidenceRecord(
                evidence_id="E-001",
                claim="NVDA trades at 45x forward P/E, above 5-year average of 35x.",
                source_title="Bloomberg Terminal",
                publisher="Bloomberg",
                source_url="https://bloomberg.com/nvda",
                source_type=SourceType.REPUTABLE_SECONDARY,
                publication_date=date(2026, 7, 15),
                retrieval_date=date(2026, 7, 31),
                excerpt="NVDA forward P/E of 45x vs 5-year avg 35x",
                reliability=Level.HIGH,
                directness=Level.HIGH,
                independence_group="market-data",
                limitations=["Trailing data may not reflect future growth"],
                retrieved_by="researcher",
            ),
            EvidenceRecord(
                evidence_id="E-002",
                claim="NVDA revenue grew 120% YoY in latest quarter.",
                source_title="NVDA 10-Q Filing",
                publisher="NVIDIA Corporation",
                source_url="https://sec.gov/nvda-10q",
                source_type=SourceType.REGULATORY_FILING,
                publication_date=date(2026, 5, 20),
                retrieval_date=date(2026, 7, 31),
                excerpt="Revenue $26B, up 120% year over year",
                reliability=Level.HIGH,
                directness=Level.HIGH,
                independence_group="sec-filings",
                limitations=["Quarterly data, may not annualize"],
                retrieved_by="researcher",
            ),
        ],
    )


def _make_analysis_result(task_id: str) -> AnalysisResult:
    return AnalysisResult(
        task_id=task_id,
        script_path=f"analysis/{task_id}/model.py",
        results_path=f"analysis/{task_id}/results.yaml",
        scenarios=[
            AnalysisScenario(scenario_name="bull", probability=_prob(0.30)),
            AnalysisScenario(scenario_name="base", probability=_prob(0.45)),
            AnalysisScenario(scenario_name="bear", probability=_prob(0.25)),
        ],
        expected_values_by_alternative={
            "invest_nvda_now": 12500.0,
            "staged_entry": 11000.0,
            "etf_diversified": 7000.0,
        },
        sensitivity_table=[
            SensitivityRow(
                parameter="earnings_growth",
                parameter_value=0.15,
                resulting_expected_values={
                    "invest_nvda_now": 18000.0,
                    "staged_entry": 15000.0,
                    "etf_diversified": 8000.0,
                },
                preferred_alternative="invest_nvda_now",
            ),
            SensitivityRow(
                parameter="earnings_growth",
                parameter_value=0.05,
                resulting_expected_values={
                    "invest_nvda_now": 7000.0,
                    "staged_entry": 9000.0,
                    "etf_diversified": 6500.0,
                },
                preferred_alternative="staged_entry",
            ),
        ],
        break_even_thresholds=[
            BreakEvenThreshold(
                parameter="earnings_growth",
                threshold_value=0.08,
                favored_alternative_below="staged_entry",
                favored_alternative_above="invest_nvda_now",
            ),
        ],
        assumption_ids=["A-001"],
        evidence_ids=["E-001", "E-002"],
    )


def _make_objection_batch() -> ObjectionBatch:
    return ObjectionBatch(
        mode=ObjectionMode.STANDARD,
        no_objections_justification=None,
        objections=[
            ObjectionRecord(
                objection_id="O-001",
                target_section="preliminary_recommendation.rationale[0]",
                claim="Staged entry may miss upside if earnings beat expectations.",
                materiality=Level.MEDIUM,
                reasoning="If NVDA beats earnings, waiting means missing the rally.",
                reversal_evidence="Historical post-earning rally data showing 10%+ jumps",
                referenced_evidence_ids=["E-002"],
                referenced_assumption_ids=[],
                resolution_status=ObjectionResolutionStatus.OPEN,
                commissioned_tasks=[],
            ),
        ],
    )


def _make_final_recommendation() -> FinalRecommendation:
    return FinalRecommendation(
        recommended_action="Invest via staged entry: 30% now, 40% post-earnings, 30% after 90 days",
        timing="Begin this week, complete within 90 days",
        decision_confidence_summary="Moderate confidence based on mixed evidence quality",
        alternatives_considered=[
            AlternativeAssessment(
                alternative="invest_nvda_now",
                rank=3,
                rationale="Full allocation carries concentration risk",
                objective_scores={"capital appreciation": 0.85, "risk management": 0.30},
            ),
            AlternativeAssessment(
                alternative="staged_entry",
                rank=1,
                rationale="Balances timing risk with participation",
                objective_scores={"capital appreciation": 0.70, "risk management": 0.75},
            ),
            AlternativeAssessment(
                alternative="etf_diversified",
                rank=2,
                rationale="Lower risk but also lower expected return",
                objective_scores={"capital appreciation": 0.45, "risk management": 0.72},
            ),
        ],
        key_reasons=[
            "Valuation is above historical average but supported by growth [E-001]",
            "Revenue growth of 120% justifies premium pricing [E-002]",
            "Concentration in single stock violates diversification [A-001]",
        ],
        scenario_analysis=[
            ScenarioAssessment(
                scenario_name="bull_case",
                summary="Strong earnings beat drives 20%+ upside",
                probability=_prob(0.30),
            ),
            ScenarioAssessment(
                scenario_name="base_case",
                summary="In-line earnings, modest appreciation",
                probability=_prob(0.45),
            ),
            ScenarioAssessment(
                scenario_name="bear_case",
                summary="Earnings miss triggers 15% drawdown",
                probability=_prob(0.25),
            ),
        ],
        quantitative_findings=[
            "Expected value of staged entry: $11,000 based on scenario model [E-001]"
        ],
        strongest_counterarguments=[
            Counterargument(
                claim="Staged entry may miss the upside if earnings beat",
                resolution="Accept timing risk in exchange for reduced concentration risk",
                resolved=True,
            ),
        ],
        critical_assumptions=["A-001"],
        recommendation_change_triggers=["If earnings miss by >10%, shift to ETF strategy"],
        limitations=[
            "Valuation evidence rests on a single independence group",
            "Competitive response within 24 months was not investigated",
        ],
        next_actions=[
            NextAction(
                action_id="N-001",
                action="Place initial 30% allocation",
                owner="user",
                by_date=date(2026, 8, 15),
                first_step="Open the brokerage order ticket and set a limit price",
                why_now="Staged entry starts now so the remaining tranches stay optional",
                estimated_cost="15000 USD",
            ),
            NextAction(
                action_id="N-002",
                action="Set an earnings alert for next quarter",
                owner="user",
                by_date=date(2026, 8, 20),
                first_step="Add the earnings date to the calendar with a price alert",
                why_now="The next print is the first checkpoint for the staged plan",
                depends_on=["N-001"],
            ),
        ],
        citations=["E-001", "E-002"],
        outcome_probabilities={"positive_return_12m": _prob(0.58)},
        evidence_confidence=ConfidenceAssessment(
            value=0.55, basis="Mix of primary filings and secondary analysis"
        ),
        recommendation_confidence=ConfidenceAssessment(
            value=0.68, basis="Staged entry balances risk across scenarios"
        ),
        model_stability=ModelStability(
            share_of_sensitivity_runs_supporting_recommendation=0.50,
            runs_total=2,
            runs_supporting=1,
        ),
    )


def _make_independent_review() -> IndependentReview:
    return IndependentReview(
        verdict=IndependentVerdict.CONCUR_WITH_RESERVATIONS,
        reasoning=(
            "The evidence supports a staged entry over a full allocation: the valuation "
            "records show a premium multiple that growth only partly justifies, and the "
            "concentration argument is documented. I reach the same action. My reservation "
            "is that the demand-growth claim rests on one independence group."
        ),
        unsupported_claims=["Demand growth is independently corroborated"],
        evidence_ids=["E-001", "E-002"],
    )


def _make_ach_matrix() -> ACHMatrix:
    """A deliberately mixed matrix: one discriminating record, one that is not.

    E-002 scores the same against every alternative, so it lands in the
    zero-diagnosticity list — which exercises the reporting path that names evidence
    the case collected and could not have used.
    """
    alternatives = ["invest_nvda_now", "staged_entry", "etf_diversified"]
    scores = {
        "E-001": {
            "invest_nvda_now": ACHConsistency.STRONGLY_INCONSISTENT,
            "staged_entry": ACHConsistency.CONSISTENT,
            "etf_diversified": ACHConsistency.CONSISTENT,
        },
        "E-002": {
            "invest_nvda_now": ACHConsistency.NEUTRAL,
            "staged_entry": ACHConsistency.NEUTRAL,
            "etf_diversified": ACHConsistency.NEUTRAL,
        },
    }
    return ACHMatrix(
        decision_question="Should I invest $50k in Nvidia vs semiconductor ETF?",
        alternatives=alternatives,
        evidence_ids=["E-001", "E-002"],
        cells=[
            ACHCell(
                evidence_id=evidence_id,
                alternative=alternative,
                consistency=consistency,
                note=f"Scored {consistency.value} for {alternative}",
            )
            for evidence_id, row in scores.items()
            for alternative, consistency in row.items()
        ],
    )


def _make_review_report(worksheet: VerificationWorksheet | None) -> ReviewReport:
    items = worksheet.items if worksheet is not None else []
    return ReviewReport(
        outcome=ReviewOutcome.PASS,
        defects=[],
        citation_verdicts=[
            CitationVerdict(
                item_id=item.item_id,
                supported=True,
                justification="The quoted excerpt states the figure the claim relies on.",
            )
            for item in items
        ],
    )


def _make_assumption() -> AssumptionRecord:
    return AssumptionRecord(
        assumption_id="A-001",
        claim="NVDA growth will continue at 50%+ for the next 12 months",
        type=AssumptionType.FORECAST,
        estimate=ProbabilityEstimate(
            method=ProbabilityMethod.STRUCTURED_SUBJECTIVE,
            point=0.65,
            adjustments=[],
        ),
        confidence=Level.MEDIUM,
        materiality=Level.HIGH,
        evidence_for=["E-002"],
        evidence_against=[],
        status=AssumptionStatus.UNRESOLVED,
    )


# ── analysis files for the stub analyst ──────────────────────────────────────

_MODEL_PY = """\
import yaml

results = {
    "scenarios": [
        {"scenario_name": "bull", "probability": {
            "method": "scenario_model", "point": 0.30, "adjustments": []}},
        {"scenario_name": "base", "probability": {
            "method": "scenario_model", "point": 0.45, "adjustments": []}},
        {"scenario_name": "bear", "probability": {
            "method": "scenario_model", "point": 0.25, "adjustments": []}},
    ],
    "expected_values_by_alternative": {
        "invest_nvda_now": 12500.0,
        "staged_entry": 11000.0,
        "etf_diversified": 7000.0,
    },
    "sensitivity_table": [
        {"parameter": "earnings_growth", "parameter_value": 0.15,
         "resulting_expected_values": {
             "invest_nvda_now": 18000.0, "staged_entry": 15000.0,
             "etf_diversified": 8000.0},
         "preferred_alternative": "invest_nvda_now"},
        {"parameter": "earnings_growth", "parameter_value": 0.05,
         "resulting_expected_values": {
             "invest_nvda_now": 7000.0, "staged_entry": 9000.0,
             "etf_diversified": 6500.0},
         "preferred_alternative": "staged_entry"},
    ],
    "break_even_thresholds": [
        {"parameter": "earnings_growth", "threshold_value": 0.08,
         "favored_alternative_below": "staged_entry",
         "favored_alternative_above": "invest_nvda_now"},
    ],
}

with open("results.yaml", "w") as f:
    yaml.dump(results, f, default_flow_style=False)
print("Done")
"""

_RESULTS_YAML = """\
break_even_thresholds:
- favored_alternative_above: invest_nvda_now
  favored_alternative_below: staged_entry
  parameter: earnings_growth
  threshold_value: 0.08
expected_values_by_alternative:
  etf_diversified: 7000.0
  invest_nvda_now: 12500.0
  staged_entry: 11000.0
scenarios:
- probability:
    adjustments: []
    method: scenario_model
    point: 0.3
  scenario_name: bull
- probability:
    adjustments: []
    method: scenario_model
    point: 0.45
  scenario_name: base
- probability:
    adjustments: []
    method: scenario_model
    point: 0.25
  scenario_name: bear
sensitivity_table:
- parameter: earnings_growth
  parameter_value: 0.15
  resulting_expected_values:
    etf_diversified: 8000.0
    invest_nvda_now: 18000.0
    staged_entry: 15000.0
  preferred_alternative: invest_nvda_now
- parameter: earnings_growth
  parameter_value: 0.05
  resulting_expected_values:
    etf_diversified: 6500.0
    invest_nvda_now: 7000.0
    staged_entry: 9000.0
  preferred_alternative: staged_entry
"""


# ── Stub backend ─────────────────────────────────────────────────────────────


def _read_worksheet(workspace: Path) -> VerificationWorksheet | None:
    path = workspace / "inputs" / "verification_worksheet.yaml"
    if not path.exists():
        return None
    return load_model_from_yaml_text(VerificationWorksheet, path.read_text(encoding="utf-8"))


class PipelineStubBackend:
    """Backend that returns scripted artifacts based on the workspace's task.yaml."""

    name: str = BackendName.CURSOR

    def __init__(self, case: Case) -> None:
        self._case = case
        self.invocations: list[RoleInvocation] = []
        self._assumption_seeded = False

    def _seed_assumption(self) -> None:
        """Seed an AssumptionRecord to the case (called during investigation)."""
        if not self._assumption_seeded:
            self._case.next_id("A-")
            self._case.write_artifact(_make_assumption())
            self._assumption_seeded = True

    def run(self, invocation: RoleInvocation) -> RoleResult:
        self.invocations.append(invocation)
        workspace = invocation.workspace

        task_data: dict[str, Any] = {}
        task_yaml_path = workspace / "task.yaml"
        if task_yaml_path.exists():
            task_data = yaml.safe_load(task_yaml_path.read_text())

        output_schema = task_data.get("required_output_schema", "")
        mode = task_data.get("mode")
        task_id = task_data.get("task_id", "")

        if output_schema == "intake_record":
            artifact: BaseModel = _make_intake()
        elif output_schema == "ach_matrix":
            artifact = _make_ach_matrix()
        elif output_schema == "independent_review":
            artifact = _make_independent_review()
        elif output_schema == "decision_spec":
            artifact = _make_decision_spec()
        elif output_schema == "preliminary_recommendation":
            artifact = _make_preliminary_recommendation(mode or "provisional_thesis")
        elif output_schema == "task_proposal_batch":
            artifact = _make_task_proposal_batch()
        elif output_schema == "evidence_batch":
            artifact = _make_evidence_batch(task_id)
            self._seed_assumption()
        elif output_schema == "analysis_result":
            artifact = _make_analysis_result(task_id)
            analysis_dir = workspace / "analysis" / task_id
            analysis_dir.mkdir(parents=True, exist_ok=True)
            (analysis_dir / "model.py").write_text(_MODEL_PY)
            (analysis_dir / "results.yaml").write_text(_RESULTS_YAML)
        elif output_schema == "objection_batch":
            artifact = _make_objection_batch()
        elif output_schema == "issue_tree":
            artifact = _make_issue_tree()
        elif output_schema == "assumption_batch":
            artifact = _make_assumption_batch()
        elif output_schema == "premortem_report":
            artifact = _make_premortem_report()
        elif output_schema == "final_recommendation":
            artifact = _make_final_recommendation()
        elif output_schema == "review_report":
            artifact = _make_review_report(_read_worksheet(workspace))
        else:
            raise ValueError(f"Unknown output schema: {output_schema}")

        output_filename = task_data.get("required_output_filename", f"{output_schema}.yaml")
        output_path = workspace / "outputs" / output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(dump_model_to_yaml_text(artifact), encoding="utf-8")

        return _ok_result()
