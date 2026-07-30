from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from orchestrator.artifacts import (
    AnalysisResult,
    AnalysisScenario,
    ProbabilityEstimate,
    ProbabilityMethod,
)
from orchestrator.artifacts.analysis import SensitivityRow
from orchestrator.reproduce import ReproduceStatus, reproduce_analysis_result

FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures" / "roles" / "analyst"


def _analysis_result(task_id: str) -> AnalysisResult:
    return AnalysisResult(
        task_id=task_id,
        script_path=f"analysis/{task_id}/model.py",
        results_path=f"analysis/{task_id}/results.yaml",
        scenarios=[
            AnalysisScenario(
                scenario_name="base",
                probability=ProbabilityEstimate(
                    method=ProbabilityMethod.STRUCTURED_SUBJECTIVE,
                    point=1.0,
                ),
            )
        ],
        expected_values_by_alternative={"invest_now": 1.0},
        sensitivity_table=[
            SensitivityRow(
                parameter="base_case",
                parameter_value=1.0,
                resulting_expected_values={"invest_now": 1.0},
                preferred_alternative="invest_now",
            )
        ],
        break_even_thresholds=[],
        assumption_ids=["A-001"],
        evidence_ids=["E-001"],
    )


def _prepare_case_root(tmp_path: Path, fixture_name: str, task_id: str) -> Path:
    case_root = tmp_path / "case"
    fixture_dir = FIXTURES_ROOT / fixture_name
    target_dir = case_root / "analysis" / task_id
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fixture_dir / "model.py", target_dir / "model.py")
    shutil.copy2(fixture_dir / "results.yaml", target_dir / "results.yaml")
    return case_root


def test_reproducibility_passes_when_rerun_matches(tmp_path: Path) -> None:
    task_id = "T-001"
    case_root = _prepare_case_root(tmp_path, "pass", task_id)
    artifact = _analysis_result(task_id)

    result = reproduce_analysis_result(case_root=case_root, analysis_result=artifact, timeout_s=2.0)

    assert result.status is ReproduceStatus.PASS
    assert result.diff == ()
    result.require_pass()


def test_reproducibility_divergence_returns_diff_and_rejects(tmp_path: Path) -> None:
    task_id = "T-002"
    case_root = _prepare_case_root(tmp_path, "diverge", task_id)
    artifact = _analysis_result(task_id)
    results_path = case_root / "analysis" / task_id / "results.yaml"
    committed_before = results_path.read_text(encoding="utf-8")

    result = reproduce_analysis_result(case_root=case_root, analysis_result=artifact, timeout_s=2.0)

    assert result.status is ReproduceStatus.DIVERGED
    assert result.diff
    assert any(entry.path.startswith("$.count") for entry in result.diff)
    with pytest.raises(ValueError, match="Reproducibility check diverged"):
        result.require_pass()
    committed_after = results_path.read_text(encoding="utf-8")
    assert committed_after == committed_before


def test_reproducibility_timeout(tmp_path: Path) -> None:
    task_id = "T-003"
    case_root = _prepare_case_root(tmp_path, "hang", task_id)
    artifact = _analysis_result(task_id)

    result = reproduce_analysis_result(case_root=case_root, analysis_result=artifact, timeout_s=0.1)

    assert result.status is ReproduceStatus.TIMEOUT
    assert result.timeout_s == 0.1
    with pytest.raises(ValueError, match="timed out"):
        result.require_pass()
