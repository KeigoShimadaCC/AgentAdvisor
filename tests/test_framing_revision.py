"""Tests for framing revision loop (SPEC-028).

These tests run the full pipeline in a worker subprocess with
``AGENTADVISOR_BACKEND=stub`` so no live model calls are made.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import (
    FramingApproval,
    FramingDecision,
)
from orchestrator.case_store import load_case
from orchestrator.control import (
    RevisionCapReached,
    WrongStage,
    new_case,
    request_framing_revision,
)
from orchestrator.state_machine import (
    MAX_FRAMING_REVISIONS,
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


def _park_at_framing(control_env: Path) -> str:
    """Create a case and run it to the framing approval gate."""
    return new_case(
        _RAW_PROMPT,
        slug="framing-rev",
        budget_profile="small",
        cases_root=control_env,
    )


class TestFramingRevisionEdit:
    def test_edit_reruns_framing_and_increments_counter(self, control_env: Path) -> None:
        case_id = _park_at_framing(control_env)

        request_framing_revision(
            case_id,
            edits={"deadline": "2027-06-30"},
            clarification_answers={},
            cases_root=control_env,
        )

        case = load_case(case_id, cases_root=control_env)
        state = load_case_state(case)
        assert state.stage is CaseStage.AWAITING_FRAMING_APPROVAL
        assert state.framing_revisions == 1

    def test_edits_written_to_approval_artifact(self, control_env: Path) -> None:
        case_id = _park_at_framing(control_env)

        request_framing_revision(
            case_id,
            edits={"deadline": "2027-06-30", "objectives": ["growth"]},
            clarification_answers={},
            cases_root=control_env,
        )

        case = load_case(case_id, cases_root=control_env)
        approval = case.read_artifact(FramingApproval)
        assert approval.decision is FramingDecision.EDIT
        assert approval.edits == {"deadline": "2027-06-30", "objectives": ["growth"]}

    def test_archived_workspace_contains_feedback(self, control_env: Path) -> None:
        case_id = _park_at_framing(control_env)

        request_framing_revision(
            case_id,
            edits={"deadline": "2027-06-30"},
            clarification_answers={},
            cases_root=control_env,
        )

        case = load_case(case_id, cases_root=control_env)
        # The revision run uses task_id T-framing-r1.
        rev_workspace = case.root / "agents" / "director--T-framing-r1"
        assert rev_workspace.exists(), f"Revision workspace not found: {rev_workspace}"

        inputs_dir = rev_workspace / "inputs"
        # framing_feedback.yaml should contain the edits.
        feedback_path = inputs_dir / "framing_feedback.yaml"
        assert feedback_path.exists(), "framing_feedback.yaml not in revision workspace inputs"
        feedback = yaml.safe_load(feedback_path.read_text(encoding="utf-8"))
        assert feedback["kind"] == "framing_feedback"
        assert feedback["edits"] == {"deadline": "2027-06-30"}

        # The previous decision_spec.yaml should also be in inputs.
        spec_path = inputs_dir / "decision_spec.yaml"
        assert spec_path.exists(), "Previous decision_spec.yaml not in revision workspace inputs"

    def test_new_decision_spec_written(self, control_env: Path) -> None:
        case_id = _park_at_framing(control_env)

        request_framing_revision(
            case_id,
            edits={"deadline": "2027-06-30"},
            clarification_answers={},
            cases_root=control_env,
        )

        case = load_case(case_id, cases_root=control_env)
        # A new decision_spec.yaml should be in shared/.
        spec_path = case.root / "shared" / "decision_spec.yaml"
        assert spec_path.exists()
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        assert "question" in spec

    def test_audit_event_recorded(self, control_env: Path) -> None:
        case_id = _park_at_framing(control_env)

        request_framing_revision(
            case_id,
            edits={"deadline": "2027-06-30"},
            clarification_answers={},
            cases_root=control_env,
        )

        case = load_case(case_id, cases_root=control_env)
        audit_lines = (case.root / "audit.jsonl").read_text(encoding="utf-8").strip().split("\n")
        revision_events = [
            json.loads(line)
            for line in audit_lines
            if json.loads(line).get("event_type") == "framing_revision_requested"
        ]
        assert len(revision_events) == 1
        payload = revision_events[0]["payload"]
        assert payload["decision"] == "edit"
        assert "deadline" in payload["edited_fields"]
        assert payload["framing_revisions"] == 1


class TestFramingRevisionClarifications:
    def test_answer_clarifications_reruns_framing(self, control_env: Path) -> None:
        case_id = _park_at_framing(control_env)

        request_framing_revision(
            case_id,
            edits={},
            clarification_answers={"deadline": "2027-03-15"},
            cases_root=control_env,
        )

        case = load_case(case_id, cases_root=control_env)
        state = load_case_state(case)
        assert state.stage is CaseStage.AWAITING_FRAMING_APPROVAL
        assert state.framing_revisions == 1

        approval = case.read_artifact(FramingApproval)
        assert approval.decision is FramingDecision.ANSWER_CLARIFICATIONS
        assert approval.clarification_answers == {"deadline": "2027-03-15"}

    def test_clarification_answers_projected_to_workspace(self, control_env: Path) -> None:
        case_id = _park_at_framing(control_env)

        request_framing_revision(
            case_id,
            edits={},
            clarification_answers={"deadline": "2027-03-15"},
            cases_root=control_env,
        )

        case = load_case(case_id, cases_root=control_env)
        rev_workspace = case.root / "agents" / "director--T-framing-r1"
        feedback_path = rev_workspace / "inputs" / "framing_feedback.yaml"
        feedback = yaml.safe_load(feedback_path.read_text(encoding="utf-8"))
        assert feedback["clarification_answers"] == {"deadline": "2027-03-15"}

    def test_unknown_intake_field_rejected(self, control_env: Path) -> None:
        case_id = _park_at_framing(control_env)

        with pytest.raises(ValueError, match="Unknown IntakeField"):
            request_framing_revision(
                case_id,
                edits={},
                clarification_answers={"nonexistent_field": "value"},
                cases_root=control_env,
            )


class TestFramingRevisionCap:
    def test_cap_enforced(self, control_env: Path) -> None:
        case_id = _park_at_framing(control_env)

        # First revision (framing_revisions 0 -> 1).
        request_framing_revision(
            case_id,
            edits={"deadline": "2027-06-30"},
            clarification_answers={},
            cases_root=control_env,
        )

        # Second revision (framing_revisions 1 -> 2).
        request_framing_revision(
            case_id,
            edits={"deadline": "2027-12-31"},
            clarification_answers={},
            cases_root=control_env,
        )

        case = load_case(case_id, cases_root=control_env)
        state = load_case_state(case)
        assert state.framing_revisions == MAX_FRAMING_REVISIONS

        # Third revision should be refused.
        with pytest.raises(RevisionCapReached, match="framing revision cap"):
            request_framing_revision(
                case_id,
                edits={"deadline": "2028-01-01"},
                clarification_answers={},
                cases_root=control_env,
            )


class TestFramingWrongStage:
    def test_wrong_stage_raises(self, control_env: Path) -> None:
        case_id = _park_at_framing(control_env)

        # Approve framing to move past the gate.
        from orchestrator.artifacts import FramingApproval as FA
        from orchestrator.control import approve_framing

        approval = FA(
            decision=FramingDecision.APPROVE,
            approved_by="test-user",
            approved_at=datetime.now(UTC),
        )
        approve_framing(case_id, approval, cases_root=control_env)

        # Now at AWAITING_FINAL_APPROVAL, not AWAITING_FRAMING_APPROVAL.
        with pytest.raises(WrongStage, match="awaiting_framing_approval"):
            request_framing_revision(
                case_id,
                edits={"deadline": "2027-06-30"},
                clarification_answers={},
                cases_root=control_env,
            )
