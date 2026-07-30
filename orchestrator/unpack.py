from __future__ import annotations

from datetime import UTC, datetime

from orchestrator.artifacts import (
    AuditEvent,
    EvidenceBatch,
    EvidenceRecord,
    ObjectionBatch,
    ObjectionRecord,
)
from orchestrator.case_store import Case


def unpack_evidence_batch(case: Case, batch: EvidenceBatch) -> list[EvidenceRecord]:
    """Persist an EvidenceBatch by unpacking it into canonical EvidenceRecord artifacts.

    This function intentionally does not run evidence normalization. Callers should normalize
    a batch first (see `orchestrator.normalize.normalize_evidence_batch`) and pass the surviving
    records here for persistence.

    Idempotency: not idempotent. Re-running unpack on the same batch mints fresh canonical IDs.
    """

    unpacked: list[EvidenceRecord] = []
    id_mapping: list[dict[str, str]] = []
    for record in batch.records:
        canonical_id = case.next_id("E-")
        rewritten = record.model_copy(update={"evidence_id": canonical_id})
        case.write_artifact(rewritten)
        unpacked.append(rewritten)
        id_mapping.append(
            {
                "original_evidence_id": record.evidence_id,
                "canonical_evidence_id": canonical_id,
            }
        )

    case.audit(
        AuditEvent(
            ts=datetime.now(UTC),
            actor="orchestrator",
            event_type="evidence_batch_unpacked",
            payload={
                "task_id": batch.task_id,
                "question": batch.question,
                "record_count": len(unpacked),
                "no_evidence_found": batch.no_evidence_found,
                "search_notes": batch.search_notes,
                "id_mapping": id_mapping,
            },
        )
    )
    return unpacked


def unpack_objection_batch(case: Case, batch: ObjectionBatch) -> list[ObjectionRecord]:
    """Persist an ObjectionBatch by unpacking it into canonical ObjectionRecord artifacts.

    Idempotency: not idempotent. Re-running unpack on the same batch mints fresh canonical IDs.
    """

    unpacked: list[ObjectionRecord] = []
    id_mapping: list[dict[str, str]] = []
    for objection in batch.objections:
        canonical_id = case.next_id("O-")
        rewritten = objection.model_copy(update={"objection_id": canonical_id})
        case.write_artifact(rewritten)
        unpacked.append(rewritten)
        id_mapping.append(
            {
                "original_objection_id": objection.objection_id,
                "canonical_objection_id": canonical_id,
            }
        )

    case.audit(
        AuditEvent(
            ts=datetime.now(UTC),
            actor="orchestrator",
            event_type="objection_batch_unpacked",
            payload={
                "mode": batch.mode.value,
                "objection_count": len(unpacked),
                "no_objections_justification": batch.no_objections_justification,
                "id_mapping": id_mapping,
            },
        )
    )
    return unpacked
