from __future__ import annotations

from orchestrator.artifacts import (
    AnalysisResult,
    AnalysisScenario,
    ProbabilityEstimate,
    ProbabilityMethod,
)
from orchestrator.artifacts.analysis import SensitivityRow
from orchestrator.stability import compute_model_stability


def _analysis_with_preferences(preferred: list[str]) -> AnalysisResult:
    sensitivity_rows = [
        SensitivityRow(
            parameter="test_parameter",
            parameter_value=float(index),
            resulting_expected_values={"invest_now": 1.0, "wait": 0.9},
            preferred_alternative=value,
        )
        for index, value in enumerate(preferred, start=1)
    ]
    return AnalysisResult(
        task_id="T-010",
        script_path="analysis/T-010/model.py",
        results_path="analysis/T-010/results.yaml",
        scenarios=[
            AnalysisScenario(
                scenario_name="base",
                probability=ProbabilityEstimate(
                    method=ProbabilityMethod.STRUCTURED_SUBJECTIVE,
                    point=1.0,
                ),
            )
        ],
        expected_values_by_alternative={"invest_now": 1.0, "wait": 0.9},
        sensitivity_table=sensitivity_rows,
        break_even_thresholds=[],
        assumption_ids=["A-001"],
        evidence_ids=["E-001"],
    )


def test_stability_computes_share_and_counts() -> None:
    analysis = _analysis_with_preferences(["invest_now", "wait", "invest_now", "invest_now"])

    stability = compute_model_stability(analysis, candidate_alternative="invest_now")

    assert stability.runs_total == 4
    assert stability.runs_supporting == 3
    assert stability.share_of_sensitivity_runs_supporting_recommendation == 0.75
    assert (
        abs(
            stability.share_of_sensitivity_runs_supporting_recommendation
            - (stability.runs_supporting / stability.runs_total)
        )
        <= 1e-12
    )


def test_stability_unanimous_support() -> None:
    analysis = _analysis_with_preferences(["invest_now", "invest_now", "invest_now"])

    stability = compute_model_stability(analysis, candidate_alternative="invest_now")

    assert stability.runs_total == 3
    assert stability.runs_supporting == 3
    assert stability.share_of_sensitivity_runs_supporting_recommendation == 1.0


def test_stability_zero_support() -> None:
    analysis = _analysis_with_preferences(["wait", "wait", "wait"])

    stability = compute_model_stability(analysis, candidate_alternative="invest_now")

    assert stability.runs_total == 3
    assert stability.runs_supporting == 0
    assert stability.share_of_sensitivity_runs_supporting_recommendation == 0.0
