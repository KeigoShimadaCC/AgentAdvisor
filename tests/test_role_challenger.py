from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from orchestrator import roles_config as rc
from orchestrator.artifacts import (
    AssumptionRecord,
    AuditEvent,
    DecisionSpec,
    EvidenceRecord,
    ObjectionBatch,
    ObjectionRecord,
    PreliminaryRecommendation,
)
from orchestrator.artifacts.yaml_io import dump_model_to_yaml_text
from orchestrator.backend import (
    CursorCLIBackend,
    ResultStatus,
    RoleInvocation,
    RoleResult,
    StubBackend,
)
from orchestrator.case_store import Case, create_case
from orchestrator.invoke_role import InvokeTask, invoke
from orchestrator.roles_config import (
    RoleConfigError,
    load_role_config,
    validate_director_challenger_family_diversity,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "roles" / "challenger"
PLANTED_TARGET = "A-301"


def _ok_result() -> RoleResult:
    return RoleResult(
        status=ResultStatus.OK,
        result_text="ok",
        session_id="sess-1",
        request_id="req-1",
        duration_ms=15,
        raw_stdout="{}",
        raw_stderr="",
        cli_version="cursor-agent test",
    )


def _build_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Case:
    case = create_case("challenger", cases_root=tmp_path / "cases-root")
    monkeypatch.setenv("AGENTADVISOR_RUNTIME_ROOT", str(tmp_path / "runtime-root"))
    return case


def _load_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError(f"Fixture must be a mapping: {path}")
    return loaded


def _seed_flawed_context(case: Case) -> None:
    payload = _load_yaml(FIXTURES_DIR / "flawed_context.yaml")

    decision_payload = payload["decision_spec"]
    assumptions_payload = payload["assumptions"]
    evidence_payload = payload["evidence"]
    objections_payload = payload["prior_resolved_objections"]
    preliminary_payload = payload["preliminary_recommendation"]

    if not isinstance(decision_payload, dict):
        raise TypeError("decision_spec fixture payload must be a mapping.")
    if not isinstance(assumptions_payload, list):
        raise TypeError("assumptions fixture payload must be a list.")
    if not isinstance(evidence_payload, list):
        raise TypeError("evidence fixture payload must be a list.")
    if not isinstance(objections_payload, list):
        raise TypeError("prior_resolved_objections fixture payload must be a list.")
    if not isinstance(preliminary_payload, dict):
        raise TypeError("preliminary_recommendation fixture payload must be a mapping.")

    case.write_artifact(DecisionSpec.model_validate(decision_payload))
    for assumption in assumptions_payload:
        case.write_artifact(AssumptionRecord.model_validate(assumption))
    for evidence in evidence_payload:
        case.write_artifact(EvidenceRecord.model_validate(evidence))
    for objection in objections_payload:
        case.write_artifact(ObjectionRecord.model_validate(objection))

    recommendation = PreliminaryRecommendation.model_validate(preliminary_payload)
    (case.root / "outputs" / "preliminary_recommendation.yaml").write_text(
        dump_model_to_yaml_text(recommendation),
        encoding="utf-8",
    )


def _write_output_from_fixture(fixture_name: str):
    payload = (FIXTURES_DIR / "replay" / fixture_name).read_text(encoding="utf-8")

    def _side_effect(invocation: RoleInvocation) -> None:
        (invocation.workspace / "outputs" / "objection_batch.yaml").write_text(
            payload,
            encoding="utf-8",
        )

    return _side_effect


def _load_objection_batch(path: Path) -> ObjectionBatch:
    return ObjectionBatch.model_validate(_load_yaml(path))


def _count_attempts(case: Case, task_id: str) -> int:
    lines = (case.root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    events = [AuditEvent.model_validate_json(line) for line in lines]
    return sum(
        1
        for event in events
        if event.actor == "challenger"
        and event.event_type == "role_invocation_attempt"
        and isinstance(event.payload, dict)
        and event.payload.get("task_id") == task_id
    )


def test_challenger_role_config_loads_expected_model_and_projection() -> None:
    config = load_role_config("challenger")

    assert config.default_model == "composer-2.5"
    assert config.escalation_model == "cursor-grok-4.5-low"
    assert config.output_artifact_type == "objection_batch"
    assert "decision_spec" in config.projection_include
    assert "preliminary_recommendation" in config.projection_include
    assert "high_materiality_assumptions" in config.projection_include
    assert "key_evidence" in config.projection_include
    assert "objections" in config.projection_include


def test_fixture_replay_produces_schema_valid_objection_with_required_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    _seed_flawed_context(case)
    backend = StubBackend(
        [_ok_result()],
        side_effects=[_write_output_from_fixture("objection_batch.yaml")],
    )

    artifact = invoke(
        case,
        "challenger",
        InvokeTask(
            task_id="T-CHAL-001",
            assignment="Run adversarial review and return one material objection.",
            output_artifact_type="objection_batch",
        ),
        backend=backend,
    )

    assert isinstance(artifact, ObjectionBatch)
    assert artifact.mode.value == "standard"
    assert len(artifact.objections) == 1
    assert artifact.objections[0].materiality.value in {"high", "medium", "low"}
    assert artifact.objections[0].target_section.strip()
    assert artifact.objections[0].reversal_evidence.strip()

    objections = _load_objection_batch(FIXTURES_DIR / "objections.valid.yaml")
    assert len(objections.objections) <= 5
    assert all(objection.target_section.strip() for objection in objections.objections)
    assert all(
        objection.materiality.value in {"high", "medium", "low"}
        for objection in objections.objections
    )


def test_six_objection_fixture_is_rejected_by_cap_validation() -> None:
    with pytest.raises(ValidationError, match=r"objections exceeds 5 cap for mode 'standard'\."):
        _load_objection_batch(FIXTURES_DIR / "objections.too_many.yaml")


def test_director_and_challenger_same_family_fails_startup_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    roles_dir = repo_root / "cursor" / "roles"
    roles_dir.mkdir(parents=True, exist_ok=True)
    (roles_dir / "director.md").write_text("director\n", encoding="utf-8")
    (roles_dir / "challenger.md").write_text("challenger\n", encoding="utf-8")
    (roles_dir / "director.yaml").write_text(
        "\n".join(
            [
                "role_md_path: cursor/roles/director.md",
                "default_model: gpt-5.6-sol-high",
                "escalation_model: gpt-5.6-sol-high",
                "read_only: false",
                "allow_shell: false",
                "projection_include: []",
                "output_artifact_type: preliminary_recommendation",
                "model_tier: high",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (roles_dir / "challenger.yaml").write_text(
        "\n".join(
            [
                "role_md_path: cursor/roles/challenger.md",
                "default_model: gpt-5.6-sol-high",
                "escalation_model: gpt-5.6-sol-high",
                "read_only: false",
                "allow_shell: false",
                "projection_include: []",
                "output_artifact_type: objection_batch",
                "model_tier: high",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(rc, "_repo_root", lambda: repo_root)
    with pytest.raises(RoleConfigError, match=r"Director/Challenger family diversity guard failed"):
        validate_director_challenger_family_diversity()


def test_final_pass_mode_written_and_cap_is_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    _seed_flawed_context(case)
    backend = StubBackend(
        [_ok_result()],
        side_effects=[_write_output_from_fixture("objection_batch.yaml")],
    )

    invoke(
        case,
        "challenger",
        InvokeTask(
            task_id="T-CHAL-FINAL",
            assignment="Final falsification pass. Return only the strongest objection if any.",
            output_artifact_type="objection_batch",
            mode="final_pass",
        ),
        backend=backend,
    )

    task_yaml = (case.root / "agents" / "challenger--T-CHAL-FINAL" / "task.yaml").read_text(
        encoding="utf-8"
    )
    assert "mode: final_pass" in task_yaml

    with pytest.raises(ValidationError, match=r"objections exceeds 2 cap for mode 'final_pass'\."):
        _load_objection_batch(FIXTURES_DIR / "objections.final_pass.too_many.yaml")


def test_empty_batch_without_justification_is_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match=r"An empty objections list requires no_objections_justification",
    ):
        _load_objection_batch(FIXTURES_DIR / "objections.empty_without_justification.yaml")


@pytest.mark.live
def test_live_mini_run_challenger_finds_planted_flaw_within_two_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    _seed_flawed_context(case)

    artifact = invoke(
        case,
        "challenger",
        InvokeTask(
            task_id="T-CHAL-LIVE",
            assignment=(
                "Challenge the preliminary recommendation. Focus on material objections only. "
                "Target sections mechanically and include reversal evidence."
            ),
            output_artifact_type="objection_batch",
        ),
        backend=CursorCLIBackend(),
    )

    assert isinstance(artifact, ObjectionBatch)
    assert any(PLANTED_TARGET in objection.target_section for objection in artifact.objections)
    assert _count_attempts(case, "T-CHAL-LIVE") <= 2
