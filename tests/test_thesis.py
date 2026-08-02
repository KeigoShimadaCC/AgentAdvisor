from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.artifacts import (
    ConfidenceAssessment,
    ModelStability,
    PreliminaryRecommendation,
    ProbabilityEstimate,
    ProbabilityMethod,
    ThesisTrigger,
)
from orchestrator.case_store import Case, create_case
from orchestrator.thesis import current_head, drift_summary, load_ledger, write_thesis


@pytest.fixture
def case(tmp_path: Path) -> Case:
    return create_case("thesis", cases_root=tmp_path)


def _recommendation(
    alternative: str,
    *,
    rationale: list[str] | None = None,
    rec: float = 0.6,
) -> PreliminaryRecommendation:
    return PreliminaryRecommendation(
        preferred_alternative=alternative,
        rationale=rationale or ["Reasoning that stands on its own"],
        key_assumptions=[],
        outcome_probabilities={
            "positive_return_12m": ProbabilityEstimate(
                method=ProbabilityMethod.SCENARIO_MODEL, point=0.5
            )
        },
        evidence_confidence=ConfidenceAssessment(value=0.5, basis="Mixed"),
        recommendation_confidence=ConfidenceAssessment(value=rec, basis="Balanced"),
        model_stability=ModelStability(
            share_of_sensitivity_runs_supporting_recommendation=1.0,
            runs_total=2,
            runs_supporting=2,
        ),
        unresolved_evidence_gaps=[],
        major_risks=["drawdown"],
    )


def test_first_revision_has_no_previous_and_is_not_a_change(case: Case) -> None:
    revision = write_thesis(
        case, _recommendation("staged_entry"), trigger=ThesisTrigger.PROVISIONAL
    )

    assert revision.revision == 1
    assert revision.previous_alternative is None
    assert revision.changed is False
    assert revision.trigger is ThesisTrigger.PROVISIONAL


def test_ledger_is_append_only_and_ordered(case: Case) -> None:
    write_thesis(case, _recommendation("staged_entry"), trigger=ThesisTrigger.PROVISIONAL)
    write_thesis(case, _recommendation("staged_entry"), trigger=ThesisTrigger.PRELIMINARY)
    write_thesis(case, _recommendation("etf_diversified"), trigger=ThesisTrigger.REPAIR)

    ledger = load_ledger(case)
    assert [entry.revision for entry in ledger] == [1, 2, 3]
    assert [entry.trigger.value for entry in ledger] == [
        "provisional",
        "preliminary",
        "repair",
    ]


def test_changing_the_preferred_alternative_is_recorded_as_a_change(case: Case) -> None:
    write_thesis(case, _recommendation("staged_entry"), trigger=ThesisTrigger.PROVISIONAL)
    revision = write_thesis(
        case, _recommendation("etf_diversified"), trigger=ThesisTrigger.PRELIMINARY
    )

    assert revision.previous_alternative == "staged_entry"
    assert revision.changed is True


def test_holding_the_same_alternative_is_not_a_change(case: Case) -> None:
    write_thesis(case, _recommendation("staged_entry"), trigger=ThesisTrigger.PROVISIONAL)
    revision = write_thesis(
        case, _recommendation("staged_entry"), trigger=ThesisTrigger.PRELIMINARY
    )

    assert revision.changed is False


def test_cited_ids_in_the_rationale_are_captured_as_drivers(case: Case) -> None:
    revision = write_thesis(
        case,
        _recommendation(
            "staged_entry",
            rationale=["Growth is strong [E-001] but concentrated [E-002]", "Depends on [A-003]"],
        ),
        trigger=ThesisTrigger.PRELIMINARY,
    )

    assert revision.changed_because_evidence_ids == ["E-001", "E-002"]
    assert revision.changed_because_assumption_ids == ["A-003"]


def test_objection_ids_are_attached_on_repair(case: Case) -> None:
    revision = write_thesis(
        case,
        _recommendation("staged_entry"),
        trigger=ThesisTrigger.REPAIR,
        objection_ids=["O-002", "O-001", "O-001"],
    )

    assert revision.changed_because_objection_ids == ["O-001", "O-002"]


def test_write_thesis_also_updates_the_current_recommendation(case: Case) -> None:
    write_thesis(case, _recommendation("staged_entry"), trigger=ThesisTrigger.PROVISIONAL)
    write_thesis(case, _recommendation("etf_diversified"), trigger=ThesisTrigger.PRELIMINARY)

    assert case.read_artifact(PreliminaryRecommendation).preferred_alternative == (
        "etf_diversified"
    )
    head = current_head(case)
    assert head is not None and head.preferred_alternative == "etf_diversified"


def test_drift_summary_reports_the_path_and_change_count(case: Case) -> None:
    write_thesis(case, _recommendation("staged_entry"), trigger=ThesisTrigger.PROVISIONAL)
    write_thesis(case, _recommendation("etf_diversified"), trigger=ThesisTrigger.PRELIMINARY)
    write_thesis(case, _recommendation("etf_diversified"), trigger=ThesisTrigger.REPAIR)

    summary = drift_summary(case)
    assert summary["revisions"] == 3
    assert summary["changed_count"] == 1
    path = summary["path"]
    assert isinstance(path, list)
    assert [step["preferred_alternative"] for step in path] == [
        "staged_entry",
        "etf_diversified",
        "etf_diversified",
    ]


def test_empty_ledger_reports_no_revisions(case: Case) -> None:
    assert current_head(case) is None
    assert drift_summary(case) == {"revisions": 0, "changed_count": 0, "path": []}


def test_long_rationale_is_truncated_at_a_word_boundary(case: Case) -> None:
    reason = "Retention durability is the load-bearing input " * 12
    revision = write_thesis(
        case, _recommendation("staged_entry", rationale=[reason]), trigger=ThesisTrigger.PRELIMINARY
    )
    digest = revision.rationale_digest[0]

    assert len(digest) <= 220
    assert digest.endswith("…")
    assert not digest[:-1].endswith(" ")
    # The cut lands between words: every word in the digest is a whole word.
    assert reason.split()[: len(digest[:-1].split())] == digest[:-1].split()


def test_a_short_rationale_is_kept_verbatim(case: Case) -> None:
    revision = write_thesis(
        case,
        _recommendation("staged_entry", rationale=["Growth is strong [E-001]"]),
        trigger=ThesisTrigger.PRELIMINARY,
    )

    assert revision.rationale_digest == ["Growth is strong [E-001]"]


def test_every_revision_is_audited(case: Case) -> None:
    write_thesis(case, _recommendation("staged_entry"), trigger=ThesisTrigger.PROVISIONAL)

    audit_text = (case.root / "audit.jsonl").read_text(encoding="utf-8")
    assert "thesis_revision_recorded" in audit_text
