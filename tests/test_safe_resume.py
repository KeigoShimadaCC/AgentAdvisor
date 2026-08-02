"""SPEC-030: Safe resume and delivery-integrity persistence tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from orchestrator.artifacts import (
    CitationVerdict,
    EvidenceBatch,
    EvidenceRecord,
    FinalRecommendation,
    Level,
    ObjectionRecord,
    ReviewDefect,
    ReviewDefectType,
    ReviewOutcome,
    ReviewReport,
    SourceType,
    TaskRecord,
    TaskRole,
    TaskStatus,
    ThesisRevision,
)
from orchestrator.artifacts.yaml_io import dump_model_to_yaml_text, load_model_from_yaml_text
from orchestrator.backend import ResultStatus, RoleInvocation, RoleResult, TokenUsage
from orchestrator.budget import BudgetConfig
from orchestrator.case_store import Case, create_case
from orchestrator.invoke_role import clear_cross_field_validation_hooks
from orchestrator.memory import MemoryStore
from orchestrator.pipeline import prepare_resume, run
from orchestrator.state_machine import (
    CaseStage,
    CaseState,
    load_case_state,
    save_case_state,
)
from orchestrator.stub_backend import PipelineStubBackend
from orchestrator.task_graph import TaskGraph
from orchestrator.unpack import unpack_evidence_batch

_RAW_PROMPT = "I have $50k and want semiconductor exposure. Nvidia or ETF?"


# ── helpers ──────────────────────────────────────────────────────────────────


def _ok_result() -> RoleResult:
    return RoleResult(
        status=ResultStatus.OK,
        result_text=None,
        session_id="stub-session",
        request_id="stub-req",
        duration_ms=10,
        usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
        raw_stdout="{}",
        raw_stderr="",
        cli_version="stub-1.0",
    )


def _audit_events(case: Case) -> list[dict[str, Any]]:
    lines = (case.root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    return [yaml.safe_load(line) for line in lines if line]


def _budget() -> BudgetConfig:
    return BudgetConfig(
        max_agent_invocations=60,
        max_concurrent_workers=2,
        max_repair_cycles=1,
        max_research_tasks=12,
        max_high_tier_calls=30,
        max_wall_clock_s=3600,
    )


@pytest.fixture
def env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    cases_root = tmp_path / "cases"
    runtime = tmp_path / "runtime"
    memory = tmp_path / "memory"
    monkeypatch.setenv("AGENTADVISOR_RUNTIME_ROOT", str(runtime))
    monkeypatch.setenv("AGENTADVISOR_MEMORY_ROOT", str(memory))
    clear_cross_field_validation_hooks()
    yield cases_root
    clear_cross_field_validation_hooks()


# ── 1. Orphan reconciliation ─────────────────────────────────────────────────


def _make_task(task_id: str, status: TaskStatus = TaskStatus.PLANNED) -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        role=TaskRole.RESEARCHER,
        question=f"question-{task_id}",
        why_it_matters=f"why-{task_id}",
        expected_information_gain=Level.HIGH,
        materiality=Level.HIGH,
        probability_of_changing_conclusion=0.7,
        estimated_cost=1.0,
        inputs=["decision_spec"],
        required_output="evidence_batch",
        completion_criteria="done",
        status=status,
        priority="high",
        priority_score=20,
        priority_rationale="test",
    )


def test_prepare_resume_resets_active_tasks_and_audits(env: Path) -> None:
    """Simulated crash mid-investigation: two tasks active, no worker."""
    case = create_case("orphan-reset", cases_root=env)

    # Build a task graph with two ACTIVE tasks (simulating a crash mid-dispatch).
    graph = TaskGraph(case)
    graph.add_tasks(
        [
            _make_task("T-001", status=TaskStatus.ACTIVE),
            _make_task("T-002", status=TaskStatus.ACTIVE),
        ]
    )
    # Also add a COMPLETED task to ensure it is NOT reset.
    graph.add_tasks([_make_task("T-003", status=TaskStatus.COMPLETED)])

    # Set state to investigation so prepare_resume sees an active stage.
    now = datetime.now(UTC)
    state = CaseState(
        case_id=case.root.name,
        stage=CaseStage.INVESTIGATION,
        framing_approved=True,
        created_at=now,
        updated_at=now,
    )
    save_case_state(case, state)

    report = prepare_resume(case)

    assert sorted(report.reset_task_ids) == ["T-001", "T-002"]
    assert report.was_interrupted is True

    t1 = case.read_artifact(TaskRecord, "T-001")
    t2 = case.read_artifact(TaskRecord, "T-002")
    t3 = case.read_artifact(TaskRecord, "T-003")
    assert t1.status is TaskStatus.PLANNED
    assert t2.status is TaskStatus.PLANNED
    assert t3.status is TaskStatus.COMPLETED

    events = _audit_events(case)
    reset_events = [e for e in events if e["event_type"] == "task_reset_on_resume"]
    assert len(reset_events) == 1
    assert sorted(reset_events[0]["payload"]["task_ids"]) == ["T-001", "T-002"]


# ── 2. Archive collisions ────────────────────────────────────────────────────


def test_archive_collision_produces_rerun_suffix(env: Path) -> None:
    """Re-running a stage with already-archived workspace produces --rerun-1."""
    case = create_case("archive-collision", cases_root=env)
    workspace = env / "ws-source"
    (workspace / "outputs").mkdir(parents=True)
    (workspace / "outputs" / "evidence_batch.yaml").write_text("test", encoding="utf-8")

    first = case.archive_agent_workspace("researcher", "T-004", workspace)
    assert first == case.root / "agents" / "researcher--T-004"
    assert first.exists()

    # Second archive to the same role+task_id should get --rerun-1.
    second = case.archive_agent_workspace("researcher", "T-004", workspace)
    assert second == case.root / "agents" / "researcher--T-004--rerun-1"
    assert second.exists()

    # Third archive should get --rerun-2.
    third = case.archive_agent_workspace("researcher", "T-004", workspace)
    assert third == case.root / "agents" / "researcher--T-004--rerun-2"
    assert third.exists()

    # The case did not fail — all three archives coexist.
    assert (case.root / "agents").is_dir()


# ── 3. Idempotent unpack ─────────────────────────────────────────────────────


def _evidence(evidence_id: str) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        claim="Revenue grew year-over-year",
        source_title="Annual Report",
        publisher="AAA Corp",
        source_url=f"https://example.com/{evidence_id.lower()}",
        source_type=SourceType.REPUTABLE_SECONDARY,
        publication_date=date(2026, 1, 1),
        retrieval_date=date(2026, 1, 2),
        excerpt="Revenue grew by 18%.",
        reliability=Level.HIGH,
        directness=Level.MEDIUM,
        independence_group="aaa-report",
        limitations=["Company-defined segment boundaries."],
        retrieved_by="researcher-market",
    )


def test_re_unpack_evidence_batch_mints_zero_new_ids(env: Path) -> None:
    """Re-executing a stage that already unpacked T-004's evidence mints zero new E- ids."""
    case = create_case("unpack-idempotent", cases_root=env)
    batch = EvidenceBatch(
        task_id="T-004",
        question="Replay probe",
        records=[_evidence("E-777")],
        search_notes="Single-source replay test.",
    )

    first = unpack_evidence_batch(case, batch)
    assert [r.evidence_id for r in first] == ["E-001"]

    counters_path = case.root / "shared" / "counters.yaml"
    counters_before = yaml.safe_load(counters_path.read_text(encoding="utf-8"))

    second = unpack_evidence_batch(case, batch)
    assert [r.evidence_id for r in second] == ["E-001"]

    counters_after = yaml.safe_load(counters_path.read_text(encoding="utf-8"))
    assert counters_after == counters_before

    events = _audit_events(case)
    skip_events = [e for e in events if e["event_type"] == "unpack_skipped_duplicate"]
    assert len(skip_events) == 1
    assert skip_events[0]["payload"]["task_id"] == "T-004"
    assert skip_events[0]["payload"]["artifact_type"] == "evidence_batch"


# ── 4. Delivery integrity (review_accepted) ──────────────────────────────────


class _PassingReviewBackend:
    """Wraps PipelineStubBackend so all final-recommendation claims are cited.

    The stock stub produces a quantitative finding without an E-/A- citation, which
    triggers a BLOCK finding in the verification worksheet and makes the review fail
    even with a PASS report.  This wrapper adds a citation so the review genuinely
    passes and ``review_accepted`` is recorded as ``True``.
    """

    def __init__(self, case: Case) -> None:
        self._inner = PipelineStubBackend(case)

    def run(self, invocation: RoleInvocation) -> RoleResult:
        result = self._inner.run(invocation)
        workspace = invocation.workspace
        task_yaml = workspace / "task.yaml"
        if task_yaml.exists():
            data = yaml.safe_load(task_yaml.read_text())
            if data.get("required_output_schema") == "final_recommendation":
                output_filename = data.get("required_output_filename", "final_recommendation.yaml")
                output_path = workspace / "outputs" / output_filename
                if output_path.exists():
                    rec = load_model_from_yaml_text(
                        FinalRecommendation, output_path.read_text(encoding="utf-8")
                    )
                    fixed = rec.model_copy(
                        update={
                            "quantitative_findings": [
                                "Expected value of staged entry: $11,000 "
                                "based on scenario model [E-001]"
                            ]
                        }
                    )
                    output_path.write_text(dump_model_to_yaml_text(fixed), encoding="utf-8")
        return result


class _FailingReviewBackend:
    """Wraps PipelineStubBackend but returns a FAIL review report."""

    def __init__(self, case: Case) -> None:
        self._inner = PipelineStubBackend(case)

    def run(self, invocation: RoleInvocation) -> RoleResult:
        result = self._inner.run(invocation)
        workspace = invocation.workspace
        task_yaml = workspace / "task.yaml"
        if task_yaml.exists():
            data = yaml.safe_load(task_yaml.read_text())
            if data.get("required_output_schema") == "review_report":
                ws_path = workspace / "inputs" / "verification_worksheet.yaml"
                items: list[Any] = []
                if ws_path.exists():
                    ws = yaml.safe_load(ws_path.read_text(encoding="utf-8"))
                    items = ws.get("items", [])
                fail_report = ReviewReport(
                    outcome=ReviewOutcome.FAIL,
                    defects=[
                        ReviewDefect(
                            defect_type=ReviewDefectType.UNSUPPORTED_CITATION,
                            target_id="case-001-fail",
                            explanation="The cited excerpt does not support the claim as written.",
                        )
                    ],
                    citation_verdicts=[
                        CitationVerdict(
                            item_id=item["item_id"],
                            supported=False,
                            justification=(
                                "The excerpt is about the same topic "
                                "but does not support the magnitude."
                            ),
                        )
                        for item in items
                    ],
                )
                output_filename = data.get("required_output_filename", "review_report.yaml")
                (workspace / "outputs" / output_filename).write_text(
                    dump_model_to_yaml_text(fail_report), encoding="utf-8"
                )
        return result


@pytest.fixture
def completed_case(env: Path) -> Case:
    """Run a full stub pipeline to completion and return the case."""
    case = create_case("review-accepted", cases_root=env)
    store = MemoryStore(env.parent / "memory")
    run(
        case,
        raw_prompt=_RAW_PROMPT,
        backend=_PassingReviewBackend(case),
        budget_config=_budget(),
        auto_approve=True,
        memory_store=store,
    )
    return case


def test_passing_case_records_review_accepted_true(completed_case: Case) -> None:
    state = load_case_state(completed_case)
    assert state.stage is CaseStage.DONE
    assert state.review_accepted is True


def test_failing_review_after_retry_reaches_done_with_false(env: Path) -> None:
    """A case whose review fails after retry reaches done with review_accepted: false."""
    case = create_case("review-fail", cases_root=env)
    store = MemoryStore(env.parent / "memory")
    run(
        case,
        raw_prompt=_RAW_PROMPT,
        backend=_FailingReviewBackend(case),
        budget_config=_budget(),
        auto_approve=True,
        memory_store=store,
    )

    state = load_case_state(case)
    assert state.stage is CaseStage.DONE
    assert state.review_accepted is False


def test_crashed_before_review_reloads_with_none(env: Path) -> None:
    """A case crashed before review reloads with review_accepted: None."""
    case = create_case("crash-before-review", cases_root=env)
    now = datetime.now(UTC)
    state = CaseState(
        case_id=case.root.name,
        stage=CaseStage.SYNTHESIS,
        framing_approved=True,
        created_at=now,
        updated_at=now,
    )
    save_case_state(case, state)

    reloaded = load_case_state(case)
    assert reloaded.review_accepted is None


# ── 5. End-to-end interrupted → resume ───────────────────────────────────────


def test_interrupted_resume_end_to_end(env: Path) -> None:
    """Interrupted → resume on stub backend reaches done with no duplicate ids."""
    case = create_case("e2e-resume", cases_root=env)
    store = MemoryStore(env.parent / "memory")

    # First run: complete the full pipeline.
    run(
        case,
        raw_prompt=_RAW_PROMPT,
        backend=PipelineStubBackend(case),
        budget_config=_budget(),
        auto_approve=True,
        memory_store=store,
    )

    state = load_case_state(case)
    assert state.stage is CaseStage.DONE

    # Record counts before simulating the crash.
    thesis_count_before = len(case.list_artifacts(ThesisRevision))
    evidence_ids_before = {r.evidence_id for r in case.list_artifacts(EvidenceRecord)}
    objection_ids_before = {r.objection_id for r in case.list_artifacts(ObjectionRecord)}

    # Simulate a crash mid-investigation: reset stage and set tasks to ACTIVE.
    crashed_state = state.model_copy(
        update={
            "stage": CaseStage.INVESTIGATION,
            "repair_cycle": 0,
            "synthesis_retries": 0,
            "final_revisions": 0,
            "final_approved": False,
            "review_accepted": None,
            "failure_cause": None,
        }
    )
    save_case_state(case, crashed_state)

    for task in case.list_artifacts(TaskRecord):
        case.write_artifact(task.model_copy(update={"status": TaskStatus.ACTIVE}))

    # Resume: run() calls prepare_resume internally, which resets ACTIVE tasks.
    run(
        case,
        raw_prompt=_RAW_PROMPT,
        backend=PipelineStubBackend(case),
        budget_config=_budget(),
        auto_approve=True,
        memory_store=store,
    )

    resumed_state = load_case_state(case)
    assert resumed_state.stage is CaseStage.DONE

    # No duplicate thesis revisions.
    thesis_after = case.list_artifacts(ThesisRevision)
    assert len(thesis_after) == thesis_count_before

    # No duplicate evidence ids.
    evidence_ids_after = {r.evidence_id for r in case.list_artifacts(EvidenceRecord)}
    assert evidence_ids_after == evidence_ids_before

    # No duplicate objection ids.
    objection_ids_after = {r.objection_id for r in case.list_artifacts(ObjectionRecord)}
    assert objection_ids_after == objection_ids_before

    # Audit log shows task_reset_on_resume from prepare_resume.
    events = _audit_events(case)
    reset_events = [e for e in events if e["event_type"] == "task_reset_on_resume"]
    assert len(reset_events) >= 1
