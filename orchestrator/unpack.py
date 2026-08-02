from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import (
    AssumptionBatch,
    AssumptionRecord,
    AuditEvent,
    EvidenceBatch,
    EvidenceRecord,
    ObjectionBatch,
    ObjectionRecord,
)
from orchestrator.case_store import Case, atomic_write_text

# ── unpack marker helpers ────────────────────────────────────────────────────


def _marker_path(case: Case, task_id: str) -> Path:
    return case.root / "shared" / "unpack_markers" / f"{task_id}.yaml"


def _read_marker(case: Case, task_id: str) -> dict[str, Any] | None:
    path = _marker_path(case, task_id)
    if not path.exists():
        return None
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return None
    return loaded


def _write_marker(case: Case, task_id: str, artifact_type: str, record_ids: list[str]) -> None:
    payload: dict[str, Any] = {
        "task_id": task_id,
        "artifact_type": artifact_type,
        "record_ids": record_ids,
    }
    atomic_write_text(_marker_path(case, task_id), yaml.safe_dump(payload, sort_keys=True))


# ── unpack functions ─────────────────────────────────────────────────────────


def unpack_evidence_batch(case: Case, batch: EvidenceBatch) -> list[EvidenceRecord]:
    """Persist an EvidenceBatch by unpacking it into canonical EvidenceRecord artifacts.

    This function intentionally does not run evidence normalization. Callers should normalize
    a batch first (see `orchestrator.normalize.normalize_evidence_batch`) and pass the surviving
    records here for persistence.

    Idempotency: a marker at ``shared/unpack_markers/<task_id>.yaml`` records the canonical
    ids minted on the first unpack.  Re-unpacking the same ``task_id`` is a no-op that returns
    the previously recorded records and audits ``unpack_skipped_duplicate``.
    """
    marker = _read_marker(case, batch.task_id)
    if marker is not None:
        record_ids: list[str] = list(marker.get("record_ids", []))
        existing = [case.read_artifact(EvidenceRecord, rid) for rid in record_ids]
        case.audit(
            AuditEvent(
                ts=datetime.now(UTC),
                actor="orchestrator",
                event_type="unpack_skipped_duplicate",
                payload={
                    "task_id": batch.task_id,
                    "artifact_type": "evidence_batch",
                    "record_ids": record_ids,
                },
            )
        )
        return existing

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

    _write_marker(
        case,
        batch.task_id,
        "evidence_batch",
        [record.evidence_id for record in unpacked],
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


def unpack_assumption_batch(
    case: Case, batch: AssumptionBatch, *, task_id: str | None = None
) -> list[AssumptionRecord]:
    """Persist an AssumptionBatch by unpacking it into canonical AssumptionRecord artifacts.

    Evidence references that do not resolve on the blackboard are dropped rather than
    persisted, so the ledger never carries a citation that points at nothing.

    Idempotency: when ``task_id`` is provided, a marker at
    ``shared/unpack_markers/<task_id>.yaml`` records the canonical ids minted on the first
    unpack.  Re-unpacking the same ``task_id`` is a no-op that returns the previously
    recorded records and audits ``unpack_skipped_duplicate``.
    """
    if task_id is not None:
        marker = _read_marker(case, task_id)
        if marker is not None:
            record_ids = list(marker.get("record_ids", []))
            existing = [case.read_artifact(AssumptionRecord, rid) for rid in record_ids]
            case.audit(
                AuditEvent(
                    ts=datetime.now(UTC),
                    actor="orchestrator",
                    event_type="unpack_skipped_duplicate",
                    payload={
                        "task_id": task_id,
                        "artifact_type": "assumption_batch",
                        "record_ids": record_ids,
                    },
                )
            )
            return existing

    known_evidence_ids = {record.evidence_id for record in case.list_artifacts(EvidenceRecord)}
    unpacked: list[AssumptionRecord] = []
    id_mapping: list[dict[str, str]] = []
    dropped_references: list[str] = []

    for record in batch.records:
        canonical_id = case.next_id("A-")
        evidence_for = [
            evidence_id for evidence_id in record.evidence_for if evidence_id in known_evidence_ids
        ]
        evidence_against = [
            evidence_id
            for evidence_id in record.evidence_against
            if evidence_id in known_evidence_ids
        ]
        dropped_references.extend(
            sorted((set(record.evidence_for) | set(record.evidence_against)) - known_evidence_ids)
        )
        rewritten = record.model_copy(
            update={
                "assumption_id": canonical_id,
                "evidence_for": evidence_for,
                "evidence_against": evidence_against,
            }
        )
        case.write_artifact(rewritten)
        unpacked.append(rewritten)
        id_mapping.append(
            {
                "original_assumption_id": record.assumption_id,
                "canonical_assumption_id": canonical_id,
            }
        )

    if task_id is not None:
        _write_marker(
            case,
            task_id,
            "assumption_batch",
            [record.assumption_id for record in unpacked],
        )

    case.audit(
        AuditEvent(
            ts=datetime.now(UTC),
            actor="orchestrator",
            event_type="assumption_batch_unpacked",
            payload={
                "source_scope": batch.source_scope,
                "record_count": len(unpacked),
                "no_assumptions_found": batch.no_assumptions_found,
                "extraction_notes": batch.extraction_notes,
                "dropped_evidence_references": sorted(set(dropped_references)),
                "id_mapping": id_mapping,
            },
        )
    )
    return unpacked


def unpack_objection_batch(
    case: Case, batch: ObjectionBatch, *, task_id: str | None = None
) -> list[ObjectionRecord]:
    """Persist an ObjectionBatch by unpacking it into canonical ObjectionRecord artifacts.

    Idempotency: when ``task_id`` is provided, a marker at
    ``shared/unpack_markers/<task_id>.yaml`` records the canonical ids minted on the first
    unpack.  Re-unpacking the same ``task_id`` is a no-op that returns the previously
    recorded records and audits ``unpack_skipped_duplicate``.
    """
    if task_id is not None:
        marker = _read_marker(case, task_id)
        if marker is not None:
            record_ids = list(marker.get("record_ids", []))
            existing = [case.read_artifact(ObjectionRecord, rid) for rid in record_ids]
            case.audit(
                AuditEvent(
                    ts=datetime.now(UTC),
                    actor="orchestrator",
                    event_type="unpack_skipped_duplicate",
                    payload={
                        "task_id": task_id,
                        "artifact_type": "objection_batch",
                        "record_ids": record_ids,
                    },
                )
            )
            return existing

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

    if task_id is not None:
        _write_marker(
            case,
            task_id,
            "objection_batch",
            [record.objection_id for record in unpacked],
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
