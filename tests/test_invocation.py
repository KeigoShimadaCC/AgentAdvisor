from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from orchestrator.artifacts import (
    AssumptionRecord,
    AuditEvent,
    DecisionSpec,
    EvidenceRecord,
    Level,
    ProbabilityEstimate,
    ProbabilityMethod,
    Reversibility,
    RiskTolerance,
    SourceType,
    TaskRole,
)
from orchestrator.artifacts.common import AssumptionStatus, AssumptionType, Depth
from orchestrator.artifacts.yaml_io import dump_model_to_yaml_text
from orchestrator.backend import (
    CursorCLIBackend,
    ResultStatus,
    RoleInvocation,
    RoleResult,
    StubBackend,
    TokenUsage,
)
from orchestrator.case_store import create_case
from orchestrator.invoke_role import (
    InvokeTask,
    RoleInvocationFailed,
    clear_cross_field_validation_hooks,
    invoke,
    invoke_read_only,
    register_cross_field_validation_hook,
)
from orchestrator.isolation import WorkspaceNotIsolated, assert_isolated
from orchestrator.projection import ProjectedArtifact, project
from orchestrator.roles_config import PermissionProfile, RoleConfig, family
from orchestrator.workspace import WorkspaceTask, build_workspace


def _usage() -> TokenUsage:
    return TokenUsage(input_tokens=10, output_tokens=4, total_tokens=14)


def _ok_result(result_text: str = "ok") -> RoleResult:
    return RoleResult(
        status=ResultStatus.OK,
        result_text=result_text,
        session_id="sess-1",
        request_id="req-1",
        duration_ms=25,
        usage=_usage(),
        raw_stdout="{}",
        raw_stderr="",
        cli_version="cursor-agent test",
    )


def _agent_error_result() -> RoleResult:
    return RoleResult(
        status=ResultStatus.AGENT_ERROR,
        result_text=None,
        session_id="sess-err",
        request_id="req-err",
        duration_ms=25,
        usage=_usage(),
        raw_stdout='{"is_error": true}',
        raw_stderr="",
        cli_version="droid test",
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _build_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cases_root = tmp_path / "cases-root"
    case = create_case("invoke", cases_root=cases_root)
    runtime = tmp_path / "runtime-root"
    monkeypatch.setenv("AGENTADVISOR_RUNTIME_ROOT", str(runtime))
    return case, runtime


def _role_config(
    tmp_path: Path, *, allow_shell: bool = False, read_only: bool = False
) -> RoleConfig:
    role_md = tmp_path / "researcher.md"
    role_md.write_text("Role instructions for researcher.\n", encoding="utf-8")
    return RoleConfig(
        role=TaskRole.RESEARCHER,
        role_md_path=role_md,
        default_model="composer-2.5",
        escalation_model="gpt-5.2",
        read_only=read_only,
        permission_profile=PermissionProfile(allow_shell=allow_shell),
        projection_include=tuple(),
        output_artifact_type="evidence_record",
        model_tier="low",
    )


def _task(task_id: str = "T-001") -> InvokeTask:
    return InvokeTask(
        task_id=task_id,
        assignment="Find one high-quality evidence artifact.",
        output_artifact_type="evidence_record",
    )


def _evidence(evidence_id: str = "E-001") -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        claim="Revenue grew 18% year-over-year.",
        source_title="Annual Report",
        publisher="AAA Corp",
        source_url="https://example.com/report",
        source_type=SourceType.REPUTABLE_SECONDARY,
        publication_date=date(2026, 1, 1),
        retrieval_date=date(2026, 1, 2),
        excerpt="Revenue grew by 18%.",
        reliability=Level.HIGH,
        directness=Level.MEDIUM,
        independence_group="aaa-2026-report",
        limitations=["Company-defined segment boundary"],
        retrieved_by="researcher",
    )


def _write_output(artifact: EvidenceRecord):
    text = dump_model_to_yaml_text(artifact)

    def _side_effect(invocation: RoleInvocation) -> None:
        output_path = invocation.workspace / "outputs" / "evidence_record.yaml"
        output_path.write_text(text, encoding="utf-8")

    return _side_effect


def _write_invalid_output(invocation: RoleInvocation) -> None:
    (invocation.workspace / "outputs" / "evidence_record.yaml").write_text(
        "schema_version: 1\nclaim: missing required fields\n",
        encoding="utf-8",
    )


def _audit_lines(case_root: Path) -> list[AuditEvent]:
    lines = (case_root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    return [AuditEvent.model_validate_json(line) for line in lines]


def test_happy_path_valid_artifact_first_try(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case, runtime_root = _build_case(tmp_path, monkeypatch)
    config = _role_config(tmp_path)
    monkeypatch.setattr(
        "orchestrator.invoke_role.load_role_config", lambda _role, _variant=None: config
    )
    backend = StubBackend([_ok_result()], side_effects=[_write_output(_evidence())])

    artifact = invoke(case, "researcher", _task(), backend=backend)

    assert isinstance(artifact, EvidenceRecord)
    archived = case.root / "agents" / "researcher--T-001"
    assert archived.exists()
    assert not (runtime_root / case.root.name / "researcher--T-001").exists()
    assert len(backend.invocations) == 1
    events = _audit_lines(case.root)
    assert len(events) == 1
    assert events[0].model == "composer-2.5"
    assert events[0].usage is not None
    assert events[0].usage.total_tokens == 14


def test_invalid_output_retries_same_model_and_applies_feedback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case, _ = _build_case(tmp_path, monkeypatch)
    config = _role_config(tmp_path)
    monkeypatch.setattr(
        "orchestrator.invoke_role.load_role_config", lambda _role, _variant=None: config
    )
    backend = StubBackend(
        [_ok_result(), _ok_result()],
        side_effects=[_write_invalid_output, _write_output(_evidence())],
    )

    artifact = invoke(case, "researcher", _task("T-100"), backend=backend)

    assert isinstance(artifact, EvidenceRecord)
    assert [inv.model for inv in backend.invocations] == ["composer-2.5", "composer-2.5"]
    attempt_archive = case.root / "agents" / "researcher--T-100--attempt-1"
    assert attempt_archive.exists()
    final_task_yaml = (case.root / "agents" / "researcher--T-100" / "task.yaml").read_text(
        encoding="utf-8"
    )
    assert "feedback:" in final_task_yaml


def test_retry_then_escalate_changes_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case, _ = _build_case(tmp_path, monkeypatch)
    config = _role_config(tmp_path)
    monkeypatch.setattr(
        "orchestrator.invoke_role.load_role_config", lambda _role, _variant=None: config
    )
    backend = StubBackend(
        [_ok_result(), _ok_result(), _ok_result()],
        side_effects=[_write_invalid_output, _write_invalid_output, _write_output(_evidence())],
    )

    artifact = invoke(case, "researcher", _task("T-200"), backend=backend)

    assert isinstance(artifact, EvidenceRecord)
    assert [inv.model for inv in backend.invocations] == ["composer-2.5", "composer-2.5", "gpt-5.2"]


def test_escalation_fail_raises_and_archives_all_attempts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case, runtime_root = _build_case(tmp_path, monkeypatch)
    config = _role_config(tmp_path)
    monkeypatch.setattr(
        "orchestrator.invoke_role.load_role_config", lambda _role, _variant=None: config
    )
    backend = StubBackend(
        [_ok_result(), _ok_result(), _ok_result()],
        side_effects=[_write_invalid_output, _write_invalid_output, _write_invalid_output],
    )

    with pytest.raises(RoleInvocationFailed):
        invoke(case, "researcher", _task("T-300"), backend=backend)

    for attempt in (1, 2, 3):
        assert (case.root / "agents" / f"researcher--T-300--attempt-{attempt}").exists()
    assert not (runtime_root / case.root.name / "researcher--T-300").exists()
    events = _audit_lines(case.root)
    assert len(events) == 3
    assert all(event.model is not None for event in events)
    assert all(event.usage is not None for event in events)


def test_agent_error_with_valid_output_file_is_recovered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Droid can write a valid artifact, then set is_error=true on
    # post-completion cleanup. The file, not the CLI flag, is the truth: the
    # first attempt must be accepted without escalating.
    case, runtime_root = _build_case(tmp_path, monkeypatch)
    config = _role_config(tmp_path)
    monkeypatch.setattr(
        "orchestrator.invoke_role.load_role_config", lambda _role, _variant=None: config
    )
    backend = StubBackend(
        [_agent_error_result()],
        side_effects=[_write_output(_evidence())],
    )

    artifact = invoke(case, "researcher", _task("T-901"), backend=backend)

    assert isinstance(artifact, EvidenceRecord)
    assert len(backend.invocations) == 1
    assert not (case.root / "agents" / "researcher--T-901--attempt-1").exists()
    assert (case.root / "agents" / "researcher--T-901").exists()
    events = _audit_lines(case.root)
    assert len(events) == 1
    assert events[0].payload["status"] == "ok"
    assert events[0].payload["backend_status"] == ResultStatus.AGENT_ERROR.value
    assert "recovered" in (events[0].payload["detail"] or "")


def test_agent_error_without_output_file_still_fails_and_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An agent_error with no artifact left behind is a real failure and must
    # still walk the escalation ladder.
    case, _ = _build_case(tmp_path, monkeypatch)
    config = _role_config(tmp_path)
    monkeypatch.setattr(
        "orchestrator.invoke_role.load_role_config", lambda _role, _variant=None: config
    )

    def _noop(_invocation: RoleInvocation) -> None:
        return None

    backend = StubBackend(
        [_agent_error_result(), _ok_result(), _ok_result()],
        side_effects=[_noop, _write_invalid_output, _write_output(_evidence())],
    )

    artifact = invoke(case, "researcher", _task("T-902"), backend=backend)

    assert isinstance(artifact, EvidenceRecord)
    assert [inv.model for inv in backend.invocations] == [
        "composer-2.5",
        "composer-2.5",
        "gpt-5.2",
    ]
    assert (case.root / "agents" / "researcher--T-902--attempt-1").exists()


def test_workspace_shape_and_permissions_and_outside_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case, runtime_root = _build_case(tmp_path, monkeypatch)
    config = _role_config(tmp_path, allow_shell=False)
    layout = build_workspace(
        case=case,
        role_config=config,
        role="researcher",
        task=WorkspaceTask(
            task_id="T-400",
            assignment="Do task",
            required_output_filename="evidence_record.yaml",
            required_output_schema="evidence_record",
        ),
        projected_inputs=[ProjectedArtifact(filename="decision_spec.yaml", yaml_text="a: 1\n")],
    )

    assert layout.path.is_relative_to(runtime_root.resolve())
    assert not layout.path.is_relative_to(_repo_root().resolve())
    top_level = sorted(path.name for path in layout.path.iterdir())
    assert top_level == [".cursor", "AGENTS.md", "inputs", "outputs", "task.yaml"]
    assert sorted(path.name for path in (layout.path / ".cursor").iterdir()) == ["cli.json"]
    agents_text = (layout.path / "AGENTS.md").read_text(encoding="utf-8")
    assert agents_text == config.role_md_path.read_text(encoding="utf-8")
    cli_config = json.loads((layout.path / ".cursor" / "cli.json").read_text(encoding="utf-8"))
    assert cli_config["permissions"]["deny"] == ["Shell(*)"]
    assert len(cli_config["permissions"]["allow"]) == 2


def test_assert_isolated_behavior(tmp_path: Path) -> None:
    polluted = tmp_path / "polluted"
    workspace = polluted / "a" / "b" / "workspace"
    workspace.mkdir(parents=True)
    (polluted / "AGENTS.md").write_text("leak", encoding="utf-8")
    with pytest.raises(WorkspaceNotIsolated):
        assert_isolated(workspace)

    clean = tmp_path / "clean" / "workspace"
    clean.mkdir(parents=True)
    assert_isolated(clean)


def test_projection_include_list_and_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case, _ = _build_case(tmp_path, monkeypatch)
    case.write_artifact(
        DecisionSpec(
            decision_id=case.root.name,
            question="Invest now?",
            owner="owner",
            deadline=date(2026, 12, 31),
            alternatives=["yes", "no"],
            objectives=["maximize returns"],
            constraints=["none"],
            risk_tolerance=RiskTolerance.MODERATE,
            reversibility=Reversibility.PARTIALLY_REVERSIBLE,
            depth=Depth.STANDARD,
        )
    )
    case.write_artifact(_evidence("E-001"))
    case.write_artifact(_evidence("E-002"))
    case.write_artifact(
        AssumptionRecord(
            assumption_id="A-001",
            claim="Market grows",
            type=AssumptionType.FORECAST,
            estimate=ProbabilityEstimate(method=ProbabilityMethod.STRUCTURED_SUBJECTIVE, point=0.6),
            confidence=Level.MEDIUM,
            materiality=Level.HIGH,
            status=AssumptionStatus.UNRESOLVED,
        )
    )

    full = project(case, include=["evidence_records"], budget_chars=100_000)
    names = {item.filename for item in full}
    assert "evidence_record--E-001.yaml" in names
    assert "evidence_record--E-002.yaml" in names
    assert all("assumption_record" not in name for name in names)

    limited = project(case, include=["evidence_records"], budget_chars=300)
    limited_names = [item.filename for item in limited]
    assert "_truncation_notice.yaml" in limited_names
    assert len([name for name in limited_names if name.startswith("evidence_record--")]) < 2


def test_read_only_variant_collects_stdout_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case, _ = _build_case(tmp_path, monkeypatch)
    config = _role_config(tmp_path, read_only=True)
    monkeypatch.setattr(
        "orchestrator.invoke_role.load_role_config", lambda _role, _variant=None: config
    )
    yaml_text = dump_model_to_yaml_text(_evidence())
    backend = StubBackend([_ok_result(result_text=f"```yaml\n{yaml_text}```")])

    artifact = invoke_read_only(case, "researcher", _task("T-500"), backend=backend)

    assert isinstance(artifact, EvidenceRecord)
    assert backend.invocations[0].read_only is True


def test_cross_field_hook_can_reject_schema_valid_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case, _ = _build_case(tmp_path, monkeypatch)
    config = _role_config(tmp_path)
    monkeypatch.setattr(
        "orchestrator.invoke_role.load_role_config", lambda _role, _variant=None: config
    )
    backend = StubBackend(
        [_ok_result(), _ok_result(), _ok_result()],
        side_effects=[
            _write_output(_evidence()),
            _write_output(_evidence()),
            _write_output(_evidence()),
        ],
    )

    def _hook(_: EvidenceRecord, __) -> None:
        raise ValueError("cross-field hook rejected artifact")

    register_cross_field_validation_hook("evidence_record", _hook)
    try:
        with pytest.raises(RoleInvocationFailed, match="cross-field hook rejected artifact"):
            invoke(case, "researcher", _task("T-600"), backend=backend)
    finally:
        clear_cross_field_validation_hooks("evidence_record")


def test_model_family_helper() -> None:
    assert family("claude-opus-5-thinking-high") == "anthropic"
    assert family("gpt-5.6-sol-high") == "openai"
    assert family("composer-2.5") == "cursor"
    assert family("cursor-grok-4.5-low") == "cursor"


@pytest.mark.live
def test_mini_run_live(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case, _ = _build_case(tmp_path, monkeypatch)
    role_md = tmp_path / "live-role.md"
    role_md.write_text(
        (
            "You are a deterministic writer.\n"
            "Read task.yaml and write outputs/evidence_record.yaml with valid schema fields.\n"
            "Use source_url: https://example.com/live and evidence_id: E-999.\n"
            "Stop after writing the file.\n"
        ),
        encoding="utf-8",
    )
    config = RoleConfig(
        role=TaskRole.RESEARCHER,
        role_md_path=role_md,
        default_model="composer-2.5",
        escalation_model="composer-2.5",
        read_only=False,
        permission_profile=PermissionProfile(allow_shell=False),
        projection_include=tuple(),
        output_artifact_type="evidence_record",
        model_tier="low",
    )
    monkeypatch.setattr(
        "orchestrator.invoke_role.load_role_config", lambda _role, _variant=None: config
    )

    artifact = invoke(case, "researcher", _task("T-700"), backend=CursorCLIBackend())

    assert isinstance(artifact, EvidenceRecord)
