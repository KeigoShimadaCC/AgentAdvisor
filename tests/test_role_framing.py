from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import AuditEvent, DecisionSpec, IntakeRecord
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


def _fixture_root() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "roles" / "framing"


def _load_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError(f"Fixture must be a mapping: {path}")
    return loaded


def _ok_result() -> RoleResult:
    return RoleResult(status=ResultStatus.OK, duration_ms=10, result_text="ok")


def _write_output_from_fixture(
    fixture_path: Path, output_filename: str
) -> Callable[[RoleInvocation], None]:
    payload = fixture_path.read_text(encoding="utf-8")

    def _side_effect(invocation: RoleInvocation) -> None:
        output_path = invocation.workspace / "outputs" / output_filename
        output_path.write_text(payload, encoding="utf-8")

    return _side_effect


def _build_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Case:
    case = create_case("framing", cases_root=tmp_path / "cases-root")
    monkeypatch.setenv("AGENTADVISOR_RUNTIME_ROOT", str(tmp_path / "runtime-root"))
    return case


def _build_intake_task(task_id: str, raw_prompt: str) -> InvokeTask:
    return InvokeTask(
        task_id=task_id,
        assignment=(
            "Extract a schema-valid intake artifact from this raw user prompt.\n"
            f"Raw user prompt:\n{raw_prompt}"
        ),
        output_artifact_type="intake_record",
    )


def _build_framing_task(task_id: str, case_id: str) -> InvokeTask:
    return InvokeTask(
        task_id=task_id,
        assignment=(
            "Produce a schema-valid decision specification from the provided intake input.\n"
            f"Case ID: {case_id}\n"
            "Owner: user"
        ),
        output_artifact_type="decision_spec",
    )


def _seed_intake_projection_input(case: Case, intake_record: IntakeRecord) -> None:
    projection_path = case.root / "outputs" / "intake_record.yaml"
    projection_path.write_text(dump_model_to_yaml_text(intake_record), encoding="utf-8")


def _assert_clarifications_only_for_null_fields(intake: IntakeRecord) -> None:
    for clarification in intake.clarification_questions:
        assert getattr(intake, clarification.resolves_field.value) is None


def _audit_lines(case_root: Path) -> list[AuditEvent]:
    lines = (case_root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    return [AuditEvent.model_validate_json(line) for line in lines]


def _attempt_count(case_root: Path, role: str, task_id: str) -> int:
    count = 0
    for event in _audit_lines(case_root):
        if event.actor != role:
            continue
        payload = event.payload
        if isinstance(payload, dict) and payload.get("task_id") == task_id:
            count += 1
    return count


def test_investment_fixture_structural(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    case = _build_case(tmp_path, monkeypatch)
    prompt_fixture = _load_yaml(_fixture_root() / "investment_prompt.yaml")
    raw_prompt = str(prompt_fixture["raw_prompt"])
    expected_constraints = [str(value) for value in prompt_fixture["expected_constraints"]]

    intake_backend = StubBackend(
        [_ok_result()],
        side_effects=[
            _write_output_from_fixture(
                _fixture_root() / "investment" / "intake_record.yaml", "intake_record.yaml"
            )
        ],
    )
    intake = invoke(case, "intake", _build_intake_task("T-900", raw_prompt), backend=intake_backend)
    assert isinstance(intake, IntakeRecord)
    _assert_clarifications_only_for_null_fields(intake)
    case.write_artifact(intake)
    _seed_intake_projection_input(case, intake)

    framing_backend = StubBackend(
        [_ok_result()],
        side_effects=[
            _write_output_from_fixture(
                _fixture_root() / "investment" / "decision_spec.yaml", "decision_spec.yaml"
            )
        ],
    )
    decision_spec = invoke(
        case,
        "director",
        _build_framing_task("T-901", case.root.name),
        backend=framing_backend,
        variant="framing",
    )
    assert isinstance(decision_spec, DecisionSpec)
    assert len(decision_spec.alternatives) >= 5
    assert any(option.lower() not in raw_prompt.lower() for option in decision_spec.alternatives)
    for expected in expected_constraints:
        assert any(
            expected.lower() in constraint.lower() for constraint in decision_spec.constraints
        )


def test_vague_fixture_structural(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    case = _build_case(tmp_path, monkeypatch)
    prompt_fixture = _load_yaml(_fixture_root() / "vague_prompt.yaml")
    raw_prompt = str(prompt_fixture["raw_prompt"])

    intake_backend = StubBackend(
        [_ok_result()],
        side_effects=[
            _write_output_from_fixture(
                _fixture_root() / "vague" / "intake_record.yaml", "intake_record.yaml"
            )
        ],
    )
    intake = invoke(case, "intake", _build_intake_task("T-910", raw_prompt), backend=intake_backend)
    assert isinstance(intake, IntakeRecord)
    assert len(intake.clarification_questions) <= 5
    _assert_clarifications_only_for_null_fields(intake)
    case.write_artifact(intake)
    _seed_intake_projection_input(case, intake)

    framing_backend = StubBackend(
        [_ok_result()],
        side_effects=[
            _write_output_from_fixture(
                _fixture_root() / "vague" / "decision_spec.yaml", "decision_spec.yaml"
            )
        ],
    )
    decision_spec = invoke(
        case,
        "director",
        _build_framing_task("T-911", case.root.name),
        backend=framing_backend,
        variant="framing",
    )
    assert isinstance(decision_spec, DecisionSpec)
    assert decision_spec.alternatives
    assert decision_spec.objectives


@pytest.mark.live
def test_live_mini_run_framing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    case = _build_case(tmp_path, monkeypatch)
    prompt_fixture = _load_yaml(_fixture_root() / "vague_prompt.yaml")
    raw_prompt = str(prompt_fixture["raw_prompt"])

    intake = invoke(
        case,
        "intake",
        _build_intake_task("T-920", raw_prompt),
        backend=CursorCLIBackend(),
    )
    assert isinstance(intake, IntakeRecord)
    assert len(intake.clarification_questions) <= 5
    _assert_clarifications_only_for_null_fields(intake)
    case.write_artifact(intake)
    _seed_intake_projection_input(case, intake)

    decision_spec = invoke(
        case,
        "director",
        _build_framing_task("T-921", case.root.name),
        backend=CursorCLIBackend(),
        variant="framing",
    )
    assert isinstance(decision_spec, DecisionSpec)
    assert decision_spec.alternatives
    assert decision_spec.objectives

    assert _attempt_count(case.root, "intake", "T-920") <= 2
    assert _attempt_count(case.root, "director", "T-921") <= 2
