from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import EvidenceBatch
from orchestrator.normalize import (
    dump_normalized_batch,
    humanize_independence_group,
    normalize_evidence_batch,
)


def _fixture_records(filename: str) -> list[dict[str, Any]]:
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "roles" / "researcher" / filename
    payload = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    records = payload.get("records")
    assert isinstance(records, list)
    return records


def test_normalization_dedupes_groups_links_staleness_and_is_deterministic() -> None:
    records = _fixture_records("normalize_input.yaml")
    evidence_batch = EvidenceBatch(
        task_id="T-012-normalize",
        question="What was Japan's 2020 census population?",
        records=records,
        no_evidence_found=False,
        search_notes="Fixture replay for normalize determinism coverage.",
    )

    first = normalize_evidence_batch(
        evidence_batch,
        stale_after_days=3650,
    )
    second = normalize_evidence_batch(
        records,
        question="What was Japan's 2020 census population?",
        stale_after_days=3650,
    )

    first_dump = dump_normalized_batch(first)
    second_dump = dump_normalized_batch(second)
    assert first_dump == second_dump

    accepted_ids = {record.evidence_id for record in first.accepted}
    assert "E-002" not in accepted_ids

    duplicate_reasons = [
        reason
        for item in first.quarantined
        for reason in item.reasons
        if reason.startswith("duplicate_of:")
    ]
    assert "duplicate_of:E-001" in duplicate_reasons

    by_id = {record.evidence_id: record for record in first.accepted}
    assert by_id["E-003"].independence_group == by_id["E-004"].independence_group
    assert ("E-001", "E-005") in first.contradiction_links
    assert "E-006" in first.stale_evidence_ids
    assert any("Stale for this question" in limitation for limitation in by_id["E-006"].limitations)


# --- origin-keyed independence groups (SPEC-031) ---


def _record(evidence_id: str, *, publisher: str, url: str) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "claim": f"Claim behind {evidence_id}.",
        "source_title": "Quarterly filing",
        "publisher": publisher,
        "source_url": url,
        "source_type": "regulatory_filing",
        "publication_date": "2026-06-01",
        "retrieval_date": "2026-07-01",
        "excerpt": "Excerpt.",
        "reliability": "high",
        "directness": "high",
        "independence_group": "placeholder",
        "limitations": ["Scope"],
        "retrieved_by": "researcher",
    }


def _group_for(record: dict[str, Any], question: str) -> str:
    batch = normalize_evidence_batch([record], question=question, stale_after_days=3650)
    assert len(batch.accepted) == 1
    return batch.accepted[0].independence_group


def test_one_origin_answering_two_questions_forms_one_independence_group() -> None:
    first = _group_for(
        _record("E-001", publisher="AAA Investor Relations", url="https://ir.aaa.com/q2-filing"),
        "What is AAA's retention trend?",
    )
    second = _group_for(
        _record("E-002", publisher="AAA Investor Relations", url="https://ir.aaa.com/q3-filing"),
        "What is AAA's margin trend?",
    )

    assert first == second == "origin-aaa.com"


def test_group_ids_no_longer_embed_the_research_question() -> None:
    group = _group_for(
        _record("E-001", publisher="Example Capital", url="https://example.com/review"),
        "Should the fund invest in AAA this quarter?",
    )

    assert "invest" not in group
    assert "quarter" not in group
    assert group == "origin-example.com"


def test_a_wire_service_outranks_the_domain_when_naming_the_group() -> None:
    record = _record("E-001", publisher="Markets Bulletin", url="https://markets-bulletin.com/jp")
    record["excerpt"] = "This article republishes Reuters data on the Q1 contraction."

    assert _group_for(record, "Did the economy contract?") == "wire-reuters"


def test_generated_group_ids_render_as_human_labels() -> None:
    assert humanize_independence_group("origin-example.com") == "example.com (origin)"
    assert humanize_independence_group("wire-associated-press") == "Associated Press (wire service)"
    assert (
        humanize_independence_group("publisher-example-capital-research")
        == "Example Capital Research (publisher)"
    )
    assert humanize_independence_group("uncertain-source-cluster") == "Uncertain source cluster"


def test_question_keyed_groups_recorded_before_the_change_still_get_labels() -> None:
    assert (
        humanize_independence_group("should-i-invest-in-aaa-publisher-aaa-investor-relations")
        == "Aaa Investor Relations (publisher)"
    )
    assert (
        humanize_independence_group("should-i-invest-in-aaa-wire-reuters")
        == "Reuters (wire service)"
    )
    assert (
        humanize_independence_group("should-i-invest-in-aaa-uncertain-source-cluster")
        == "Uncertain source cluster"
    )


def test_an_id_with_no_kind_marker_is_passed_through_rather_than_relabelled() -> None:
    assert humanize_independence_group("aaa-q2-filing") == "aaa-q2-filing"
