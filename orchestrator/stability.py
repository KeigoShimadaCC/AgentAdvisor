from __future__ import annotations

from orchestrator.artifacts import AnalysisResult, ModelStability


def compute_model_stability(
    analysis_result: AnalysisResult,
    *,
    candidate_alternative: str,
) -> ModelStability:
    runs_total = len(analysis_result.sensitivity_table)
    runs_supporting = sum(
        1
        for row in analysis_result.sensitivity_table
        if row.preferred_alternative == candidate_alternative
    )
    share = runs_supporting / runs_total
    return ModelStability(
        share_of_sensitivity_runs_supporting_recommendation=share,
        runs_total=runs_total,
        runs_supporting=runs_supporting,
    )
