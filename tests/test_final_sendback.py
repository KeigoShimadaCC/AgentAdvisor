"""Tests for final-gate send-back (SPEC-028).

These tests run the full pipeline in a worker subprocess with
``AGENTADVISOR_BACKEND=stub`` so no live model calls are made.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from orchestrator.artifacts import (
    FinalApproval,
    FinalDecision,
    FramingApproval,
    FramingDecision,
)
from orchestrator.case_store import load_case
from orchestrator.control import (
    RevisionCapReached,
    WrongStage,
    approve_framing,
    new_case,
    request_final_revision,
)
from orchestrator.state_machine import (
    MAX_FINAL_REVISIONS,
    CaseStage,
    load_case_state,
)

_RAW_PROMPT = "I have $50k and want semiconductor exposure. Nvidia or ETF?"


@pytest.fixture
def control_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Set up isolated env vars for stub-backend worker subprocesses."""
    cases_root = tmp_path / "cases"
    runtime = tmp_path / "runtime"
    memory = tmp_path / "memory"
    cases_root.mkdir()
    runtime.mkdir()
    memory.mkdir()

    monkeypatch.setenv("AGENTADVISOR_BACKEND", "stub")
    monkeypatch.setenv("AGENTADVISOR_CASES_ROOT", str(cases_root))
    monkeypatch.setenv("AGENTADVISOR_RUNTIME_ROOT", str(runtime))
    monkeypatch.setenv("AGENTADVISOR_MEMORY_ROOT", str(memory))

    return cases_root


def _park_at_final(control_env: Path) -> str:
    """Create a case and run it to the final approval gate."""
    case_id = new_case(
        _RAW_PROMPT,
        slug="final-sendback",
        budget_profile="small",
        cases_root=control_env,
    )
    approval = FramingApproval(
        decision=FramingDecision.APPROVE,
        approved_by="test-user",
        approved_at=datetime.now(UTC),
    )
    approve_framing(case_id, approval, cases_root=control_env)
    return case_id


class TestFinalRevision:
    def test_routes_to_synthesis_and_re_parks(self, control_env: Path) -> None:
        case_id = _park_at_final(control_env)

        request_final_revision(
            case_id,
            note="I want more emphasis on downside scenarios.",
            cases_root=control_env,
        )

        case = load_case(case_id, cases_root=control_env)
        state = load_case_state(case)
        assert state.stage is CaseStage.AWAITING_FINAL_APPROVAL
        assert state.final_revisions == 1

    def test_final_approval_artifact_written(self, control_env: Path) -> None:
        case_id = _park_at_final(control_env)

        request_final_revision(
            case_id,
            note="I want more emphasis on downside scenarios.",
            cases_root=control_env,
        )

        case = load_case(case_id, cases_root=control_env)
        approval = case.read_artifact(FinalApproval)
        assert approval.decision is FinalDecision.REVISE
        assert "downside" in approval.note

    def test_user_note_in_synthesis_workspace(self, control_env: Path) -> None:
        case_id = _park_at_final(control_env)

        request_final_revision(
            case_id,
            note="I want more emphasis on downside scenarios.",
            cases_root=control_env,
        )

        case = load_case(case_id, cases_root=control_env)
        # The synthesis re-run uses a task_id ending in -fr-1 (final_revisions=1).
        agents_dir = case.root / "agents"
        synth_workspaces = [
            p
            for p in agents_dir.iterdir()
            if p.name.startswith("synthesizer--T-synthesis-") and p.name.endswith("-fr-1")
        ]
        assert len(synth_workspaces) == 1, (
            f"Expected exactly one synthesis revision workspace, found: "
            f"{[p.name for p in synth_workspaces]}"
        )
        synth_workspace = synth_workspaces[0]

        task_yaml = synth_workspace / "task.yaml"
        assert task_yaml.exists()
        task_text = task_yaml.read_text(encoding="utf-8")
        assert "downside" in task_text

    def test_audit_event_recorded(self, control_env: Path) -> None:
        case_id = _park_at_final(control_env)

        request_final_revision(
            case_id,
            note="I want more emphasis on downside scenarios.",
            cases_root=control_env,
        )

        case = load_case(case_id, cases_root=control_env)
        audit_lines = (case.root / "audit.jsonl").read_text(encoding="utf-8").strip().split("\n")
        revision_events = [
            json.loads(line)
            for line in audit_lines
            if json.loads(line).get("event_type") == "final_revision_requested"
        ]
        assert len(revision_events) == 1
        payload = revision_events[0]["payload"]
        assert payload["final_revisions"] == 1
        assert payload["note_length"] > 0


class TestFinalRevisionCap:
    def test_second_request_refused(self, control_env: Path) -> None:
        case_id = _park_at_final(control_env)

        # First revision (final_revisions 0 -> 1).
        request_final_revision(
            case_id,
            note="First revision request.",
            cases_root=control_env,
        )

        case = load_case(case_id, cases_root=control_env)
        state = load_case_state(case)
        assert state.final_revisions == MAX_FINAL_REVISIONS

        # Second revision should be refused.
        with pytest.raises(RevisionCapReached, match="final revision cap"):
            request_final_revision(
                case_id,
                note="Second revision request.",
                cases_root=control_env,
            )


class TestFinalWrongStage:
    def test_wrong_stage_raises_at_framing_gate(self, control_env: Path) -> None:
        case_id = new_case(
            _RAW_PROMPT,
            slug="final-wrong",
            budget_profile="small",
            cases_root=control_env,
        )

        # Still at AWAITING_FRAMING_APPROVAL.
        with pytest.raises(WrongStage, match="awaiting_final_approval"):
            request_final_revision(
                case_id,
                note="Some note.",
                cases_root=control_env,
            )

    def test_wrong_stage_raises_at_done(self, control_env: Path) -> None:
        case_id = _park_at_final(control_env)

        # Approve final to reach DONE.
        from orchestrator.control import approve_final

        approval = FinalApproval(
            decision=FinalDecision.ACCEPT,
            approved_by="test-user",
            approved_at=datetime.now(UTC),
        )
        approve_final(case_id, approval, cases_root=control_env)

        with pytest.raises(WrongStage, match="awaiting_final_approval"):
            request_final_revision(
                case_id,
                note="Some note.",
                cases_root=control_env,
            )
