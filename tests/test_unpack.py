from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from orchestrator.artifacts import (
    AuditEvent,
    EvidenceBatch,
    EvidenceRecord,
    Level,
    ObjectionBatch,
    ObjectionMode,
    ObjectionRecord,
    ObjectionResolutionStatus,
    SourceType,
)
from orchestrator.case_store import create_case
from orchestrator.unpack import unpack_evidence_batch, unpack_objection_batch


def _evidence(evidence_id: str, claim: str = "Revenue grew year-over-year") -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        claim=claim,
        source_title="Annual Report",
        publisher="AAA Corp",
        source_url=f"https://example.com/{evidence_id.lower()}",
        source_type=SourceType.REPUTABLE_SECONDARY,
        publication_date=date(2026, 1, 1),
        retrieval_date=date(2026, 1, 2),
        excerpt="Revenue grew by 18%.",
        reliability=Level.HIGH,
        directness=Level.MEDIUM,
        independence_group="aaa-report",
        limitations=["Company-defined segment boundaries."],
        retrieved_by="researcher-market",
    )


def _objection(objection_id: str, claim: str = "Timing risk remains") -> ObjectionRecord:
    return ObjectionRecord(
        objection_id=objection_id,
        target_section="timing",
        claim=claim,
        materiality=Level.MEDIUM,
        reasoning="Macro indicators are mixed.",
        reversal_evidence="Independent demand indicators accelerate.",
        referenced_evidence_ids=[],
        referenced_assumption_ids=[],
        resolution_status=ObjectionResolutionStatus.OPEN,
        commissioned_tasks=[],
    )


def _audit_lines(case_root: Path) -> list[AuditEvent]:
    lines = (case_root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    return [AuditEvent.model_validate_json(line) for line in lines]


def test_unpack_evidence_batch_allocates_canonical_ids_and_audits_mapping(tmp_path: Path) -> None:
    case = create_case("unpack-evidence", cases_root=tmp_path)
    batch = EvidenceBatch(
        task_id="T-001",
        question="Is demand durable?",
        records=[_evidence("E-900"), _evidence("E-901", claim="Margin expanded")],
        search_notes="Searched filings and independent coverage.",
    )

    unpacked = unpack_evidence_batch(case, batch)

    assert [record.evidence_id for record in unpacked] == ["E-001", "E-002"]
    assert [record.evidence_id for record in case.list_artifacts(EvidenceRecord)] == [
        "E-001",
        "E-002",
    ]
    assert all(record.evidence_id not in {"E-900", "E-901"} for record in unpacked)

    events = _audit_lines(case.root)
    assert len(events) == 1
    assert events[0].event_type == "evidence_batch_unpacked"
    assert events[0].payload["id_mapping"] == [
        {"original_evidence_id": "E-900", "canonical_evidence_id": "E-001"},
        {"original_evidence_id": "E-901", "canonical_evidence_id": "E-002"},
    ]


def test_unpack_evidence_batch_does_not_overwrite_existing_record_on_id_collision(
    tmp_path: Path,
) -> None:
    case = create_case("unpack-evidence-collision", cases_root=tmp_path)
    existing_id = case.next_id("E-")
    existing = _evidence(existing_id, claim="Existing canonical record")
    case.write_artifact(existing)
    batch = EvidenceBatch(
        task_id="T-002",
        question="Does this collide?",
        records=[_evidence("E-001", claim="Agent generated colliding id")],
        search_notes="Collision probe.",
    )

    unpacked = unpack_evidence_batch(case, batch)

    assert unpacked[0].evidence_id == "E-002"
    stored_existing = case.read_artifact(EvidenceRecord, "E-001")
    stored_new = case.read_artifact(EvidenceRecord, "E-002")
    assert stored_existing.claim == "Existing canonical record"
    assert stored_new.claim == "Agent generated colliding id"


def test_unpack_evidence_batch_empty_outcome_audits_zero_records(tmp_path: Path) -> None:
    case = create_case("unpack-evidence-empty", cases_root=tmp_path)
    batch = EvidenceBatch(
        task_id="T-003",
        question="Any relevant evidence?",
        records=[],
        no_evidence_found=True,
        search_notes="No credible sources found for this narrow question.",
    )

    unpacked = unpack_evidence_batch(case, batch)

    assert unpacked == []
    assert case.list_artifacts(EvidenceRecord) == []
    events = _audit_lines(case.root)
    assert len(events) == 1
    assert events[0].event_type == "evidence_batch_unpacked"
    assert events[0].payload["record_count"] == 0
    assert events[0].payload["no_evidence_found"] is True
    assert events[0].payload["id_mapping"] == []


def test_unpack_objection_batch_allocates_canonical_ids_and_audits_mapping(tmp_path: Path) -> None:
    case = create_case("unpack-objection", cases_root=tmp_path)
    batch = ObjectionBatch(
        mode=ObjectionMode.STANDARD,
        objections=[_objection("O-901"), _objection("O-902", claim="Concentration risk remains")],
    )

    unpacked = unpack_objection_batch(case, batch)

    assert [record.objection_id for record in unpacked] == ["O-001", "O-002"]
    assert [record.objection_id for record in case.list_artifacts(ObjectionRecord)] == [
        "O-001",
        "O-002",
    ]
    assert all(record.objection_id not in {"O-901", "O-902"} for record in unpacked)

    events = _audit_lines(case.root)
    assert len(events) == 1
    assert events[0].event_type == "objection_batch_unpacked"
    assert events[0].payload["id_mapping"] == [
        {"original_objection_id": "O-901", "canonical_objection_id": "O-001"},
        {"original_objection_id": "O-902", "canonical_objection_id": "O-002"},
    ]


def test_unpack_objection_batch_does_not_overwrite_existing_record_on_id_collision(
    tmp_path: Path,
) -> None:
    case = create_case("unpack-objection-collision", cases_root=tmp_path)
    existing_id = case.next_id("O-")
    existing = _objection(existing_id, claim="Existing canonical objection")
    case.write_artifact(existing)
    batch = ObjectionBatch(
        mode=ObjectionMode.STANDARD,
        objections=[_objection("O-001", claim="Agent generated colliding objection id")],
    )

    unpacked = unpack_objection_batch(case, batch)

    assert unpacked[0].objection_id == "O-002"
    stored_existing = case.read_artifact(ObjectionRecord, "O-001")
    stored_new = case.read_artifact(ObjectionRecord, "O-002")
    assert stored_existing.claim == "Existing canonical objection"
    assert stored_new.claim == "Agent generated colliding objection id"


def test_unpack_objection_batch_empty_outcome_audits_zero_records(tmp_path: Path) -> None:
    case = create_case("unpack-objection-empty", cases_root=tmp_path)
    batch = ObjectionBatch(
        mode=ObjectionMode.FINAL_PASS,
        objections=[],
        no_objections_justification="No unresolved material objections remain.",
    )

    unpacked = unpack_objection_batch(case, batch)

    assert unpacked == []
    assert case.list_artifacts(ObjectionRecord) == []
    events = _audit_lines(case.root)
    assert len(events) == 1
    assert events[0].event_type == "objection_batch_unpacked"
    assert events[0].payload["objection_count"] == 0
    assert (
        events[0].payload["no_objections_justification"]
        == "No unresolved material objections remain."
    )
    assert events[0].payload["id_mapping"] == []


def test_unpack_is_not_idempotent_and_mints_new_ids_on_replay(tmp_path: Path) -> None:
    case = create_case("unpack-non-idempotent", cases_root=tmp_path)
    evidence_batch = EvidenceBatch(
        task_id="T-004",
        question="Replay probe",
        records=[_evidence("E-777")],
        search_notes="Single-source replay test.",
    )
    objection_batch = ObjectionBatch(
        mode=ObjectionMode.STANDARD,
        objections=[_objection("O-777")],
    )

    first_evidence = unpack_evidence_batch(case, evidence_batch)
    second_evidence = unpack_evidence_batch(case, evidence_batch)
    first_objection = unpack_objection_batch(case, objection_batch)
    second_objection = unpack_objection_batch(case, objection_batch)

    assert [item.evidence_id for item in first_evidence] == ["E-001"]
    assert [item.evidence_id for item in second_evidence] == ["E-002"]
    assert [item.objection_id for item in first_objection] == ["O-001"]
    assert [item.objection_id for item in second_objection] == ["O-002"]


def test_case_write_artifact_rejects_batch_transport_envelopes(tmp_path: Path) -> None:
    case = create_case("write-batch-rejected", cases_root=tmp_path)
    evidence_batch = EvidenceBatch(
        task_id="T-005",
        question="Should not write directly",
        records=[_evidence("E-888")],
        search_notes="Transport envelope test.",
    )
    objection_batch = ObjectionBatch(
        mode=ObjectionMode.STANDARD,
        objections=[_objection("O-888")],
    )

    with pytest.raises(
        TypeError,
        match=r"EvidenceBatch cannot be written directly.*transport envelopes",
    ):
        case.write_artifact(evidence_batch)
    with pytest.raises(
        TypeError, match=r"ObjectionBatch cannot be written directly.*transport envelopes"
    ):
        case.write_artifact(objection_batch)
