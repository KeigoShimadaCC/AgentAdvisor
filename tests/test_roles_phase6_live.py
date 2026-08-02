"""Live pre-flight for the four Phase 6 roles.

These roles were added after the last benchmark run, so a full e2e sweep would be the
first time they ever met a real model. That is an expensive place to discover a broken
prompt or an unreachable schema, hence a cheap per-role check first.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import (
    AnalysisResult,
    AssumptionBatch,
    AssumptionRecord,
    DecisionSpec,
    EvidenceRecord,
    IssueTree,
    PreliminaryRecommendation,
    PreMortemReport,
)
from orchestrator.backend import CursorCLIBackend
from orchestrator.case_store import Case, create_case
from orchestrator.evidence_critic import critique_case_evidence
from orchestrator.invoke_role import InvokeTask, invoke

DIRECTOR_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "roles" / "director"
TIMEOUT_S = 300.0

pytestmark = pytest.mark.live


def _load_yaml_dict(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError(f"Fixture must be a mapping: {path}")
    return loaded


@pytest.fixture
def case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Case:
    monkeypatch.setenv("AGENTADVISOR_RUNTIME_ROOT", str(tmp_path / "runtime-root"))
    monkeypatch.setenv("AGENTADVISOR_MEMORY_ROOT", str(tmp_path / "memory"))
    built = create_case("phase6", cases_root=tmp_path / "cases-root")

    payload = _load_yaml_dict(DIRECTOR_FIXTURES / "context.yaml")
    built.write_artifact(DecisionSpec.model_validate(payload["decision_spec"]))
    for item in payload["evidence"]:
        built.write_artifact(EvidenceRecord.model_validate(item))
    for item in payload["assumptions"]:
        built.write_artifact(AssumptionRecord.model_validate(item))
    built.write_artifact(AnalysisResult.model_validate(payload["analysis"]))
    return built


def _seed_recommendation(case: Case) -> None:
    case.write_artifact(
        PreliminaryRecommendation.model_validate(
            _load_yaml_dict(DIRECTOR_FIXTURES / "preliminary_recommendation.valid.yaml")
        )
    )


def test_structurer_live_produces_a_mece_issue_tree(case: Case) -> None:
    artifact = invoke(
        case,
        "structurer",
        InvokeTask(
            task_id="T-structurer-live",
            assignment=(
                "Decompose this decision into a MECE issue tree of sub-questions.\n"
                "The root node Q-1 restates the decision. Every node needs "
                "resolution_criteria."
            ),
            output_artifact_type="issue_tree",
            timeout_s=TIMEOUT_S,
        ),
        backend=CursorCLIBackend(),
    )

    assert isinstance(artifact, IssueTree)
    assert len(artifact.nodes) >= 4
    assert len(artifact.leaf_node_ids()) >= 2
    assert all(node.resolution_criteria for node in artifact.nodes)


def test_assumption_analyst_live_extracts_a_ledger(case: Case) -> None:
    _seed_recommendation(case)
    critique_case_evidence(case, as_of=date.today())

    artifact = invoke(
        case,
        "assumption_analyst",
        InvokeTask(
            task_id="T-assumptions-live",
            assignment=(
                "Extract the load-bearing assumptions the case is currently resting on.\n"
                "Every assumption needs a testable claim and a probability estimate."
            ),
            output_artifact_type="assumption_batch",
            timeout_s=TIMEOUT_S,
        ),
        backend=CursorCLIBackend(),
    )

    assert isinstance(artifact, AssumptionBatch)
    assert artifact.no_assumptions_found is False
    assert artifact.records
    assert all(record.estimate is not None for record in artifact.records)


def test_premortem_live_names_specific_failure_modes(case: Case) -> None:
    _seed_recommendation(case)

    artifact = invoke(
        case,
        "premortem",
        InvokeTask(
            task_id="T-premortem-live",
            assignment=(
                "Assume the recommendation was followed and it failed badly. Write the "
                "explanation of why. Each failure mode needs a mechanism and at least one "
                "concrete leading indicator."
            ),
            output_artifact_type="premortem_report",
            timeout_s=TIMEOUT_S,
        ),
        backend=CursorCLIBackend(),
    )

    assert isinstance(artifact, PreMortemReport)
    assert len(artifact.failure_modes) >= 3
    assert all(mode.leading_indicators for mode in artifact.failure_modes)


def test_director_track_b_live_reaches_its_own_conclusion(case: Case) -> None:
    artifact = invoke(
        case,
        "director",
        InvokeTask(
            task_id="T-track-b-live",
            assignment=(
                "Form an independent view of what the evidence supports.\n"
                "Reason from the evidence upward. Every rationale item must cite E-/A- IDs."
            ),
            output_artifact_type="preliminary_recommendation",
            mode="preliminary_recommendation",
            timeout_s=TIMEOUT_S,
        ),
        backend=CursorCLIBackend(),
        variant="b",
    )

    assert isinstance(artifact, PreliminaryRecommendation)
    assert artifact.preferred_alternative
    assert artifact.rationale
