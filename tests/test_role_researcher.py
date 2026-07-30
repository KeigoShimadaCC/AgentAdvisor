from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from orchestrator.artifacts import AuditEvent, EvidenceBatch, EvidenceRecord
from orchestrator.backend import CursorCLIBackend
from orchestrator.case_store import create_case
from orchestrator.invoke_role import InvokeTask, invoke
from orchestrator.normalize import normalize_evidence_batch, write_quarantine_file


def _fixture_payload(filename: str) -> dict[str, Any]:
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "roles" / "researcher" / filename
    payload = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_replay_records_are_validated_or_quarantined_before_ledger_write(tmp_path: Path) -> None:
    case = create_case("researcher-replay", cases_root=tmp_path / "cases")
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    payload = _fixture_payload("replay_batch.yaml")
    records = payload.get("records")
    assert isinstance(records, list)
    normalized = normalize_evidence_batch(
        records,
        question="What was Japan's 2020 census population?",
        stale_after_days=3650,
    )
    quarantine_path = write_quarantine_file(workspace, normalized.quarantined)

    for record in normalized.accepted:
        case.write_artifact(record)

    ledger_records = case.list_artifacts(EvidenceRecord)
    assert len(normalized.accepted) + len(normalized.quarantined) == len(records)
    assert len(ledger_records) == len(normalized.accepted)
    assert {record.evidence_id for record in ledger_records} == {
        record.evidence_id for record in normalized.accepted
    }
    assert quarantine_path is not None
    quarantine_text = quarantine_path.read_text(encoding="utf-8")
    assert "schema_validation_error" in quarantine_text


def test_no_evidence_found_batch_is_valid_and_normalizes_as_noop(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    evidence_batch = EvidenceBatch(
        task_id="T-012-empty",
        question="What population did Japan's 1900 census record?",
        records=[],
        no_evidence_found=True,
        search_notes=(
            "Queries tried: Japanese census 1900 official archive, "
            "Statistics Bureau historical tables. "
            "Rejected secondary blogs due to no primary citation."
        ),
    )

    normalized = normalize_evidence_batch(evidence_batch, stale_after_days=3650)
    quarantine_path = write_quarantine_file(workspace, normalized.quarantined)

    assert normalized.accepted == tuple()
    assert normalized.quarantined == tuple()
    assert normalized.contradiction_links == tuple()
    assert normalized.stale_evidence_ids == tuple()
    assert quarantine_path is None


def test_researcher_batch_rejects_more_than_eight_records() -> None:
    records: list[dict[str, Any]] = []
    for index in range(1, 10):
        records.append(
            {
                "evidence_id": f"E-{index:03d}",
                "claim": f"Claim {index}",
                "source_title": f"Source {index}",
                "publisher": "Publisher",
                "source_url": f"https://example.com/{index}",
                "source_type": "official_statistic",
                "publication_date": date(2024, 1, 1).isoformat(),
                "retrieval_date": date(2026, 7, 31).isoformat(),
                "excerpt": f"Excerpt {index}",
                "reliability": "high",
                "directness": "high",
                "independence_group": "group",
                "limitations": ["Test limitation."],
                "retrieved_by": "researcher",
            }
        )

    with pytest.raises(ValidationError):
        EvidenceBatch.model_validate(
            {
                "task_id": "T-012-cap",
                "question": "Cap test question",
                "records": records,
                "no_evidence_found": False,
                "search_notes": "Cap test.",
            }
        )


@pytest.mark.live
def test_researcher_live_2020_japan_census_population(tmp_path: Path) -> None:
    case = create_case("researcher-live", cases_root=tmp_path / "cases")
    task = InvokeTask(
        task_id="T-012-live",
        assignment=(
            "Question: What population did Japan's 2020 national census record?\n"
            "Use an official primary source and provide an EvidenceBatch with up to 8 records.\n"
            "Include a direct excerpt with the census value and publication context.\n"
        ),
        output_artifact_type="evidence_batch",
    )

    artifact = invoke(case, "researcher", task, backend=CursorCLIBackend())

    assert isinstance(artifact, EvidenceBatch)
    assert artifact.question.strip()
    assert artifact.search_notes.strip()
    assert len(artifact.records) <= 8
    assert artifact.records
    assert not artifact.no_evidence_found

    for record in artifact.records:
        assert record.source_url.startswith("http")
        assert record.excerpt.strip()
        assert record.independence_group.strip()
        assert record.publication_date <= record.retrieval_date
    assert any("stat.go.jp" in record.source_url for record in artifact.records)

    lines = (case.root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    events = [AuditEvent.model_validate_json(line) for line in lines]
    attempts = [
        event
        for event in events
        if event.actor == "researcher"
        and event.event_type == "role_invocation_attempt"
        and event.payload.get("task_id") == "T-012-live"
    ]
    assert 1 <= len(attempts) <= 2

    # Guard against malformed audit payload serialization.
    _ = json.dumps([event.model_dump(mode="json") for event in attempts], sort_keys=True)
