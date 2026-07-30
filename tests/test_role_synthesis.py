from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import (
    AssumptionRecord,
    AuditEvent,
    DecisionSpec,
    EvidenceRecord,
    FinalRecommendation,
    ObjectionRecord,
    ReviewDefectType,
    ReviewOutcome,
    ReviewReport,
    TaskRole,
)
from orchestrator.artifacts.yaml_io import load_model_from_yaml_path
from orchestrator.backend import (
    CursorCLIBackend,
    ResultStatus,
    RoleInvocation,
    RoleResult,
    StubBackend,
)
from orchestrator.case_store import Case, create_case
from orchestrator.invoke_role import (
    InvokeTask,
    RoleInvocationFailed,
    clear_cross_field_validation_hooks,
    invoke,
    register_cross_field_validation_hook,
)
from orchestrator.render import validate_final_recommendation_citations
from orchestrator.roles_config import PermissionProfile, RoleConfig, family, load_role_config


def _fixture_root() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "roles" / "synthesis" / "replay"


def _ok_result(*, result_text: str = "ok") -> RoleResult:
    return RoleResult(
        status=ResultStatus.OK,
        result_text=result_text,
        session_id="sess-1",
        request_id="req-1",
        duration_ms=20,
        raw_stdout="{}",
        raw_stderr="",
        cli_version="cursor-agent test",
    )


def _read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_evidence_records(path: Path) -> list[EvidenceRecord]:
    payload = _read_yaml(path)
    if not isinstance(payload, list):
        raise TypeError("evidence fixture must be a list")
    return [EvidenceRecord.model_validate(item) for item in payload]


def _load_assumptions(path: Path) -> list[AssumptionRecord]:
    payload = _read_yaml(path)
    if not isinstance(payload, list):
        raise TypeError("assumption fixture must be a list")
    return [AssumptionRecord.model_validate(item) for item in payload]


def _load_objections(path: Path) -> list[ObjectionRecord]:
    payload = _read_yaml(path)
    if not isinstance(payload, list):
        raise TypeError("objection fixture must be a list")
    return [ObjectionRecord.model_validate(item) for item in payload]


def _seed_case_inputs(case: Case, fixture_root: Path) -> None:
    decision_spec = load_model_from_yaml_path(DecisionSpec, fixture_root / "decision_spec.yaml")
    case.write_artifact(decision_spec)
    for evidence in _load_evidence_records(fixture_root / "evidence_records.yaml"):
        case.write_artifact(evidence)
    for assumption in _load_assumptions(fixture_root / "assumptions.yaml"):
        case.write_artifact(assumption)
    for objection in _load_objections(fixture_root / "objections.yaml"):
        case.write_artifact(objection)
    preliminary_text = (fixture_root / "preliminary_recommendation.yaml").read_text(
        encoding="utf-8"
    )
    (case.root / "outputs" / "preliminary_recommendation.yaml").write_text(
        preliminary_text,
        encoding="utf-8",
    )


def _write_output_from_fixture(
    fixture_path: Path, output_filename: str
) -> Callable[[RoleInvocation], None]:
    payload = fixture_path.read_text(encoding="utf-8")

    def _side_effect(invocation: RoleInvocation) -> None:
        output_path = invocation.workspace / "outputs" / output_filename
        output_path.write_text(payload, encoding="utf-8")

    return _side_effect


def _build_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, slug: str) -> Case:
    case = create_case(slug, cases_root=tmp_path / "cases-root")
    monkeypatch.setenv("AGENTADVISOR_RUNTIME_ROOT", str(tmp_path / "runtime-root"))
    return case


def _attempt_count(case: Case, role: str, task_id: str) -> int:
    lines = (case.root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    events = [AuditEvent.model_validate_json(line) for line in lines]
    return sum(
        1
        for event in events
        if event.actor == role
        and event.event_type == "role_invocation_attempt"
        and isinstance(event.payload, dict)
        and event.payload.get("task_id") == task_id
    )


def test_role_configs_use_distinct_model_families_and_expected_output_types() -> None:
    synthesizer = load_role_config(TaskRole.SYNTHESIZER)
    reviewer = load_role_config(TaskRole.REVIEWER)

    assert synthesizer.output_artifact_type == "final_recommendation"
    assert reviewer.output_artifact_type == "review_report"
    assert reviewer.read_only is False
    assert family(synthesizer.default_model) != family(reviewer.default_model)


def test_synthesizer_fixture_replay_has_section16_blocks_and_distinct_uncertainty_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_root = _fixture_root()
    case = _build_case(tmp_path, monkeypatch, "synthesizer-replay")
    _seed_case_inputs(case, fixture_root)

    backend = StubBackend(
        [_ok_result()],
        side_effects=[
            _write_output_from_fixture(
                fixture_root / "final_recommendation.yaml", "final_recommendation.yaml"
            )
        ],
    )
    artifact = invoke(
        case,
        "synthesizer",
        InvokeTask(
            task_id="T-SYN-001",
            assignment="Synthesize the final recommendation package.",
            output_artifact_type="final_recommendation",
        ),
        backend=backend,
    )
    assert isinstance(artifact, FinalRecommendation)
    assert artifact.recommended_action
    assert artifact.timing
    assert artifact.decision_confidence_summary
    assert artifact.alternatives_considered
    assert artifact.key_reasons
    assert artifact.scenario_analysis
    assert artifact.strongest_counterarguments
    assert artifact.recommendation_change_triggers
    assert artifact.next_actions
    assert artifact.citations
    assert artifact.outcome_probabilities
    assert artifact.evidence_confidence.value >= 0
    assert artifact.recommendation_confidence.value >= 0
    assert (
        artifact.model_stability.share_of_sensitivity_runs_supporting_recommendation
        == artifact.model_stability.runs_supporting / artifact.model_stability.runs_total
    )
    validate_final_recommendation_citations(
        artifact,
        case.list_artifacts(EvidenceRecord),
    )


def test_synthesizer_dangling_citation_fixture_fails_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_root = _fixture_root()
    case = _build_case(tmp_path, monkeypatch, "synthesizer-dangling")
    _seed_case_inputs(case, fixture_root)

    def _citation_hook(model: Any, hook_case: Case) -> None:
        if not isinstance(model, FinalRecommendation):
            raise TypeError("Hook expected FinalRecommendation")
        validate_final_recommendation_citations(model, hook_case.list_artifacts(EvidenceRecord))

    register_cross_field_validation_hook("final_recommendation", _citation_hook)
    try:
        backend = StubBackend(
            [_ok_result(), _ok_result(), _ok_result()],
            side_effects=[
                _write_output_from_fixture(
                    fixture_root / "final_recommendation.dangling.yaml",
                    "final_recommendation.yaml",
                ),
                _write_output_from_fixture(
                    fixture_root / "final_recommendation.dangling.yaml",
                    "final_recommendation.yaml",
                ),
                _write_output_from_fixture(
                    fixture_root / "final_recommendation.dangling.yaml",
                    "final_recommendation.yaml",
                ),
            ],
        )
        with pytest.raises(RoleInvocationFailed):
            invoke(
                case,
                "synthesizer",
                InvokeTask(
                    task_id="T-SYN-002",
                    assignment="Synthesize with dangling citation fixture.",
                    output_artifact_type="final_recommendation",
                ),
                backend=backend,
            )
    finally:
        clear_cross_field_validation_hooks("final_recommendation")


def test_reviewer_fixture_flags_false_precision_and_unsupported_citation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_root = _fixture_root()
    case = _build_case(tmp_path, monkeypatch, "reviewer-fail")
    _seed_case_inputs(case, fixture_root)
    (case.root / "outputs" / "final_recommendation.yaml").write_text(
        (fixture_root / "final_recommendation.dangling.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    backend = StubBackend(
        [_ok_result()],
        side_effects=[
            _write_output_from_fixture(
                fixture_root / "review_report.fail.yaml", "review_report.yaml"
            )
        ],
    )

    artifact = invoke(
        case,
        "reviewer",
        InvokeTask(
            task_id="T-REV-001",
            assignment="Review final recommendation for calibration and citation defects.",
            output_artifact_type="review_report",
        ),
        backend=backend,
    )
    assert isinstance(artifact, ReviewReport)
    assert artifact.outcome is ReviewOutcome.FAIL
    defect_types = {defect.defect_type for defect in artifact.defects}
    assert ReviewDefectType.FALSE_PRECISION in defect_types
    assert ReviewDefectType.UNSUPPORTED_CITATION in defect_types


def test_reviewer_clean_fixture_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture_root = _fixture_root()
    case = _build_case(tmp_path, monkeypatch, "reviewer-pass")
    _seed_case_inputs(case, fixture_root)
    (case.root / "outputs" / "final_recommendation.yaml").write_text(
        (fixture_root / "final_recommendation.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    backend = StubBackend(
        [_ok_result()],
        side_effects=[
            _write_output_from_fixture(
                fixture_root / "review_report.pass.yaml", "review_report.yaml"
            )
        ],
    )

    artifact = invoke(
        case,
        "reviewer",
        InvokeTask(
            task_id="T-REV-002",
            assignment="Review a clean final recommendation fixture.",
            output_artifact_type="review_report",
        ),
        backend=backend,
    )
    assert isinstance(artifact, ReviewReport)
    assert artifact.outcome is ReviewOutcome.PASS
    assert artifact.defects == []


@pytest.mark.live
def test_live_mini_run_synthesizer_schema_valid_within_two_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _build_case(tmp_path, monkeypatch, "synthesizer-live")
    role_md = tmp_path / "synthesizer-live.md"
    role_md.write_text(
        (
            "Read task.yaml and write exactly one schema-valid outputs/final_recommendation.yaml.\n"
            "Use EXACT field names and types below; do not add extra keys (forbidden: task_id,\n"
            "alternative_assessments, scenarios, or model_stability.share).\n"
            "recommended_action: invest_in_stages\n"
            "timing: this quarter\n"
            "decision_confidence_summary: Moderate confidence in staged deployment,\n"
            "  under current evidence.\n"
            "alternatives_considered:\n"
            "  - alternative: immediate_full_commitment\n"
            "    rank: 2\n"
            "    rationale: Lower flexibility if early signals degrade.\n"
            "key_reasons:\n"
            "  - Staged investment preserves option value while keeping upside exposure.\n"
            "scenario_analysis:\n"
            "  - scenario_name: milestone_success\n"
            "    summary: Early milestones are met and staged deployment continues.\n"
            "    probability:\n"
            "      method: structured_subjective\n"
            "      point: 0.55\n"
            "quantitative_findings:\n"
            "  - Expected value remains positive under staged deployment assumptions.\n"
            "strongest_counterarguments:\n"
            "  - claim: Staging may delay upside capture.\n"
            "    resolution: Delay cost is acceptable relative to downside control.\n"
            "    resolved: true\n"
            "critical_assumptions: []\n"
            "recommendation_change_triggers:\n"
            "  - Material deterioration in milestone conversion.\n"
            "next_actions:\n"
            "  - Define stage-gate milestones and tranche release rules.\n"
            "citations: [E-321]\n"
            "outcome_probabilities:\n"
            "  staged_investment_succeeds:\n"
            "    method: structured_subjective\n"
            "    point: 0.55\n"
            "evidence_confidence:\n"
            "  value: 0.6\n"
            "  basis: Moderate support from provided evidence set.\n"
            "recommendation_confidence:\n"
            "  value: 0.7\n"
            "  basis: Recommendation is stable under the stated scenario assumptions.\n"
            "model_stability:\n"
            "  runs_total: 10\n"
            "  runs_supporting: 8\n"
            "  share_of_sensitivity_runs_supporting_recommendation: 0.8\n"
            "Stop.\n"
        ),
        encoding="utf-8",
    )
    config = RoleConfig(
        role=TaskRole.SYNTHESIZER,
        role_md_path=role_md,
        default_model="claude-opus-5-thinking-high",
        escalation_model="claude-opus-5-thinking-high",
        read_only=False,
        permission_profile=PermissionProfile(allow_shell=False),
        projection_include=tuple(),
        output_artifact_type="final_recommendation",
        model_tier="high",
    )
    monkeypatch.setattr(
        "orchestrator.invoke_role.load_role_config",
        lambda _role, _variant=None: config,
    )

    artifact = invoke(
        case,
        "synthesizer",
        InvokeTask(
            task_id="T-SYN-LIVE",
            assignment="Produce a minimal schema-valid final recommendation.",
            output_artifact_type="final_recommendation",
            timeout_s=300.0,
        ),
        backend=CursorCLIBackend(),
    )

    assert isinstance(artifact, FinalRecommendation)
    assert _attempt_count(case, "synthesizer", "T-SYN-LIVE") <= 2


@pytest.mark.live
def test_live_mini_run_reviewer_schema_valid_within_two_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _build_case(tmp_path, monkeypatch, "reviewer-live")
    role_md = tmp_path / "reviewer-live.md"
    role_md.write_text(
        (
            "Read task.yaml and write outputs/review_report.yaml.\n"
            "Write a schema-valid review_report with outcome pass and defects [].\n"
            "Stop.\n"
        ),
        encoding="utf-8",
    )
    config = RoleConfig(
        role=TaskRole.REVIEWER,
        role_md_path=role_md,
        default_model="gpt-5.2",
        escalation_model="gpt-5.2",
        read_only=False,
        permission_profile=PermissionProfile(allow_shell=False),
        projection_include=tuple(),
        output_artifact_type="review_report",
        model_tier="medium",
    )
    monkeypatch.setattr(
        "orchestrator.invoke_role.load_role_config",
        lambda _role, _variant=None: config,
    )

    artifact = invoke(
        case,
        "reviewer",
        InvokeTask(
            task_id="T-REV-LIVE",
            assignment="Return a minimal schema-valid review report.",
            output_artifact_type="review_report",
            timeout_s=120.0,
        ),
        backend=CursorCLIBackend(),
    )

    assert isinstance(artifact, ReviewReport)
    assert artifact.outcome is ReviewOutcome.PASS
    assert _attempt_count(case, "reviewer", "T-REV-LIVE") <= 2
