from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import EvidenceBatch
from orchestrator.normalize import dump_normalized_batch, normalize_evidence_batch


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
