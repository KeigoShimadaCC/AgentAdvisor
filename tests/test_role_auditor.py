from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel

from orchestrator.artifacts import (
    AssumptionRecord,
    AuditEvent,
    AuditFinding,
    AuditFindingType,
    DecisionSpec,
    EvidenceRecord,
    ObjectionRecord,
    TaskRecord,
    TaskRole,
)
from orchestrator.artifacts.yaml_io import load_model_from_yaml_text
from orchestrator.backend import CursorCLIBackend, ResultStatus, RoleResult, StubBackend
from orchestrator.case_store import Case, create_case
from orchestrator.invoke_role import (
    InvokeTask,
    RoleInvocationFailed,
    clear_cross_field_validation_hooks,
    invoke_read_only,
    register_cross_field_validation_hook,
)
from orchestrator.roles_config import load_role_config

FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures" / "roles" / "auditor"


def _ok_result(result_text: str) -> RoleResult:
    return RoleResult(
        status=ResultStatus.OK,
        result_text=result_text,
        session_id="sess-auditor",
        request_id="req-auditor",
        duration_ms=20,
        usage=None,
        raw_stdout="{}",
        raw_stderr="",
        cli_version="cursor-agent test",
    )


def _build_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Case:
    case = create_case("auditor", cases_root=tmp_path / "cases-root")
    monkeypatch.setenv("AGENTADVISOR_RUNTIME_ROOT", str(tmp_path / "runtime-root"))
    return case


def _load_fixture_mapping(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError(f"Fixture must be a mapping: {path}")
    return cast(dict[str, Any], loaded)


def _require_mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise TypeError(f"{key} must be a mapping.")
    return cast(dict[str, Any], value)


def _require_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise TypeError(f"{key} must be a list.")
    for entry in value:
        if not isinstance(entry, dict):
            raise TypeError(f"{key} entries must be mappings.")
    return cast(list[dict[str, Any]], value)


def _seed_drift_context(case: Case) -> None:
    payload = _load_fixture_mapping(FIXTURES_ROOT / "drift_context.yaml")
    case.write_artifact(DecisionSpec.model_validate(_require_mapping(payload, "decision_spec")))
    for task_payload in _require_list(payload, "tasks"):
        case.write_artifact(TaskRecord.model_validate(task_payload))
    for evidence_payload in _require_list(payload, "evidence_records"):
        case.write_artifact(EvidenceRecord.model_validate(evidence_payload))
    for assumption_payload in _require_list(payload, "assumptions"):
        case.write_artifact(AssumptionRecord.model_validate(assumption_payload))
    for objection_payload in _require_list(payload, "objections"):
        case.write_artifact(ObjectionRecord.model_validate(objection_payload))

    task_graph = payload.get("task_graph")
    artifact_index = payload.get("artifact_index")
    budget_snapshot = payload.get("budget_snapshot")
    if task_graph is not None:
        (case.root / "shared" / "task_graph.yaml").write_text(
            yaml.safe_dump(task_graph, sort_keys=True),
            encoding="utf-8",
        )
    if artifact_index is not None:
        (case.root / "outputs" / "artifact_index.yaml").write_text(
            yaml.safe_dump(artifact_index, sort_keys=True),
            encoding="utf-8",
        )
    if budget_snapshot is not None:
        (case.root / "outputs" / "budget_snapshot.yaml").write_text(
            yaml.safe_dump(budget_snapshot, sort_keys=True),
            encoding="utf-8",
        )


def _auditor_task(task_id: str, mode: str) -> InvokeTask:
    return InvokeTask(
        task_id=task_id,
        assignment=(
            "Audit this checkpoint for process drift, duplication, mandate violations, "
            "unsupported claims, and Stage 9 stop-input readiness."
        ),
        output_artifact_type="audit_finding",
        mode=mode,
    )


def _attempt_events(case: Case, task_id: str) -> list[AuditEvent]:
    lines = (case.root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    events = [AuditEvent.model_validate_json(line) for line in lines]
    return [
        event
        for event in events
        if event.actor == "auditor"
        and event.event_type == "role_invocation_attempt"
        and event.payload.get("task_id") == task_id
    ]


def _validate_audit_target_ids_exist(artifact: BaseModel, case: Case) -> None:
    if not isinstance(artifact, AuditFinding):
        raise TypeError("Expected AuditFinding artifact.")

    valid_ids: set[str] = {case.root.name}
    valid_ids.update(record.task_id for record in case.list_artifacts(TaskRecord))
    valid_ids.update(record.evidence_id for record in case.list_artifacts(EvidenceRecord))
    valid_ids.update(record.assumption_id for record in case.list_artifacts(AssumptionRecord))
    valid_ids.update(record.objection_id for record in case.list_artifacts(ObjectionRecord))

    for issue in artifact.findings:
        for target_id in issue.target_ids:
            if target_id not in valid_ids:
                raise ValueError(f"unknown target_id: {target_id}")


def test_auditor_role_config_loads_expected_permissions_and_output_type() -> None:
    config = load_role_config(TaskRole.AUDITOR)

    assert config.default_model == "composer-2.5"
    assert config.read_only is True
    assert config.permission_profile.allow_shell is False
    assert config.output_artifact_type == "audit_finding"
    assert "decision_spec" in config.projection_include
    assert "task_graph" in config.projection_include
    assert "artifact_index" in config.projection_include
    assert "budget_snapshot" in config.projection_include


def test_fixture_replay_flags_planted_drift_and_collects_stdout_yaml_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    _seed_drift_context(case)
    yaml_text = (FIXTURES_ROOT / "replay.audit_finding.yaml").read_text(encoding="utf-8")
    backend = StubBackend([_ok_result(result_text=f"```yaml\n{yaml_text}```")])

    register_cross_field_validation_hook("audit_finding", _validate_audit_target_ids_exist)
    try:
        artifact = invoke_read_only(
            case,
            "auditor",
            _auditor_task("T-860", "post_planning"),
            backend=backend,
        )
    finally:
        clear_cross_field_validation_hooks("audit_finding")

    assert isinstance(artifact, AuditFinding)
    finding_types = {finding.finding_type for finding in artifact.findings}
    assert AuditFindingType.DUPLICATED_WORK in finding_types
    assert AuditFindingType.IRRELEVANT_TASK in finding_types
    assert artifact.stop_input.open_critical_evidence_gaps is True
    assert artifact.stop_input.unresolved_material_objections is True
    assert artifact.stop_input.recommendation_stable is False
    assert artifact.stop_input.expected_value_of_more_research_low is False

    assert len(backend.invocations) == 1
    assert backend.invocations[0].read_only is True
    archived_workspace = case.root / "agents" / "auditor--T-860"
    assert archived_workspace.exists()
    assert "mode: post_planning" in (archived_workspace / "task.yaml").read_text(encoding="utf-8")
    assert list((archived_workspace / "outputs").iterdir()) == []


def test_fixture_with_nonexistent_target_ids_fails_cross_field_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    _seed_drift_context(case)
    yaml_text = (FIXTURES_ROOT / "invalid_targets.audit_finding.yaml").read_text(encoding="utf-8")
    backend = StubBackend(
        [
            _ok_result(result_text=f"```yaml\n{yaml_text}```"),
            _ok_result(result_text=f"```yaml\n{yaml_text}```"),
            _ok_result(result_text=f"```yaml\n{yaml_text}```"),
        ]
    )

    register_cross_field_validation_hook("audit_finding", _validate_audit_target_ids_exist)
    try:
        with pytest.raises(RoleInvocationFailed, match="unknown target_id:"):
            invoke_read_only(
                case,
                "auditor",
                _auditor_task("T-861", "post_challenge"),
                backend=backend,
            )
    finally:
        clear_cross_field_validation_hooks("audit_finding")

    assert len(backend.invocations) == 3


@pytest.mark.live
def test_auditor_live_mini_run_returns_schema_valid_artifact_within_two_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    _seed_drift_context(case)
    wrapped_patterns: list[bool] = []

    from orchestrator import invoke_role as invoke_role_module

    extract_yaml_block = invoke_role_module._extract_yaml_block

    def _recording_extract_yaml_block(result_text: str) -> str:
        wrapped = (
            re.search(
                r"```(?:yaml|yml)\\s*\\n(.*?)```",
                result_text,
                flags=re.DOTALL | re.IGNORECASE,
            )
            is not None
        )
        wrapped_patterns.append(wrapped)
        return extract_yaml_block(result_text)

    monkeypatch.setattr(
        "orchestrator.invoke_role._extract_yaml_block",
        _recording_extract_yaml_block,
    )

    register_cross_field_validation_hook("audit_finding", _validate_audit_target_ids_exist)
    try:
        artifact = invoke_read_only(
            case,
            "auditor",
            _auditor_task("T-862", "post_wave"),
            backend=CursorCLIBackend(),
        )
    finally:
        clear_cross_field_validation_hooks("audit_finding")

    assert isinstance(artifact, AuditFinding)
    serialized = yaml.safe_dump(artifact.model_dump(mode="json"), sort_keys=True)
    reloaded = load_model_from_yaml_text(AuditFinding, serialized)
    assert isinstance(reloaded, AuditFinding)

    attempts = _attempt_events(case, "T-862")
    assert 1 <= len(attempts) <= 2
    assert attempts[-1].payload.get("status") == "ok"
    assert wrapped_patterns
    print(f"AUDITOR_LIVE_ATTEMPTS={len(attempts)}")
    print(f"AUDITOR_LIVE_YAML_FENCED={all(wrapped_patterns)}")

    archived_workspace = case.root / "agents" / "auditor--T-862"
    assert archived_workspace.exists()
    assert "mode: post_wave" in (archived_workspace / "task.yaml").read_text(encoding="utf-8")
