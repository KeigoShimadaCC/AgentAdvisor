"""SPEC-040 — Analysis of Competing Hypotheses: matrix validation and scoring."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from orchestrator.ach import (
    diagnosticity,
    rank_by_disconfirmation,
    select_matrix_evidence,
    weighted_inconsistency,
    zero_diagnosticity_records,
)
from orchestrator.artifacts import (
    MAX_ACH_EVIDENCE,
    ACHCell,
    ACHConsistency,
    ACHMatrix,
    DecisionSpec,
    Depth,
    Reversibility,
    RiskTolerance,
)
from orchestrator.case_store import create_case
from orchestrator.gates import run_stage_gate

C = ACHConsistency


def _matrix(scores: dict[str, dict[str, ACHConsistency]], **overrides: Any) -> ACHMatrix:
    alternatives = sorted({alt for row in scores.values() for alt in row})
    payload: dict[str, Any] = {
        "decision_question": "Should I proceed?",
        "alternatives": alternatives,
        "evidence_ids": list(scores),
        "cells": [
            ACHCell(
                evidence_id=evidence_id,
                alternative=alternative,
                consistency=consistency,
                note=f"{evidence_id} vs {alternative}",
            )
            for evidence_id, row in scores.items()
            for alternative, consistency in row.items()
        ],
    }
    payload.update(overrides)
    return ACHMatrix(**payload)


# ── matrix validation ────────────────────────────────────────────────────────


def test_complete_matrix_is_accepted() -> None:
    matrix = _matrix(
        {
            "E-001": {"a": C.CONSISTENT, "b": C.INCONSISTENT},
            "E-002": {"a": C.NEUTRAL, "b": C.NEUTRAL},
        }
    )
    assert len(matrix.cells) == 4


def test_incomplete_matrix_is_rejected() -> None:
    """A partial matrix would let the ranking be driven by which cells were filled."""
    with pytest.raises(ValidationError, match="matrix is incomplete"):
        ACHMatrix(
            decision_question="Should I proceed?",
            alternatives=["a", "b"],
            evidence_ids=["E-001"],
            cells=[
                ACHCell(evidence_id="E-001", alternative="a", consistency=C.CONSISTENT, note="n")
            ],
        )


def test_duplicate_cell_is_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate cell"):
        ACHMatrix(
            decision_question="Should I proceed?",
            alternatives=["a", "b"],
            evidence_ids=["E-001"],
            cells=[
                ACHCell(evidence_id="E-001", alternative="a", consistency=C.CONSISTENT, note="n"),
                ACHCell(evidence_id="E-001", alternative="a", consistency=C.NEUTRAL, note="n"),
                ACHCell(evidence_id="E-001", alternative="b", consistency=C.NEUTRAL, note="n"),
            ],
        )


def test_cell_for_an_undeclared_alternative_is_rejected() -> None:
    with pytest.raises(ValidationError, match="not declared in the matrix"):
        ACHMatrix(
            decision_question="Should I proceed?",
            alternatives=["a", "b"],
            evidence_ids=["E-001"],
            cells=[
                ACHCell(evidence_id="E-001", alternative="a", consistency=C.NEUTRAL, note="n"),
                ACHCell(evidence_id="E-001", alternative="b", consistency=C.NEUTRAL, note="n"),
                ACHCell(evidence_id="E-001", alternative="z", consistency=C.NEUTRAL, note="n"),
            ],
        )


def test_matrix_requires_at_least_two_alternatives() -> None:
    with pytest.raises(ValidationError):
        ACHMatrix(
            decision_question="Should I proceed?",
            alternatives=["only_one"],
            evidence_ids=["E-001"],
            cells=[
                ACHCell(
                    evidence_id="E-001", alternative="only_one", consistency=C.NEUTRAL, note="n"
                )
            ],
        )


def test_evidence_cap_is_enforced() -> None:
    scores = {
        f"E-{n:03d}": {"a": C.NEUTRAL, "b": C.NEUTRAL} for n in range(1, MAX_ACH_EVIDENCE + 2)
    }
    with pytest.raises(ValidationError, match="exceeds the 20-record cap"):
        _matrix(scores)


def test_evidence_cannot_be_both_scored_and_excluded() -> None:
    with pytest.raises(ValidationError, match="both in the matrix and in exclusions"):
        _matrix(
            {"E-001": {"a": C.NEUTRAL, "b": C.NEUTRAL}},
            excluded_evidence_ids=[{"evidence_id": "E-001", "reason": "below the cut"}],
        )


# ── diagnosticity ────────────────────────────────────────────────────────────


def test_record_scored_identically_everywhere_has_zero_diagnosticity() -> None:
    matrix = _matrix({"E-001": {"a": C.STRONGLY_CONSISTENT, "b": C.STRONGLY_CONSISTENT}})
    assert diagnosticity(matrix)["E-001"] == 0.0


def test_record_spanning_the_full_range_has_maximum_diagnosticity() -> None:
    matrix = _matrix({"E-001": {"a": C.STRONGLY_CONSISTENT, "b": C.STRONGLY_INCONSISTENT}})
    assert diagnosticity(matrix)["E-001"] == pytest.approx(1.0)


def test_partial_spread_scales_between() -> None:
    matrix = _matrix({"E-001": {"a": C.CONSISTENT, "b": C.NEUTRAL}})
    assert diagnosticity(matrix)["E-001"] == pytest.approx(0.25)


def test_zero_diagnosticity_records_are_reported() -> None:
    matrix = _matrix(
        {
            "E-001": {"a": C.CONSISTENT, "b": C.INCONSISTENT},
            "E-002": {"a": C.NEUTRAL, "b": C.NEUTRAL},
            "E-003": {"a": C.CONSISTENT, "b": C.CONSISTENT},
        }
    )
    assert zero_diagnosticity_records(matrix) == ("E-002", "E-003")


def test_authoritative_but_undiscriminating_evidence_carries_no_weight() -> None:
    """The central claim of the technique: consistency with everything proves nothing."""
    matrix = _matrix(
        {
            "E-001": {"a": C.STRONGLY_CONSISTENT, "b": C.STRONGLY_CONSISTENT},
            "E-002": {"a": C.STRONGLY_INCONSISTENT, "b": C.CONSISTENT},
        }
    )
    totals = weighted_inconsistency(matrix)
    # E-001 contributes nothing to either side; only E-002 moves the ranking.
    assert totals["b"] == 0.0
    assert totals["a"] > 0.0


# ── ranking ──────────────────────────────────────────────────────────────────


def test_least_disconfirmed_alternative_ranks_first() -> None:
    matrix = _matrix(
        {
            "E-001": {"a": C.STRONGLY_INCONSISTENT, "b": C.CONSISTENT},
            "E-002": {"a": C.INCONSISTENT, "b": C.NEUTRAL},
        }
    )
    standings = rank_by_disconfirmation(matrix)
    assert standings[0].alternative == "b"
    assert standings[1].alternative == "a"


def test_best_supported_is_not_necessarily_least_disconfirmed() -> None:
    """The case that separates ACH from counting supporting citations.

    ``a`` has two strongly consistent records and one strongly inconsistent one;
    ``b`` has none of either. ACH prefers ``b``, because nothing rules it out.
    """
    matrix = _matrix(
        {
            "E-001": {"a": C.STRONGLY_CONSISTENT, "b": C.NEUTRAL},
            "E-002": {"a": C.STRONGLY_CONSISTENT, "b": C.NEUTRAL},
            "E-003": {"a": C.STRONGLY_INCONSISTENT, "b": C.NEUTRAL},
        }
    )
    standings = rank_by_disconfirmation(matrix)
    assert standings[0].alternative == "b"
    assert "E-003" in standings[1].disconfirming_evidence_ids


def test_ties_keep_the_declared_alternative_order() -> None:
    matrix = _matrix({"E-001": {"a": C.NEUTRAL, "b": C.NEUTRAL}})
    matrix = matrix.model_copy(update={"alternatives": ["b", "a"]})
    standings = rank_by_disconfirmation(matrix)
    assert [s.alternative for s in standings] == ["b", "a"]


def test_disconfirming_evidence_ids_are_listed_per_alternative() -> None:
    matrix = _matrix(
        {
            "E-001": {"a": C.INCONSISTENT, "b": C.CONSISTENT},
            "E-002": {"a": C.STRONGLY_INCONSISTENT, "b": C.NEUTRAL},
        }
    )
    by_alt = {s.alternative: s for s in rank_by_disconfirmation(matrix)}
    assert by_alt["a"].disconfirming_evidence_ids == ("E-001", "E-002")
    assert by_alt["b"].disconfirming_evidence_ids == ()


# ── evidence selection ───────────────────────────────────────────────────────


def test_selection_takes_the_highest_authority_records_up_to_the_cap() -> None:
    authority = {"E-001": 0.2, "E-002": 0.9, "E-003": 0.5}
    selected, excluded = select_matrix_evidence(authority, list(authority), cap=2)
    assert selected == ["E-002", "E-003"]
    assert excluded == ["E-001"]


def test_selection_is_deterministic_under_ties() -> None:
    authority = {"E-003": 0.5, "E-001": 0.5, "E-002": 0.5}
    selected, _ = select_matrix_evidence(authority, list(authority), cap=2)
    assert selected == ["E-001", "E-002"]


def test_unscored_evidence_defaults_to_the_bottom() -> None:
    selected, excluded = select_matrix_evidence({"E-002": 0.7}, ["E-001", "E-002"], cap=1)
    assert selected == ["E-002"]
    assert excluded == ["E-001"]


def test_selection_below_the_cap_excludes_nothing() -> None:
    selected, excluded = select_matrix_evidence({"E-001": 0.5}, ["E-001"], cap=20)
    assert selected == ["E-001"]
    assert excluded == []


# ── gate checks ──────────────────────────────────────────────────────────────


def _case_with(tmp_path: Path, matrix: ACHMatrix, alternatives: list[str] | None = None):
    case = create_case("ach", cases_root=tmp_path)
    case.write_artifact(
        DecisionSpec(
            decision_id=case.root.name,
            question="Should I proceed?",
            owner="user",
            deadline=date(2026, 12, 31),
            alternatives=alternatives or list(matrix.alternatives),
            objectives=["return"],
            risk_tolerance=RiskTolerance.MODERATE,
            reversibility=Reversibility.PARTIALLY_REVERSIBLE,
            depth=Depth.STANDARD,
        )
    )
    case.write_artifact(matrix)
    return case


def test_matrix_covering_every_alternative_produces_no_mismatch(tmp_path: Path) -> None:
    matrix = _matrix({"E-001": {"a": C.CONSISTENT, "b": C.INCONSISTENT}})
    case = _case_with(tmp_path, matrix)
    report = run_stage_gate(case, "competing_hypotheses")
    assert not [f for f in report.findings if f.check_id == "ach.alternative_mismatch"]


def test_unscored_alternative_produces_a_mismatch_finding(tmp_path: Path) -> None:
    matrix = _matrix({"E-001": {"a": C.CONSISTENT, "b": C.INCONSISTENT}})
    case = _case_with(tmp_path, matrix, alternatives=["a", "b", "never_scored"])
    report = run_stage_gate(case, "competing_hypotheses")
    findings = [f for f in report.findings if f.check_id == "ach.alternative_mismatch"]
    assert len(findings) == 1
    assert findings[0].target_ids == ["never_scored"]


def test_all_neutral_matrix_produces_a_thin_matrix_finding(tmp_path: Path) -> None:
    matrix = _matrix(
        {
            "E-001": {"a": C.NEUTRAL, "b": C.NEUTRAL},
            "E-002": {"a": C.CONSISTENT, "b": C.CONSISTENT},
        }
    )
    case = _case_with(tmp_path, matrix)
    report = run_stage_gate(case, "competing_hypotheses")
    assert [f for f in report.findings if f.check_id == "ach.thin_matrix"]


def test_discriminating_matrix_produces_no_thin_finding(tmp_path: Path) -> None:
    matrix = _matrix({"E-001": {"a": C.CONSISTENT, "b": C.STRONGLY_INCONSISTENT}})
    case = _case_with(tmp_path, matrix)
    report = run_stage_gate(case, "competing_hypotheses")
    assert not [f for f in report.findings if f.check_id == "ach.thin_matrix"]


def test_gate_is_silent_without_a_matrix(tmp_path: Path) -> None:
    case = create_case("no-ach", cases_root=tmp_path)
    report = run_stage_gate(case, "competing_hypotheses")
    assert not [f for f in report.findings if f.check_id.startswith("ach.")]
