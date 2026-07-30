from __future__ import annotations

from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import (
    AssumptionRecord,
    AuditEvent,
    DecisionSpec,
    ObjectionRecord,
    PlanningMode,
    TaskProposalBatch,
    TaskRecord,
)
from orchestrator.artifacts.yaml_io import load_model_from_yaml_text
from orchestrator.backend import (
    CursorCLIBackend,
    ResultStatus,
    RoleInvocation,
    RoleResult,
    StubBackend,
)
from orchestrator.case_store import Case, create_case
from orchestrator.invoke_role import InvokeTask, invoke
from orchestrator.planning import apply_planner_acceptance_filter

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "roles" / "planner"


def _ok_result() -> RoleResult:
    return RoleResult(
        status=ResultStatus.OK,
        result_text="ok",
        session_id="sess-1",
        request_id="req-1",
        duration_ms=25,
        raw_stdout="{}",
        raw_stderr="",
        cli_version="cursor-agent test",
    )


def _build_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Case:
    case = create_case("planner", cases_root=tmp_path / "cases-root")
    monkeypatch.setenv("AGENTADVISOR_RUNTIME_ROOT", str(tmp_path / "runtime-root"))
    return case


def _load_fixture_batch(name: str) -> TaskProposalBatch:
    yaml_text = (FIXTURES_DIR / name).read_text(encoding="utf-8")
    return load_model_from_yaml_text(TaskProposalBatch, yaml_text)


def _write_planner_output_from_fixture(fixture_name: str):
    yaml_text = (FIXTURES_DIR / fixture_name).read_text(encoding="utf-8")

    def _side_effect(invocation: RoleInvocation) -> None:
        output_path = invocation.workspace / "outputs" / "task_proposal_batch.yaml"
        output_path.write_text(yaml_text, encoding="utf-8")

    return _side_effect


def _seed_investment_context(case: Case) -> None:
    payload_raw = yaml.safe_load(
        (FIXTURES_DIR / "investment_context.yaml").read_text(encoding="utf-8")
    )
    if not isinstance(payload_raw, dict):
        raise TypeError("investment_context.yaml must be a mapping.")

    decision_payload = payload_raw.get("decision_spec")
    assumptions_payload = payload_raw.get("assumptions")
    objections_payload = payload_raw.get("objections")
    tasks_payload = payload_raw.get("tasks")
    if not isinstance(decision_payload, dict):
        raise TypeError("investment_context.yaml decision_spec must be a mapping.")
    if not isinstance(assumptions_payload, list):
        raise TypeError("investment_context.yaml assumptions must be a list.")
    if not isinstance(objections_payload, list):
        raise TypeError("investment_context.yaml objections must be a list.")
    if not isinstance(tasks_payload, list):
        raise TypeError("investment_context.yaml tasks must be a list.")

    case.write_artifact(DecisionSpec.model_validate(decision_payload))
    for assumption_payload in assumptions_payload:
        case.write_artifact(AssumptionRecord.model_validate(assumption_payload))
    for objection_payload in objections_payload:
        case.write_artifact(ObjectionRecord.model_validate(objection_payload))
    for task_payload in tasks_payload:
        case.write_artifact(TaskRecord.model_validate(task_payload))


def _planner_task(task_id: str, mode: PlanningMode) -> InvokeTask:
    assignment = (
        "Propose only remaining decision-relevant tasks.\n"
        f"mode: {mode.value}\n"
        "Use open objections only when mode is repair."
    )
    return InvokeTask(
        task_id=task_id,
        assignment=assignment,
        output_artifact_type="task_proposal_batch",
    )


def _assert_structural_task_fields(batch: TaskProposalBatch) -> None:
    for proposal in batch.proposals:
        assert proposal.task.role.value
        assert proposal.task.completion_criteria.strip()
        assert proposal.task.why_it_matters.strip()
        assert 0.0 <= proposal.task.probability_of_changing_conclusion <= 1.0
        assert proposal.task.estimated_cost > 0.0


def _audit_events(case: Case) -> list[AuditEvent]:
    lines = (case.root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    return [AuditEvent.model_validate_json(line) for line in lines]


@pytest.mark.parametrize(
    ("fixture_name", "mode", "max_count"),
    [
        ("post_framing.task_proposal_batch.yaml", PlanningMode.INITIAL, 10),
        ("repair_mode.task_proposal_batch.yaml", PlanningMode.REPAIR, 4),
    ],
)
def test_fixture_replay_planner_batches(
    fixture_name: str,
    mode: PlanningMode,
    max_count: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    _seed_investment_context(case)
    backend = StubBackend(
        [_ok_result()],
        side_effects=[_write_planner_output_from_fixture(fixture_name)],
    )

    artifact = invoke(case, "planner", _planner_task("T-PLN-001", mode), backend=backend)

    assert isinstance(artifact, TaskProposalBatch)
    assert artifact.mode is mode
    assert len(artifact.proposals) <= max_count
    _assert_structural_task_fields(artifact)
    if mode is PlanningMode.REPAIR:
        assert all(proposal.resolves_objections for proposal in artifact.proposals)


def test_acceptance_filter_rejects_unknown_role_and_near_duplicate_keeps_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    batch = _load_fixture_batch("post_framing.task_proposal_batch.yaml")

    unknown_role = batch.proposals[0].model_copy(
        update={"task": batch.proposals[0].task.model_copy(update={"role": "unknown_worker"})}
    )
    near_duplicate = batch.proposals[1].model_copy(
        update={
            "task": batch.proposals[1].task.model_copy(
                update={
                    "question": (
                        "  WHAT is the reference class base-rate of loss making outcomes for "
                        "comparable pre IPO software investments over five years???  "
                    )
                }
            )
        }
    )
    candidate_batch = batch.model_copy(
        update={"proposals": [unknown_role, batch.proposals[0], near_duplicate, batch.proposals[2]]}
    )

    result = apply_planner_acceptance_filter(case, candidate_batch)

    accepted_questions = [proposal.task.question for proposal in result.accepted_batch.proposals]
    assert len(result.accepted_batch.proposals) == 2
    assert batch.proposals[0].task.question in accepted_questions
    assert batch.proposals[2].task.question in accepted_questions
    assert {rejection.reason for rejection in result.rejections} == {
        "unknown_role",
        "near_duplicate_question",
    }

    events = _audit_events(case)
    assert len(events) == 2
    assert {event.event_type for event in events} == {"planner_proposal_rejected"}
    reasons = {event.payload.get("reason") for event in events}
    assert reasons == {"unknown_role", "near_duplicate_question"}


@pytest.mark.live
def test_planner_live_mini_run_investment_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    _seed_investment_context(case)

    artifact = invoke(
        case,
        "planner",
        _planner_task("T-PLN-LIVE", PlanningMode.INITIAL),
        backend=CursorCLIBackend(),
    )

    assert isinstance(artifact, TaskProposalBatch)
    assert artifact.mode is PlanningMode.INITIAL
    assert len(artifact.proposals) <= 10
    _assert_structural_task_fields(artifact)

    attempt_events = [
        event
        for event in _audit_events(case)
        if event.actor == "planner" and event.event_type == "role_invocation_attempt"
    ]
    assert 1 <= len(attempt_events) <= 2
    assert attempt_events[-1].payload.get("status") == "ok"
