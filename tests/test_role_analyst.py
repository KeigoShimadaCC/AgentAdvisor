from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import (
    AnalysisResult,
    AssumptionRecord,
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
from orchestrator.artifacts.yaml_io import load_model_from_yaml_path
from orchestrator.backend import (
    CursorCLIBackend,
    ResultStatus,
    RoleInvocation,
    RoleResult,
    StubBackend,
)
from orchestrator.case_store import create_case
from orchestrator.invoke_role import InvokeTask, invoke
from orchestrator.reproduce import ReproduceStatus, reproduce_analysis_result
from orchestrator.roles_config import PermissionProfile, RoleConfig, load_role_config

FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures" / "roles" / "analyst"


def _build_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cases_root = tmp_path / "cases-root"
    case = create_case("analyst", cases_root=cases_root)
    monkeypatch.setenv("AGENTADVISOR_RUNTIME_ROOT", str(tmp_path / "runtime-root"))
    return case


def _ok_result() -> RoleResult:
    return RoleResult(
        status=ResultStatus.OK,
        result_text="ok",
        session_id="sess-1",
        request_id="req-1",
        duration_ms=10,
        usage=None,
        raw_stdout="{}",
        raw_stderr="",
        cli_version="cursor-agent test",
    )


def _seed_case_inputs(case) -> None:
    case.write_artifact(
        DecisionSpec(
            decision_id=case.root.name,
            question="Choose between invest_now and wait.",
            owner="owner",
            deadline=date(2026, 12, 31),
            alternatives=["invest_now", "wait"],
            objectives=["maximize expected value"],
            constraints=["limit downside"],
            risk_tolerance=RiskTolerance.MODERATE,
            reversibility=Reversibility.PARTIALLY_REVERSIBLE,
            depth=Depth.STANDARD,
        )
    )
    case.write_artifact(
        EvidenceRecord(
            evidence_id="E-001",
            claim="Comparable category investments had moderate upside distribution.",
            source_title="Benchmark memo",
            publisher="Example Research",
            source_url="https://example.com/benchmark",
            source_type=SourceType.REPUTABLE_SECONDARY,
            publication_date=date(2026, 1, 10),
            retrieval_date=date(2026, 1, 11),
            excerpt="Median outcome near base case, long right tail.",
            reliability=Level.MEDIUM,
            directness=Level.MEDIUM,
            independence_group="benchmark-memo-2026",
            limitations=["Secondary synthesis"],
            retrieved_by="researcher",
        )
    )
    case.write_artifact(
        AssumptionRecord(
            assumption_id="A-001",
            claim="Distribution channel quality stays stable through horizon.",
            type=AssumptionType.FORECAST,
            estimate=ProbabilityEstimate(method=ProbabilityMethod.STRUCTURED_SUBJECTIVE, point=0.6),
            confidence=Level.MEDIUM,
            materiality=Level.HIGH,
            status=AssumptionStatus.UNRESOLVED,
        )
    )


def test_analyst_role_config_loads_expected_permissions_and_output_type() -> None:
    config = load_role_config(TaskRole.ANALYST)

    assert config.default_model == "gpt-5.3-codex"
    assert config.permission_profile.allow_shell is True
    assert config.output_artifact_type == "analysis_result"
    assert "decision_spec" in config.projection_include
    assert "assumptions" in config.projection_include
    assert "key_evidence" in config.projection_include


def test_fixture_replay_is_schema_valid_and_reproducible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    _seed_case_inputs(case)
    fixture_dir = FIXTURES_ROOT / "replay"
    scripted_artifact = load_model_from_yaml_path(
        AnalysisResult,
        fixture_dir / "analysis_result.yaml",
    )

    def _side_effect(invocation: RoleInvocation) -> None:
        output_path = invocation.workspace / "outputs" / "analysis_result.yaml"
        output_path.write_text(
            (fixture_dir / "analysis_result.yaml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        analysis_dir = case.root / "analysis" / scripted_artifact.task_id
        analysis_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fixture_dir / "model.py", analysis_dir / "model.py")
        shutil.copy2(fixture_dir / "results.yaml", analysis_dir / "results.yaml")

    backend = StubBackend([_ok_result()], side_effects=[_side_effect])
    role_md = tmp_path / "analyst-replay.md"
    role_md.write_text("Fixture replay analyst role.\n", encoding="utf-8")
    config = RoleConfig(
        role=TaskRole.ANALYST,
        role_md_path=role_md,
        default_model="gpt-5.3-codex",
        escalation_model="gpt-5.6-sol-high",
        read_only=False,
        permission_profile=PermissionProfile(allow_shell=True),
        projection_include=("decision_spec", "task_records", "key_evidence", "assumptions"),
        output_artifact_type="analysis_result",
        model_tier="medium",
    )
    monkeypatch.setattr(
        "orchestrator.invoke_role.load_role_config", lambda _role, _variant=None: config
    )

    artifact = invoke(
        case,
        "analyst",
        InvokeTask(
            task_id="T-900",
            assignment="Run the fixture analysis model.",
            output_artifact_type="analysis_result",
        ),
        backend=backend,
    )

    assert isinstance(artifact, AnalysisResult)
    result = reproduce_analysis_result(
        case_root=case.root,
        analysis_result=artifact,
        timeout_s=2.0,
    )
    assert result.status is ReproduceStatus.PASS
    rerun_results = yaml.safe_load((case.root / artifact.results_path).read_text(encoding="utf-8"))
    assert (
        rerun_results["expected_values_by_alternative"] == artifact.expected_values_by_alternative
    )


@pytest.mark.live
def test_live_mini_run_analyst_reproducible_within_two_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    _seed_case_inputs(case)
    role_md = tmp_path / "analyst-live.md"
    task_id = "T-910"
    role_md.write_text(
        (
            "You are a deterministic quantitative analyst.\n"
            "Read task.yaml and use task_id T-910 exactly.\n"
            "Create analysis/T-910/model.py using only the Python standard library.\n"
            "In model.py, write results using a path derived from __file__.\n"
            "This must work when rerun from any cwd.\n"
            "Path(__file__).resolve().parent / 'results.yaml'.\n"
            "Execute the script once and ensure it writes analysis/T-910/results.yaml.\n"
            "Then write outputs/analysis_result.yaml with EXACTLY this schema-valid shape.\n"
            "Use these exact field names.\n"
            "(no extra keys like schema, scenario_id, outcomes,\n"
            "low_case/base_case/high_case, direction,\n"
            "or preferred_alternative_at_threshold):\n"
            "task_id: T-910\n"
            "script_path: analysis/T-910/model.py\n"
            "results_path: analysis/T-910/results.yaml\n"
            "expected_values_by_alternative:\n"
            "  invest_now: 106.0\n"
            "  wait: 100.0\n"
            "scenarios:\n"
            "  - scenario_name: bull\n"
            "    probability:\n"
            "      method: structured_subjective\n"
            "      point: 0.25\n"
            "  - scenario_name: base\n"
            "    probability:\n"
            "      method: structured_subjective\n"
            "      point: 0.45\n"
            "  - scenario_name: bear\n"
            "    probability:\n"
            "      method: structured_subjective\n"
            "      point: 0.20\n"
            "  - scenario_name: failure\n"
            "    probability:\n"
            "      method: structured_subjective\n"
            "      point: 0.10\n"
            "sensitivity_table:\n"
            "  - parameter: upside_multiplier\n"
            "    parameter_value: 1.0\n"
            "    resulting_expected_values:\n"
            "      invest_now: 106.0\n"
            "      wait: 100.0\n"
            "    preferred_alternative: invest_now\n"
            "  - parameter: failure_probability\n"
            "    parameter_value: 0.10\n"
            "    resulting_expected_values:\n"
            "      invest_now: 106.0\n"
            "      wait: 100.0\n"
            "    preferred_alternative: invest_now\n"
            "break_even_thresholds:\n"
            "  - parameter: invest_now_expected_value\n"
            "    threshold_value: 100.0\n"
            "    favored_alternative_below: wait\n"
            "    favored_alternative_above: invest_now\n"
            "assumption_ids: [A-001]\n"
            "evidence_ids: [E-001]\n"
            "Stop.\n"
        ),
        encoding="utf-8",
    )
    config = RoleConfig(
        role=TaskRole.ANALYST,
        role_md_path=role_md,
        default_model="gpt-5.3-codex",
        escalation_model="gpt-5.3-codex",
        read_only=False,
        permission_profile=PermissionProfile(allow_shell=True),
        projection_include=tuple(),
        output_artifact_type="analysis_result",
        model_tier="medium",
    )
    monkeypatch.setattr(
        "orchestrator.invoke_role.load_role_config", lambda _role, _variant=None: config
    )

    artifact = invoke(
        case,
        "analyst",
        InvokeTask(
            task_id=task_id,
            assignment="Build a tiny two-alternative model and return analysis_result.",
            output_artifact_type="analysis_result",
            timeout_s=300.0,
        ),
        backend=CursorCLIBackend(),
    )

    assert isinstance(artifact, AnalysisResult)
    archive_root = case.root / "agents" / f"analyst--{task_id}"
    source_analysis_root = archive_root / "analysis" / task_id
    target_analysis_root = case.root / "analysis" / task_id
    target_analysis_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_analysis_root / "model.py", target_analysis_root / "model.py")
    shutil.copy2(source_analysis_root / "results.yaml", target_analysis_root / "results.yaml")

    reproduce = reproduce_analysis_result(
        case_root=case.root,
        analysis_result=artifact,
        timeout_s=5.0,
    )
    assert reproduce.status is ReproduceStatus.PASS

    audit_lines = (case.root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(audit_lines) <= 2
    output_payload = yaml.safe_load((case.root / artifact.results_path).read_text(encoding="utf-8"))
    assert (
        output_payload["expected_values_by_alternative"] == artifact.expected_values_by_alternative
    )
    assert json.dumps(output_payload, sort_keys=True)
