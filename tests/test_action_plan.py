"""SPEC-041 — typed action plan: model validation and the process gate checks."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from orchestrator.artifacts import (
    ConfidenceAssessment,
    FinalRecommendation,
    ModelStability,
    NextAction,
    ProbabilityEstimate,
    ProbabilityMethod,
)
from orchestrator.case_store import create_case
from orchestrator.gates import NEAR_TERM_ACTION_DAYS, run_stage_gate


def _action(action_id: str = "N-001", **overrides: Any) -> NextAction:
    payload: dict[str, Any] = {
        "action_id": action_id,
        "action": "Place the first tranche",
        "owner": "user",
        "by_date": date(2026, 8, 15),
        "first_step": "Open the brokerage order ticket",
        "why_now": "Staged entry starts now",
    }
    payload.update(overrides)
    return NextAction(**payload)


def _final(actions: list[NextAction]) -> FinalRecommendation:
    return FinalRecommendation(
        recommended_action="Proceed with a staged allocation.",
        timing="Within the current quarter.",
        decision_confidence_summary="Moderate confidence with defined guardrails.",
        alternatives_considered=[
            {"alternative": "wait", "rank": 2, "rationale": "Lower variance, lower return."}
        ],
        key_reasons=["Scenario-weighted expected value is highest [E-001]."],
        scenario_analysis=[
            {
                "scenario_name": "base",
                "summary": "Base case supports entry.",
                "probability": ProbabilityEstimate(
                    method=ProbabilityMethod.SCENARIO_MODEL, point=0.6, adjustments=[]
                ),
            }
        ],
        next_actions=actions,
        outcome_probabilities={
            "success": ProbabilityEstimate(
                method=ProbabilityMethod.SCENARIO_MODEL, point=0.6, adjustments=[]
            )
        },
        evidence_confidence=ConfidenceAssessment(value=0.6, basis="Mixed sources"),
        recommendation_confidence=ConfidenceAssessment(value=0.65, basis="Balanced"),
        model_stability=ModelStability(
            share_of_sensitivity_runs_supporting_recommendation=0.7,
            runs_total=10,
            runs_supporting=7,
        ),
    )


# ── model validation ─────────────────────────────────────────────────────────


def test_action_plan_accepts_a_resolvable_dependency_chain() -> None:
    rec = _final([_action("N-001"), _action("N-002", depends_on=["N-001"])])
    assert [action.action_id for action in rec.next_actions] == ["N-001", "N-002"]


def test_action_id_must_match_the_n_prefix() -> None:
    with pytest.raises(ValidationError):
        _action("A-001")


def test_unresolvable_dependency_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown action_id"):
        _final([_action("N-001", depends_on=["N-999"])])


def test_self_dependency_is_rejected() -> None:
    with pytest.raises(ValidationError, match="depends on itself"):
        _final([_action("N-001", depends_on=["N-001"])])


def test_two_node_cycle_is_rejected() -> None:
    with pytest.raises(ValidationError, match="cycle"):
        _final(
            [
                _action("N-001", depends_on=["N-002"]),
                _action("N-002", depends_on=["N-001"]),
            ]
        )


def test_three_node_cycle_is_rejected() -> None:
    with pytest.raises(ValidationError, match="cycle"):
        _final(
            [
                _action("N-001", depends_on=["N-003"]),
                _action("N-002", depends_on=["N-001"]),
                _action("N-003", depends_on=["N-002"]),
            ]
        )


def test_diamond_dependency_is_not_a_cycle() -> None:
    rec = _final(
        [
            _action("N-001"),
            _action("N-002", depends_on=["N-001"]),
            _action("N-003", depends_on=["N-001"]),
            _action("N-004", depends_on=["N-002", "N-003"]),
        ]
    )
    assert len(rec.next_actions) == 4


def test_duplicate_action_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate action_ids"):
        _final([_action("N-001"), _action("N-001")])


def test_next_actions_cannot_be_empty() -> None:
    with pytest.raises(ValidationError):
        _final([])


# ── gate checks ──────────────────────────────────────────────────────────────


def _case_with(tmp_path: Path, actions: list[NextAction]):
    case = create_case("actions", cases_root=tmp_path)
    case.write_artifact(_final(actions))
    return case


def test_placeholder_owner_produces_missing_owner_finding(tmp_path: Path) -> None:
    case = _case_with(tmp_path, [_action("N-001", owner="TBD")])
    report = run_stage_gate(case, "synthesis", as_of=date(2026, 8, 1))
    findings = [f for f in report.findings if f.check_id == "action_plan.missing_owner"]
    assert len(findings) == 1
    assert findings[0].target_ids == ["N-001"]


def test_named_owner_produces_no_missing_owner_finding(tmp_path: Path) -> None:
    case = _case_with(tmp_path, [_action("N-001", owner="your accountant")])
    report = run_stage_gate(case, "synthesis", as_of=date(2026, 8, 1))
    assert not [f for f in report.findings if f.check_id == "action_plan.missing_owner"]


def test_distant_plan_produces_no_near_term_action_finding(tmp_path: Path) -> None:
    as_of = date(2026, 8, 1)
    far = as_of + timedelta(days=NEAR_TERM_ACTION_DAYS + 5)
    case = _case_with(tmp_path, [_action("N-001", by_date=far)])
    report = run_stage_gate(case, "synthesis", as_of=as_of)
    assert [f for f in report.findings if f.check_id == "action_plan.no_near_term_action"]


def test_near_term_plan_produces_no_such_finding(tmp_path: Path) -> None:
    as_of = date(2026, 8, 1)
    soon = as_of + timedelta(days=NEAR_TERM_ACTION_DAYS - 5)
    case = _case_with(tmp_path, [_action("N-001", by_date=soon)])
    report = run_stage_gate(case, "synthesis", as_of=as_of)
    assert not [f for f in report.findings if f.check_id == "action_plan.no_near_term_action"]


def test_backdated_action_produces_date_in_past_finding(tmp_path: Path) -> None:
    as_of = date(2026, 8, 1)
    case = _case_with(
        tmp_path,
        [_action("N-001", by_date=as_of - timedelta(days=1)), _action("N-002", by_date=as_of)],
    )
    report = run_stage_gate(case, "synthesis", as_of=as_of)
    findings = [f for f in report.findings if f.check_id == "action_plan.date_in_past"]
    assert len(findings) == 1
    assert findings[0].target_ids == ["N-001"]


def test_gate_is_silent_when_no_final_recommendation_exists(tmp_path: Path) -> None:
    case = create_case("empty", cases_root=tmp_path)
    report = run_stage_gate(case, "synthesis", as_of=date(2026, 8, 1))
    assert not [f for f in report.findings if f.check_id.startswith("action_plan.")]
