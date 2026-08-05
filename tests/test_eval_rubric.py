"""SPEC-044 — the Phase 8 rubric extension and its scorer.

The point of these tests is that the *legacy* average stays comparable to the recorded
2026-08-03 baseline of 1.96. New dimensions are reported alongside it, never folded into
it, so a before/after table means what it says.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

evaluator = importlib.import_module("run_e2e_eval")

LEGACY_DIMENSIONS = {
    "decision_completeness",
    "evidence_quality",
    "analytical_quality",
    "adversarial_robustness",
    "traceability",
}
PHASE8_DIMENSIONS = {
    "value_model_binding",
    "independent_review",
    "disconfirmation",
    "commitment_to_action",
}


@pytest.fixture(scope="module")
def rubric() -> dict[str, Any]:
    return yaml.safe_load((REPO_ROOT / "benchmarks" / "rubric.yaml").read_text(encoding="utf-8"))


# ── rubric shape ─────────────────────────────────────────────────────────────


def test_legacy_dimensions_are_untouched(rubric: dict[str, Any]) -> None:
    """Any edit here breaks comparability with the recorded baseline."""
    dimensions = rubric["dimensions"]
    for name in LEGACY_DIMENSIONS:
        assert name in dimensions
        assert "phase" not in dimensions[name], f"{name} must stay a legacy dimension"


def test_phase8_dimensions_are_marked(rubric: dict[str, Any]) -> None:
    dimensions = rubric["dimensions"]
    for name in PHASE8_DIMENSIONS:
        assert dimensions[name]["phase"] == 8


def test_every_criterion_has_a_full_scoring_band(rubric: dict[str, Any]) -> None:
    for name, dimension in rubric["dimensions"].items():
        for criterion in dimension["criteria"]:
            assert criterion["score_range"] == [0, 2], f"{name}/{criterion['id']}"
            assert set(criterion["scoring"]) == {0, 1, 2}, f"{name}/{criterion['id']}"


def test_criterion_ids_are_unique(rubric: dict[str, Any]) -> None:
    ids = [c["id"] for d in rubric["dimensions"].values() for c in d["criteria"]]
    assert len(ids) == len(set(ids))


# ── scoring ──────────────────────────────────────────────────────────────────


class _FakeCase:
    """Just enough of ``Case`` for the scorer: a root with artifact files."""

    def __init__(self, root: Path) -> None:
        self.root = root


def _case(tmp_path: Path, files: dict[str, Any] | None = None) -> _FakeCase:
    (tmp_path / "shared").mkdir(parents=True, exist_ok=True)
    (tmp_path / "outputs").mkdir(parents=True, exist_ok=True)
    for relative, payload in (files or {}).items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return _FakeCase(tmp_path)


def _metrics(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "value_model_present": True,
        "value_model_score_coverage": 1.0,
        "independent_review_verdict": "concur",
        "limitations_count": 2,
        "ach_evidence_scored": 4,
        "ach_alternatives": 3,
        "ach_matrix_complete": True,
        "ach_zero_diagnosticity_records": 1,
        "next_action_count": 2,
        "next_actions_with_first_step": 2,
        "next_actions_placeholder_owner": 0,
        "monitoring_indicators": 3,
        "monitoring_mitigations": 1,
        "monitoring_concretized": True,
    }
    base.update(overrides)
    return base


def test_a_fully_equipped_case_scores_two_everywhere(tmp_path: Path) -> None:
    case = _case(
        tmp_path,
        {
            "shared/decision_spec.yaml": {"alternatives": ["a", "b", "c"]},
            "outputs/independent_review.yaml": {"reasoning": " ".join(["word"] * 40)},
        },
    )
    scores = evaluator._score_phase8(case, _metrics())
    assert scores == {
        "vm-1": 2,
        "vm-2": 2,
        "ir-1": 2,
        "ir-2": 2,
        "dq-1": 2,
        "dq-2": 2,
        "ca-1": 2,
        "ca-2": 2,
    }


def test_absent_value_model_scores_zero(tmp_path: Path) -> None:
    case = _case(tmp_path)
    scores = evaluator._score_phase8(case, _metrics(value_model_present=False))
    assert scores["vm-1"] == 0
    assert scores["vm-2"] == 0


def test_partial_objective_score_coverage_scores_one(tmp_path: Path) -> None:
    case = _case(tmp_path)
    scores = evaluator._score_phase8(case, _metrics(value_model_score_coverage=0.5))
    assert scores["vm-1"] == 1


def test_rank_divergence_without_explanation_scores_zero(tmp_path: Path) -> None:
    case = _case(
        tmp_path,
        {
            "shared/gates/synthesis.yaml": {
                "findings": [{"check_id": "value_model.rank_divergence", "severity": "warn"}]
            },
            "outputs/final_recommendation.yaml": {"key_reasons": ["Because it is better."]},
        },
    )
    assert evaluator._score_phase8(case, _metrics())["vm-2"] == 0


def test_rank_divergence_that_is_argued_scores_one(tmp_path: Path) -> None:
    case = _case(
        tmp_path,
        {
            "shared/gates/synthesis.yaml": {
                "findings": [{"check_id": "value_model.rank_divergence", "severity": "warn"}]
            },
            "outputs/final_recommendation.yaml": {
                "key_reasons": ["Liquidity is a threshold, not a tradeoff, so the weights mislead."]
            },
        },
    )
    assert evaluator._score_phase8(case, _metrics())["vm-2"] == 1


def test_missing_independent_review_scores_zero(tmp_path: Path) -> None:
    case = _case(tmp_path)
    assert evaluator._score_phase8(case, _metrics(independent_review_verdict=None))["ir-1"] == 0


def test_bare_concur_scores_one(tmp_path: Path) -> None:
    """A review that concurs without deriving anything is the failure mode."""
    case = _case(tmp_path, {"outputs/independent_review.yaml": {"reasoning": "Looks right."}})
    assert evaluator._score_phase8(case, _metrics())["ir-1"] == 1


def test_limitations_scoring_bands(tmp_path: Path) -> None:
    case = _case(tmp_path)
    assert evaluator._score_phase8(case, _metrics(limitations_count=0))["ir-2"] == 0
    assert evaluator._score_phase8(case, _metrics(limitations_count=1))["ir-2"] == 1
    assert evaluator._score_phase8(case, _metrics(limitations_count=3))["ir-2"] == 2


def test_matrix_missing_an_alternative_scores_one(tmp_path: Path) -> None:
    case = _case(tmp_path, {"shared/decision_spec.yaml": {"alternatives": ["a", "b", "c", "d"]}})
    assert evaluator._score_phase8(case, _metrics(ach_alternatives=3))["dq-1"] == 1


def test_absent_matrix_scores_zero(tmp_path: Path) -> None:
    case = _case(tmp_path)
    scores = evaluator._score_phase8(case, _metrics(ach_evidence_scored=0))
    assert scores["dq-1"] == 0
    assert scores["dq-2"] == 0


def test_wholly_undiscriminating_matrix_scores_zero(tmp_path: Path) -> None:
    case = _case(tmp_path, {"shared/decision_spec.yaml": {"alternatives": ["a", "b", "c"]}})
    scores = evaluator._score_phase8(
        case, _metrics(ach_evidence_scored=4, ach_zero_diagnosticity_records=4)
    )
    assert scores["dq-2"] == 0


def test_placeholder_owner_downgrades_the_action_plan(tmp_path: Path) -> None:
    case = _case(tmp_path)
    assert evaluator._score_phase8(case, _metrics(next_actions_placeholder_owner=1))["ca-1"] == 1


def test_unconcretized_monitoring_scores_one(tmp_path: Path) -> None:
    case = _case(tmp_path)
    assert evaluator._score_phase8(case, _metrics(monitoring_concretized=False))["ca-2"] == 1


def test_absent_monitoring_scores_zero(tmp_path: Path) -> None:
    case = _case(tmp_path)
    assert evaluator._score_phase8(case, _metrics(monitoring_indicators=0))["ca-2"] == 0
