from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import (
    AnalysisResult,
    AssumptionRecord,
    AuditEvent,
    DecisionSpec,
    EvidenceRecord,
    PreliminaryRecommendation,
)
from orchestrator.backend import (
    CursorCLIBackend,
    ResultStatus,
    RoleInvocation,
    RoleResult,
    StubBackend,
)
from orchestrator.case_store import Case, create_case
from orchestrator.citations import register_citation_hooks
from orchestrator.invoke_role import (
    InvokeTask,
    RoleInvocationFailed,
    clear_cross_field_validation_hooks,
    invoke,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "roles" / "director"
_REF_ID_RE = re.compile(r"\b(?:E|A)-\d+\b")


@pytest.fixture(autouse=True)
def _clear_director_hooks() -> Iterator[None]:
    clear_cross_field_validation_hooks("preliminary_recommendation")
    yield
    clear_cross_field_validation_hooks("preliminary_recommendation")


def _ok_result() -> RoleResult:
    return RoleResult(status=ResultStatus.OK, duration_ms=10, result_text="ok")


def _build_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Case:
    case = create_case("director", cases_root=tmp_path / "cases-root")
    monkeypatch.setenv("AGENTADVISOR_RUNTIME_ROOT", str(tmp_path / "runtime-root"))
    return case


def _load_yaml_dict(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError(f"Fixture must be a mapping: {path}")
    return loaded


def _seed_context(case: Case) -> None:
    payload = _load_yaml_dict(FIXTURES_DIR / "context.yaml")
    decision_payload = payload.get("decision_spec")
    evidence_payload = payload.get("evidence")
    assumptions_payload = payload.get("assumptions")
    analysis_payload = payload.get("analysis")
    if not isinstance(decision_payload, dict):
        raise TypeError("context.yaml decision_spec must be a mapping.")
    if not isinstance(evidence_payload, list):
        raise TypeError("context.yaml evidence must be a list.")
    if not isinstance(assumptions_payload, list):
        raise TypeError("context.yaml assumptions must be a list.")
    if not isinstance(analysis_payload, dict):
        raise TypeError("context.yaml analysis must be a mapping.")

    case.write_artifact(DecisionSpec.model_validate(decision_payload))
    for item in evidence_payload:
        case.write_artifact(EvidenceRecord.model_validate(item))
    for item in assumptions_payload:
        case.write_artifact(AssumptionRecord.model_validate(item))
    case.write_artifact(AnalysisResult.model_validate(analysis_payload))


def _write_output_from_fixture(fixture_name: str) -> Callable[[RoleInvocation], None]:
    payload = (FIXTURES_DIR / fixture_name).read_text(encoding="utf-8")

    def _side_effect(invocation: RoleInvocation) -> None:
        output_path = invocation.workspace / "outputs" / "preliminary_recommendation.yaml"
        output_path.write_text(payload, encoding="utf-8")

    return _side_effect


def _director_task(task_id: str, mode: str) -> InvokeTask:
    return InvokeTask(
        task_id=task_id,
        assignment=(
            "Produce a schema-valid PreliminaryRecommendation for the provided inputs.\n"
            f"mode: {mode}"
        ),
        output_artifact_type="preliminary_recommendation",
        timeout_s=300.0,
        mode=mode,
    )


def _assert_citation_coverage(artifact: PreliminaryRecommendation, case: Case) -> None:
    known_ids = {record.evidence_id for record in case.list_artifacts(EvidenceRecord)} | {
        record.assumption_id for record in case.list_artifacts(AssumptionRecord)
    }

    for reason in artifact.rationale:
        reason_ids = _REF_ID_RE.findall(reason)
        assert reason_ids
        assert all(ref_id in known_ids for ref_id in reason_ids)

    for outcome_name, estimate in artifact.outcome_probabilities.items():
        outcome_ids = _REF_ID_RE.findall(outcome_name)
        adjustment_ids = [ref_id for adj in estimate.adjustments for ref_id in adj.evidence_ids]
        combined_ids = outcome_ids + adjustment_ids
        assert combined_ids
        assert all(ref_id in known_ids for ref_id in combined_ids)


def _attempt_count(case: Case, role: str, task_id: str) -> int:
    lines = (case.root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    events = [AuditEvent.model_validate_json(line) for line in lines]
    return len(
        [
            event
            for event in events
            if event.actor == role
            and event.event_type == "role_invocation_attempt"
            and event.payload.get("task_id") == task_id
        ]
    )


def test_fixture_replay_preliminary_recommendation_with_existing_citations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    _seed_context(case)
    register_citation_hooks()

    backend = StubBackend(
        [_ok_result()],
        side_effects=[_write_output_from_fixture("preliminary_recommendation.valid.yaml")],
    )
    artifact = invoke(
        case,
        "director",
        _director_task("T-140", "preliminary_recommendation"),
        backend=backend,
    )

    assert isinstance(artifact, PreliminaryRecommendation)
    _assert_citation_coverage(artifact, case)


def test_dangling_id_fixture_is_tolerated_when_valid_ids_remain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    _seed_context(case)
    register_citation_hooks()

    backend = StubBackend(
        [_ok_result()],
        side_effects=[_write_output_from_fixture("preliminary_recommendation.dangling.yaml")],
    )

    artifact = invoke(
        case,
        "director",
        _director_task("T-141", "preliminary_recommendation"),
        backend=backend,
    )

    assert isinstance(artifact, PreliminaryRecommendation)


def test_collapsed_confidence_fixture_is_rejected_by_citation_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    _seed_context(case)
    register_citation_hooks()

    backend = StubBackend(
        [_ok_result(), _ok_result(), _ok_result()],
        side_effects=[
            _write_output_from_fixture("preliminary_recommendation.collapsed_confidence.yaml"),
            _write_output_from_fixture("preliminary_recommendation.collapsed_confidence.yaml"),
            _write_output_from_fixture("preliminary_recommendation.collapsed_confidence.yaml"),
        ],
    )

    with pytest.raises(RoleInvocationFailed, match="confidence collapse detected"):
        invoke(
            case,
            "director",
            _director_task("T-142", "preliminary_recommendation"),
            backend=backend,
        )


def test_provisional_thesis_mode_output_is_non_final_with_reversal_uncertainties(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    _seed_context(case)
    register_citation_hooks()

    backend = StubBackend(
        [_ok_result()],
        side_effects=[_write_output_from_fixture("provisional_thesis.yaml")],
    )
    artifact = invoke(
        case,
        "director",
        _director_task("T-143", "provisional_thesis"),
        backend=backend,
    )

    assert isinstance(artifact, PreliminaryRecommendation)
    assert artifact.rationale[0].startswith("NON-FINAL PROVISIONAL THESIS:")
    assert len(artifact.major_risks) >= 3
    assert all("reversal uncertainty" in risk.lower() for risk in artifact.major_risks[:3])


@pytest.mark.live
def test_director_live_mini_run_produces_valid_preliminary_recommendation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    _seed_context(case)
    register_citation_hooks()

    artifact = invoke(
        case,
        "director",
        _director_task("T-144-live", "preliminary_recommendation"),
        backend=CursorCLIBackend(),
    )

    assert isinstance(artifact, PreliminaryRecommendation)
    _assert_citation_coverage(artifact, case)
    assert 1 <= _attempt_count(case, "director", "T-144-live") <= 2
