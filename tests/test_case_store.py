from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

import pytest

from orchestrator.artifacts import AuditEvent, EvidenceRecord, Level, SourceType
from orchestrator.case_store import create_case, runtime_root


def _build_evidence(evidence_id: str) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        claim="Revenue grew year-over-year",
        source_title="Annual Report",
        publisher="AAA Corp",
        source_url="https://example.com/report",
        source_type=SourceType.REPUTABLE_SECONDARY,
        publication_date=date(2026, 1, 1),
        retrieval_date=date(2026, 1, 2),
        excerpt="Revenue grew by 18%.",
        reliability=Level.HIGH,
        directness=Level.MEDIUM,
        independence_group="aaa-report",
        limitations=["Company-defined segment boundary"],
        retrieved_by="researcher-market",
    )


def test_create_case_allocates_monotonic_ids_and_expected_layout(tmp_path: Path) -> None:
    case_1 = create_case("alpha", cases_root=tmp_path)
    case_2 = create_case("beta", cases_root=tmp_path)

    assert case_1.root.name == "case-001-alpha"
    assert case_2.root.name == "case-002-beta"

    expected_paths = [
        case_1.root / "shared",
        case_1.root / "shared" / "evidence",
        case_1.root / "shared" / "assumptions",
        case_1.root / "shared" / "objections",
        case_1.root / "shared" / "task_graph.yaml",
        case_1.root / "agents",
        case_1.root / "analysis",
        case_1.root / "outputs",
        case_1.root / "state.yaml",
        case_1.root / "audit.jsonl",
    ]
    for expected_path in expected_paths:
        assert expected_path.exists()

    assert not (case_1.root / "shared" / "decision_spec.yaml").exists()


def test_write_artifact_is_atomic_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = create_case("atomic", cases_root=tmp_path)
    evidence = _build_evidence("E-001")

    def _raise_replace(_: os.PathLike[str] | str, __: os.PathLike[str] | str) -> None:
        raise RuntimeError("replace failed")

    monkeypatch.setattr("orchestrator.case_store.os.replace", _raise_replace)

    with pytest.raises(RuntimeError, match="replace failed"):
        case.write_artifact(evidence)

    final_path = case.root / "shared" / "evidence" / "E-001.yaml"
    assert not final_path.exists()
    assert list(final_path.parent.glob(f".{final_path.name}.tmp-*.tmp")) == []


def test_next_id_is_unique_and_monotonic_per_prefix_under_threads(tmp_path: Path) -> None:
    case = create_case("ids", cases_root=tmp_path)

    for prefix in ("E-", "A-", "T-", "O-"):
        with ThreadPoolExecutor(max_workers=16) as executor:
            ids = list(executor.map(case.next_id, [prefix] * 100))

        assert len(ids) == 100
        assert len(set(ids)) == 100
        numeric_ids = sorted(int(value.split("-")[1]) for value in ids)
        assert numeric_ids[0] == 1
        assert numeric_ids[-1] == 100


def test_audit_appends_ordered_jsonl_and_round_trips_models(tmp_path: Path) -> None:
    case = create_case("audit", cases_root=tmp_path)
    events = [
        AuditEvent(ts=datetime(2026, 1, 1, 0, 0, 0), actor="planner", event_type="task_planned"),
        AuditEvent(ts=datetime(2026, 1, 1, 0, 0, 1), actor="director", event_type="thesis_updated"),
        AuditEvent(ts=datetime(2026, 1, 1, 0, 0, 2), actor="auditor", event_type="gate_checked"),
    ]

    for event in events:
        case.audit(event)

    lines = (case.root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(events)

    loaded = [AuditEvent.model_validate_json(line) for line in lines]
    assert loaded == events


def test_write_and_read_artifact_round_trip(tmp_path: Path) -> None:
    case = create_case("roundtrip", cases_root=tmp_path)
    evidence = _build_evidence("E-007")

    written_path = case.write_artifact(evidence)
    assert written_path == case.root / "shared" / "evidence" / "E-007.yaml"

    loaded = case.read_artifact(EvidenceRecord, "E-007")
    assert loaded == evidence
    assert case.list_artifacts(EvidenceRecord) == [evidence]


def test_runtime_root_is_outside_repo_and_respects_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AGENTADVISOR_RUNTIME_ROOT", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    default_root = runtime_root().resolve()

    repo_root = Path(__file__).resolve().parents[1]
    assert not default_root.is_relative_to(repo_root.resolve())

    configured = tmp_path / "custom-runtime-root"
    monkeypatch.setenv("AGENTADVISOR_RUNTIME_ROOT", str(configured))
    configured_root = runtime_root()
    assert configured_root == configured
    assert configured_root.exists()


def test_archive_agent_workspace_copies_nested_tree(tmp_path: Path) -> None:
    case = create_case("archive", cases_root=tmp_path)
    workspace = tmp_path / "runtime-workspace"
    nested = workspace / "nested" / "deeper"
    nested.mkdir(parents=True)
    (workspace / "top.txt").write_text("top", encoding="utf-8")
    (nested / "artifact.json").write_text('{"ok": true}', encoding="utf-8")

    destination = case.archive_agent_workspace("researcher", "T-009", workspace)

    assert destination == case.root / "agents" / "researcher--T-009"
    assert (destination / "top.txt").read_text(encoding="utf-8") == "top"
    artifact_text = (destination / "nested" / "deeper" / "artifact.json").read_text(
        encoding="utf-8"
    )
    assert artifact_text == '{"ok": true}'
    assert workspace.exists()
