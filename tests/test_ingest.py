"""SPEC-043 — private evidence: ingestion, provenance, isolation and the gate check."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from orchestrator.artifacts import (
    ClarificationKind,
    ClarificationQuestion,
    ConfidenceAssessment,
    EvidenceRecord,
    FinalRecommendation,
    IntakeField,
    IntakeRecord,
    Level,
    ModelStability,
    NextAction,
    ProbabilityEstimate,
    ProbabilityMethod,
    SourceType,
)
from orchestrator.artifacts.evidence_critique import EvidenceFlag, SourceTier
from orchestrator.case_store import create_case
from orchestrator.evidence_critic import critique_evidence
from orchestrator.gates import run_stage_gate
from orchestrator.ingest import (
    chunk_markdown,
    ingest_case_inputs,
    record_from_fact_answer,
    unsupported_input_files,
)
from orchestrator.projection import project
from orchestrator.workspace import (
    PRIVATE_EVIDENCE_ROLES,
    PrivateEvidenceLeak,
    assert_private_evidence_allowed,
)

OFFER = """# Offer letter

## Compensation

Base salary is 180,000 USD per year, reviewed annually each March.

## Equity

40,000 restricted stock units vesting over four years, one-year cliff.
"""


def _seed(tmp_path: Path, files: dict[str, str]):
    case = create_case("private", cases_root=tmp_path)
    inputs = case.root / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (inputs / name).write_text(content, encoding="utf-8")
    return case


# ── chunking ─────────────────────────────────────────────────────────────────


def test_chunks_split_on_headings_and_keep_the_heading_path() -> None:
    chunks = chunk_markdown(OFFER)
    paths = [chunk.heading_path for chunk in chunks]
    assert "Offer letter > Compensation" in paths
    assert "Offer letter > Equity" in paths


def test_chunk_text_carries_the_section_body() -> None:
    chunks = chunk_markdown(OFFER)
    comp = next(c for c in chunks if c.heading_path.endswith("Compensation"))
    assert "180,000 USD" in comp.text


def test_a_document_with_no_headings_still_chunks() -> None:
    chunks = chunk_markdown("Just a note about the lease.\n")
    assert len(chunks) == 1
    assert "lease" in chunks[0].text


def test_oversized_sections_are_split_to_the_excerpt_budget() -> None:
    body = "word " * 2000
    chunks = chunk_markdown(f"# Big\n\n{body}", max_chars=500)
    assert len(chunks) > 1
    assert all(len(chunk.text) <= 500 for chunk in chunks)


def test_empty_content_yields_no_chunks() -> None:
    assert chunk_markdown("   \n\n  ") == []


# ── ingestion and provenance ─────────────────────────────────────────────────


def test_ingestion_mints_user_document_records(tmp_path: Path) -> None:
    case = _seed(tmp_path, {"offer.md": OFFER})
    records = ingest_case_inputs(case, retrieved_on=date(2026, 8, 4))
    assert records
    assert all(record.source_type is SourceType.USER_DOCUMENT for record in records)
    assert all(record.evidence_id.startswith("E-") for record in records)


def test_records_use_a_file_url_and_are_written_to_the_case(tmp_path: Path) -> None:
    case = _seed(tmp_path, {"offer.md": OFFER})
    ingest_case_inputs(case)
    stored = case.list_artifacts(EvidenceRecord)
    assert stored
    assert all(record.source_url == "file://inputs/offer.md" for record in stored)


def test_all_chunks_of_one_document_share_one_independence_group(tmp_path: Path) -> None:
    """Two excerpts from one file are one source, never corroboration."""
    case = _seed(tmp_path, {"offer.md": OFFER})
    records = ingest_case_inputs(case)
    assert len(records) > 1
    assert len({record.independence_group for record in records}) == 1


def test_two_documents_get_two_independence_groups(tmp_path: Path) -> None:
    case = _seed(tmp_path, {"offer.md": OFFER, "lease.md": "# Lease\n\nRent is 2,400/mo.\n"})
    records = ingest_case_inputs(case)
    assert len({record.independence_group for record in records}) == 2


def test_records_carry_their_unverifiability_as_a_limitation(tmp_path: Path) -> None:
    case = _seed(tmp_path, {"offer.md": OFFER})
    record = ingest_case_inputs(case)[0]
    assert any("no external source confirms" in item for item in record.limitations)


def test_unsupported_files_are_skipped_and_reported(tmp_path: Path) -> None:
    case = _seed(tmp_path, {"offer.md": OFFER, "terms.pdf": "%PDF-1.4 binary-ish"})
    records = ingest_case_inputs(case)
    assert all("offer.md" in record.source_url for record in records)
    assert unsupported_input_files(case) == ["terms.pdf"]


def test_absent_inputs_directory_is_a_no_op(tmp_path: Path) -> None:
    case = create_case("no-inputs", cases_root=tmp_path)
    assert ingest_case_inputs(case) == []
    assert unsupported_input_files(case) == []


def test_empty_inputs_directory_is_a_no_op(tmp_path: Path) -> None:
    case = _seed(tmp_path, {})
    assert ingest_case_inputs(case) == []


def test_fact_answers_become_user_supplied_evidence() -> None:
    record = record_from_fact_answer(
        evidence_id="E-042",
        question_id="CQ-004",
        question="What is your cost basis?",
        answer="41.20 per share, bought March 2024",
        retrieved_on=date(2026, 8, 4),
    )
    assert record.source_type is SourceType.USER_DOCUMENT
    assert record.source_url == "user://intake/CQ-004"
    assert "41.20" in record.excerpt


# ── evidence critic treatment ────────────────────────────────────────────────


def test_user_documents_score_in_the_unverifiable_tier(tmp_path: Path) -> None:
    case = _seed(tmp_path, {"offer.md": OFFER})
    records = ingest_case_inputs(case, retrieved_on=date(2026, 8, 4))
    critique = critique_evidence(records, as_of=date(2026, 8, 4))
    assert all(score.source_tier is SourceTier.UNVERIFIABLE for score in critique.scored)


def test_user_documents_are_flagged_as_user_supplied(tmp_path: Path) -> None:
    case = _seed(tmp_path, {"offer.md": OFFER})
    records = ingest_case_inputs(case, retrieved_on=date(2026, 8, 4))
    critique = critique_evidence(records, as_of=date(2026, 8, 4))
    assert all(EvidenceFlag.USER_SUPPLIED in score.flags for score in critique.scored)


def test_user_documents_never_count_as_primary_sources(tmp_path: Path) -> None:
    case = _seed(tmp_path, {"offer.md": OFFER})
    records = ingest_case_inputs(case, retrieved_on=date(2026, 8, 4))
    critique = critique_evidence(records, as_of=date(2026, 8, 4))
    assert critique.primary_source_share == 0.0


# ── clarification kinds ──────────────────────────────────────────────────────


def test_field_question_without_a_target_is_rejected() -> None:
    with pytest.raises(ValidationError, match="names no resolves_field"):
        ClarificationQuestion(
            question_id="CQ-001",
            kind=ClarificationKind.FIELD,
            question="Which date?",
            materiality_reason="It matters.",
        )


def test_fact_question_needs_no_target() -> None:
    question = ClarificationQuestion(
        question_id="CQ-002",
        kind=ClarificationKind.FACT,
        question="What is your cost basis?",
        materiality_reason="It decides the tax treatment.",
    )
    assert question.resolves_field is None


def test_document_question_must_not_name_a_target() -> None:
    with pytest.raises(ValidationError, match="must not name a resolves_field"):
        ClarificationQuestion(
            question_id="CQ-003",
            kind=ClarificationKind.DOCUMENT,
            question="Can you add the term sheet?",
            materiality_reason="It settles the terms.",
            resolves_field=IntakeField.CONSTRAINTS,
        )


def test_legacy_questions_without_a_kind_still_validate() -> None:
    """Intake records written before SPEC-043 must keep loading."""
    question = ClarificationQuestion(
        question_id="CQ-001",
        resolves_field=IntakeField.DEADLINE,
        question="Which date?",
        materiality_reason="It matters.",
    )
    assert question.kind is ClarificationKind.FIELD


def test_intake_accepts_eight_questions_and_rejects_nine() -> None:
    def q(index: int) -> ClarificationQuestion:
        return ClarificationQuestion(
            question_id=f"CQ-{index:03d}",
            kind=ClarificationKind.FACT,
            question=f"Question {index}?",
            materiality_reason="It matters.",
        )

    IntakeRecord(raw_prompt="x", clarification_questions=[q(i) for i in range(1, 9)])
    with pytest.raises(ValidationError):
        IntakeRecord(raw_prompt="x", clarification_questions=[q(i) for i in range(1, 10)])


def test_field_question_targeting_a_populated_field_is_still_rejected() -> None:
    """The original guard must survive the kind split."""
    with pytest.raises(ValidationError, match="already populated"):
        IntakeRecord(
            raw_prompt="x",
            deadline=date(2026, 12, 31),
            clarification_questions=[
                ClarificationQuestion(
                    question_id="CQ-001",
                    kind=ClarificationKind.FIELD,
                    resolves_field=IntakeField.DEADLINE,
                    question="Which date?",
                    materiality_reason="It matters.",
                )
            ],
        )


# ── isolation ────────────────────────────────────────────────────────────────


def test_reasoning_roles_may_receive_private_evidence(tmp_path: Path) -> None:
    case = _seed(tmp_path, {"offer.md": OFFER})
    ingest_case_inputs(case)
    projected = project(case, ["private_evidence"], budget_chars=200_000)
    assert projected
    for role in ("analyst", "director", "researcher"):
        assert_private_evidence_allowed(role, projected)


@pytest.mark.parametrize("role", ["reviewer", "auditor", "synthesizer"])
def test_review_roles_are_refused_private_evidence(tmp_path: Path, role: str) -> None:
    """A reviewer anchored on the decision owner's own material is not independent."""
    case = _seed(tmp_path, {"offer.md": OFFER})
    ingest_case_inputs(case)
    projected = project(case, ["private_evidence"], budget_chars=200_000)
    with pytest.raises(PrivateEvidenceLeak, match=role):
        assert_private_evidence_allowed(role, projected)


def test_review_roles_are_not_in_the_allow_list() -> None:
    assert not {"reviewer", "auditor", "synthesizer"} & PRIVATE_EVIDENCE_ROLES


def test_the_projection_carries_an_unverifiability_notice(tmp_path: Path) -> None:
    case = _seed(tmp_path, {"offer.md": OFFER})
    ingest_case_inputs(case)
    projected = project(case, ["private_evidence"], budget_chars=200_000)
    blob = "\n".join(artifact.yaml_text for artifact in projected)
    assert "no external verification" in blob
    assert "never corroboration" in blob


def test_projection_is_empty_without_private_evidence(tmp_path: Path) -> None:
    case = create_case("public-only", cases_root=tmp_path)
    assert project(case, ["private_evidence"], budget_chars=200_000) == []


# ── gate check ───────────────────────────────────────────────────────────────


def _prob(point: float) -> ProbabilityEstimate:
    return ProbabilityEstimate(method=ProbabilityMethod.SCENARIO_MODEL, point=point, adjustments=[])


def _final(key_reasons: list[str]) -> FinalRecommendation:
    payload: dict[str, Any] = {
        "recommended_action": "Accept the offer.",
        "timing": "This week.",
        "decision_confidence_summary": "Moderate.",
        "alternatives_considered": [
            {"alternative": "decline", "rank": 2, "rationale": "Lower upside."}
        ],
        "key_reasons": key_reasons,
        "scenario_analysis": [
            {"scenario_name": "base", "summary": "Base case.", "probability": _prob(0.6)}
        ],
        "next_actions": [
            NextAction(
                action_id="N-001",
                action="Reply",
                owner="user",
                by_date=date(2026, 8, 15),
                first_step="Draft the acceptance email",
                why_now="The offer expires",
            )
        ],
        "outcome_probabilities": {"success": _prob(0.6)},
        "evidence_confidence": ConfidenceAssessment(value=0.6, basis="Mixed"),
        "recommendation_confidence": ConfidenceAssessment(value=0.65, basis="Balanced"),
        "model_stability": ModelStability(
            share_of_sensitivity_runs_supporting_recommendation=0.7,
            runs_total=10,
            runs_supporting=7,
        ),
    }
    return FinalRecommendation(**payload)


def _public_record(evidence_id: str) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        claim="Market salaries rose 6%.",
        source_title="Wage survey",
        publisher="Statistics office",
        source_url="https://example.gov/wages",
        source_type=SourceType.OFFICIAL_STATISTIC,
        publication_date=date(2026, 3, 1),
        retrieval_date=date(2026, 8, 1),
        excerpt="Median wages rose 6% year over year.",
        reliability=Level.HIGH,
        directness=Level.HIGH,
        independence_group="official_statistics",
        limitations=["national aggregate"],
        retrieved_by="researcher",
    )


def test_claim_resting_only_on_private_evidence_is_flagged(tmp_path: Path) -> None:
    case = _seed(tmp_path, {"offer.md": OFFER})
    records = ingest_case_inputs(case)
    private_id = records[0].evidence_id
    case.write_artifact(_final([f"The base salary is 180,000 [{private_id}]."]))
    report = run_stage_gate(case, "synthesis", as_of=date(2026, 8, 4))
    findings = [f for f in report.findings if f.check_id == "evidence.sole_private_support"]
    assert len(findings) == 1


def test_claim_with_public_corroboration_is_not_flagged(tmp_path: Path) -> None:
    case = _seed(tmp_path, {"offer.md": OFFER})
    records = ingest_case_inputs(case)
    case.write_artifact(_public_record("E-900"))
    case.write_artifact(_final([f"The offer beats the market [{records[0].evidence_id}] [E-900]."]))
    report = run_stage_gate(case, "synthesis", as_of=date(2026, 8, 4))
    assert not [f for f in report.findings if f.check_id == "evidence.sole_private_support"]


def test_case_without_private_evidence_produces_no_finding(tmp_path: Path) -> None:
    case = create_case("public", cases_root=tmp_path)
    case.write_artifact(_public_record("E-900"))
    case.write_artifact(_final(["Market wages rose [E-900]."]))
    report = run_stage_gate(case, "synthesis", as_of=date(2026, 8, 4))
    assert not [f for f in report.findings if f.check_id == "evidence.sole_private_support"]
