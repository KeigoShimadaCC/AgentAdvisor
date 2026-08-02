#!/usr/bin/env python3
"""Generate the two committed fixture cases for SPEC-032.

Runs the PipelineStubBackend end-to-end to produce a completed case, then
copies/sanitizes it into tests/fixtures/cases/case-fixture-001/.  A second
case is parked at awaiting_framing_approval for case-fixture-002-parked/.

Usage:
    .venv/bin/python scripts/generate_fixtures.py
"""

from __future__ import annotations

import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.artifacts import (  # noqa: E402
    AuditEvent,
    ClarificationQuestion,
    EvidenceRecord,
    FinalApproval,
    FinalDecision,
    IntakeField,
    IntakeRecord,
    ModelStability,
    ObjectionRecord,
    ObjectionResolutionStatus,
    ReviewDefect,
    ReviewDefectType,
    ReviewOutcome,
    ReviewReport,
    ThesisRevision,
    ThesisTrigger,
)
from orchestrator.budget import BudgetConfig  # noqa: E402
from orchestrator.case_store import Case, create_case  # noqa: E402
from orchestrator.invoke_role import clear_cross_field_validation_hooks  # noqa: E402
from orchestrator.memory import MemoryStore  # noqa: E402
from orchestrator.pipeline import run  # noqa: E402
from orchestrator.state_machine import (  # noqa: E402
    CaseStage,
    save_case_state,
)
from orchestrator.stub_backend import PipelineStubBackend  # noqa: E402

FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "cases"


def _stub_backend_with_failing_review(case: Case):
    """Wrap PipelineStubBackend so the review report fails (review_accepted=False).

    We patch the review_report factory to produce a FAIL outcome with defects,
    which makes the case interesting for the fixture.
    """
    import orchestrator.stub_backend as sb  # noqa: PLC0415

    original_make_review = sb._make_review_report

    def _failing_review(worksheet):
        return ReviewReport(
            outcome=ReviewOutcome.FAIL,
            defects=[
                ReviewDefect(
                    defect_type=ReviewDefectType.FALSE_PRECISION,
                    target_id="E-001",
                    explanation=(
                        "The recommendation states a precise figure without supporting detail."
                    ),
                ),
            ],
            citation_verdicts=[
                # verdicts omitted on fail; defects carry the signal
            ],
        )

    sb._make_review_report = _failing_review
    return original_make_review


def _make_fixture_001() -> None:
    """Completed case with failing review, stability sentinel, open objections, thesis flip."""
    tmp_root = REPO_ROOT / "build" / "fixture-tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    cases_root = tmp_root / "cases"
    cases_root.mkdir(exist_ok=True)
    memory_root = tmp_root / "memory"

    case = create_case("fixture-001", cases_root=cases_root)
    clear_cross_field_validation_hooks()

    original_review = _stub_backend_with_failing_review(case)
    try:
        backend = PipelineStubBackend(case)
        store = MemoryStore(memory_root)

        budget = BudgetConfig(
            max_agent_invocations=25,
            max_concurrent_workers=1,
            max_repair_cycles=1,
            max_research_tasks=8,
            max_high_tier_calls=20,
            max_wall_clock_s=3600,
        )

        state = run(
            case,
            raw_prompt="I have $50k and want semiconductor exposure. Nvidia or ETF?",
            backend=backend,
            budget_config=budget,
            auto_approve=True,
            memory_store=store,
        )
    finally:
        import orchestrator.stub_backend as sb  # noqa: PLC0415

        sb._make_review_report = original_review
        clear_cross_field_validation_hooks()

    assert state.stage is CaseStage.DONE, f"Expected DONE, got {state.stage}"

    # Now post-process: set review_accepted=False in state, add a thesis flip,
    # and ensure the stability sentinel is present.
    # The stub backend's final recommendation already has model_stability with
    # runs_total=2, runs_supporting=1.  We want the sentinel (runs_total=1,
    # runs_supporting=0).  Rewrite the final recommendation.
    from orchestrator.artifacts import FinalRecommendation  # noqa: PLC0415

    final = case.read_artifact(FinalRecommendation)
    final_with_sentinel = final.model_copy(
        update={
            "model_stability": ModelStability(
                share_of_sensitivity_runs_supporting_recommendation=0.0,
                runs_total=1,
                runs_supporting=0,
            )
        }
    )
    case.write_artifact(final_with_sentinel)

    # Add a thesis flip: revision 1 = staged_entry, revision 2 = invest_nvda_now (changed=True),
    # revision 3 = staged_entry (changed=True, flip back).
    revisions = sorted(case.list_artifacts(ThesisRevision), key=lambda r: r.revision)
    now = datetime.now(UTC)
    # If only 2 revisions exist, add a 3rd that flips back.
    if len(revisions) >= 2:
        last = revisions[-1]
        flip_back = ThesisRevision(
            revision=last.revision + 1,
            trigger=ThesisTrigger.REPAIR,
            preferred_alternative="staged_entry",
            previous_alternative=last.preferred_alternative,
            changed=True,
            rationale_digest=["Repair cycle re-examined evidence; reverted to staged entry."],
            changed_because_evidence_ids=["E-002"],
            recommendation_confidence=0.62,
            evidence_confidence=0.55,
            recorded_at=now,
        )
        case.write_artifact(flip_back)

    # Set review_accepted=False (the review failed, so the case is done but review not accepted).
    state = state.model_copy(update={"review_accepted": False})
    save_case_state(case, state)

    # Ensure a disclosure record exists (the happy-path stub run may not produce one).
    from orchestrator.artifacts import DisclosureRecord, StopReason  # noqa: PLC0415

    if not case.list_artifacts(DisclosureRecord):
        case.write_artifact(
            DisclosureRecord(
                stop_reasons=(
                    StopReason.NO_CRITICAL_EVIDENCE_GAPS_REMAIN,
                    StopReason.RECOMMENDATION_STABLE_ACROSS_SENSITIVITY_RANGES,
                    StopReason.EXPECTED_VALUE_OF_MORE_RESEARCH_LOW,
                ),
                exhausted_dimensions=("research_tasks",),
            )
        )

    # Ensure a final approval artifact exists.
    if not case.list_artifacts(FinalApproval):
        case.write_artifact(
            FinalApproval(
                decision=FinalDecision.ACCEPT,
                approved_by="auto-approve",
                approved_at=datetime.now(UTC),
            )
        )

    # Add a few more audit events for effort counting if sparse.
    case.audit(
        AuditEvent(
            ts=now,
            actor="orchestrator",
            event_type="case_finalized",
            payload={"review_accepted": False},
        )
    )

    # Ensure there's at least one open objection.
    objections = case.list_artifacts(ObjectionRecord)
    has_open = any(o.resolution_status is ObjectionResolutionStatus.OPEN for o in objections)
    if not has_open and objections:
        # Rewrite the first objection as open.
        first = objections[0]
        case.write_artifact(
            first.model_copy(update={"resolution_status": ObjectionResolutionStatus.OPEN})
        )

    # Copy to fixtures, excluding agent workspaces and memory.
    dest = FIXTURE_ROOT / "case-fixture-001"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    _copy_case(case.root, dest)

    # Render final recommendation markdown into outputs.
    from orchestrator.artifacts import DisclosureRecord as _DisclosureRecord
    from orchestrator.artifacts import PreMortemReport as _PreMortemReport
    from orchestrator.render import write_final_recommendation_markdown  # noqa: PLC0415

    evidence = case.list_artifacts(EvidenceRecord)
    disclosure = case.list_artifacts(_DisclosureRecord)
    disclosure_record = disclosure[0] if disclosure else None
    premortem = case.list_artifacts(_PreMortemReport)
    premortem_report = premortem[0] if premortem else None
    write_final_recommendation_markdown(
        dest,
        final_with_sentinel,
        evidence,
        disclosure_record=disclosure_record,
        user_supplied_inputs=[],
        premortem_report=premortem_report,
    )

    print(f"Fixture 001 written to {dest}")


def _make_fixture_002_parked() -> None:
    """Case parked at awaiting_framing_approval with clarification questions."""
    tmp_root = REPO_ROOT / "build" / "fixture-tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    cases_root = tmp_root / "cases"
    memory_root = tmp_root / "memory"

    case = create_case("fixture-002-parked", cases_root=cases_root)
    clear_cross_field_validation_hooks()
    try:
        backend = PipelineStubBackend(case)
        store = MemoryStore(memory_root)

        budget = BudgetConfig(
            max_agent_invocations=25,
            max_concurrent_workers=1,
            max_repair_cycles=1,
            max_research_tasks=8,
            max_high_tier_calls=20,
            max_wall_clock_s=3600,
        )

        # Run without auto_approve: it will halt at awaiting_framing_approval.
        state = run(
            case,
            raw_prompt="I have $50k and want semiconductor exposure. Nvidia or ETF?",
            backend=backend,
            budget_config=budget,
            auto_approve=False,
            memory_store=store,
        )
    finally:
        clear_cross_field_validation_hooks()

    assert state.stage is CaseStage.AWAITING_FRAMING_APPROVAL, (
        f"Expected AWAITING_FRAMING_APPROVAL, got {state.stage}"
    )

    # Rewrite the intake record to include clarification questions.
    intake = case.read_artifact(IntakeRecord)
    intake_with_clarifications = intake.model_copy(
        update={
            "decision_question": None,  # must be None for the clarification to target it
            "clarification_questions": [
                ClarificationQuestion(
                    question_id="Q-1",
                    resolves_field=IntakeField.DECISION_QUESTION,
                    question=(
                        "Are you asking about a one-time $50k investment or ongoing contributions?"
                    ),
                    materiality_reason=(
                        "The staging strategy differs for a lump sum vs periodic contributions."
                    ),
                ),
                ClarificationQuestion(
                    question_id="Q-2",
                    resolves_field=IntakeField.DEADLINE,
                    question="By when do you need to make this decision?",
                    materiality_reason=(
                        "The deadline determines whether we can wait for the next earnings report."
                    ),
                ),
            ],
        }
    )
    case.write_artifact(intake_with_clarifications)

    dest = FIXTURE_ROOT / "case-fixture-002-parked"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    _copy_case(case.root, dest)

    print(f"Fixture 002-parked written to {dest}")


def _copy_case(src: Path, dest: Path) -> None:
    """Copy a case directory, excluding agent workspace contents but keeping dirs."""
    for item in src.iterdir():
        if item.name == "agents":
            # Keep the directory (required layout) but skip workspace archives.
            (dest / "agents").mkdir(exist_ok=True)
            continue
        if item.name == "analysis":
            # Copy analysis results YAML but not the model.py scripts.
            dest_analysis = dest / "analysis"
            dest_analysis.mkdir(exist_ok=True)
            for analysis_item in item.iterdir():
                if analysis_item.is_dir():
                    # Copy only results.yaml from each analysis subdirectory.
                    results = analysis_item / "results.yaml"
                    if results.exists():
                        sub = dest_analysis / analysis_item.name
                        sub.mkdir(exist_ok=True)
                        shutil.copy2(results, sub / "results.yaml")
                elif analysis_item.suffix in (".yaml", ".yml"):
                    shutil.copy2(analysis_item, dest_analysis / analysis_item.name)
            continue
        if item.is_dir():
            shutil.copytree(item, dest / item.name, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest / item.name)


def main() -> int:
    FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
    _make_fixture_001()
    _make_fixture_002_parked()
    # Clean up temp.
    tmp_root = REPO_ROOT / "build" / "fixture-tmp"
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
