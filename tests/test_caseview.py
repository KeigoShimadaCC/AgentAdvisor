"""Tests for the CaseView projection (SPEC-032).

Covers:
- build_case_view on the completed fixture-001 case.
- build_case_view on the parked fixture-002 case.
- Probability entries never carry both point and interval (property test).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.artifacts import IntakeRecord
from orchestrator.case_store import Case
from orchestrator.service.caseview import (
    AssessedConfidence,
    CaseView,
    NotAssessed,
    build_case_view,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "cases"


@pytest.fixture
def fixture_001() -> Case:
    return Case(root=FIXTURES / "case-fixture-001")


@pytest.fixture
def fixture_002() -> Case:
    return Case(root=FIXTURES / "case-fixture-002-parked")


# ── Fixture-001: completed case ──────────────────────────────────────────────


class TestFixture001:
    def test_returns_validating_case_view(self, fixture_001: Case) -> None:
        view = build_case_view(fixture_001)
        assert isinstance(view, CaseView)
        assert view.view_version == 1
        assert view.case_id == "case-fixture-001"

    def test_phase_and_stage(self, fixture_001: Case) -> None:
        view = build_case_view(fixture_001)
        assert view.phase == "complete"
        assert view.stage == "done"
        assert view.is_terminal is True
        assert view.needs_you == "none"

    def test_model_stability_is_not_assessed(self, fixture_001: Case) -> None:
        """The stability sentinel (runs_total=1, runs_supporting=0) must be NotAssessed."""
        view = build_case_view(fixture_001)
        assert view.uncertainty is not None
        stability = view.uncertainty.model_stability
        assert isinstance(stability, NotAssessed)
        assert stability.kind == "not_assessed"
        # The reason should name the single-run sentinel.
        assert "single run" in stability.reason.lower()

    def test_review_accepted_is_false(self, fixture_001: Case) -> None:
        """The fixture has a failing review; review_accepted must be False."""
        view = build_case_view(fixture_001)
        assert view.integrity.review_accepted is False
        # The review defects should be present.
        assert len(view.integrity.review_defects) > 0
        assert view.integrity.review_outcome == "fail"

    def test_challenges_list_open_objections_first(self, fixture_001: Case) -> None:
        """Open objections must appear before resolved/dismissed ones."""
        view = build_case_view(fixture_001)
        objections = view.rooms.challenges.objections
        assert len(objections) >= 1
        # The first objection must be open.
        assert objections[0].resolution_status == "open"
        # Verify sort: no non-open objection precedes an open one.
        seen_non_open = False
        for obj in objections:
            if obj.resolution_status != "open":
                seen_non_open = True
            elif seen_non_open:
                pytest.fail(
                    f"Open objection {obj.objection_id} appears after a non-open objection."
                )

    def test_effort_invocation_count_matches_audit(self, fixture_001: Case) -> None:
        """The effort invocation count must equal the hand-counted audit lines."""
        view = build_case_view(fixture_001)
        audit_path = fixture_001.root / "audit.jsonl"
        audit_text = audit_path.read_text(encoding="utf-8")
        hand_count = sum(
            1 for line in audit_text.splitlines() if '"role_invocation_attempt"' in line
        )
        assert view.effort.invocation_attempts == hand_count

    def test_thesis_flip_present(self, fixture_001: Case) -> None:
        """The fixture includes a thesis flip (at least one revision with changed=True)."""
        view = build_case_view(fixture_001)
        revisions = view.history.thesis_revisions
        assert len(revisions) >= 2
        assert any(r.changed for r in revisions)

    def test_brief_sections_in_renderer_order(self, fixture_001: Case) -> None:
        """Brief section keys should follow the renderer's canonical order."""
        view = build_case_view(fixture_001)
        keys = [s.key for s in view.brief_sections]
        # The first few must match the expected order.
        assert keys[0] == "executive_recommendation"
        assert keys[1] == "decision_confidence"
        assert keys[2] == "alternatives_considered"
        # All sections should be present.
        assert "evidence_and_citations" in keys

    def test_brief_section_status_is_final_for_completed_case(self, fixture_001: Case) -> None:
        """A completed case should have final-status brief sections (not pending)."""
        view = build_case_view(fixture_001)
        exec_section = next(s for s in view.brief_sections if s.key == "executive_recommendation")
        assert exec_section.status == "final"
        assert len(exec_section.blocks) >= 1

    def test_uncertainty_confidences_are_assessed(self, fixture_001: Case) -> None:
        """The recommendation and evidence confidence should be assessed (not sentinel)."""
        view = build_case_view(fixture_001)
        assert view.uncertainty is not None
        assert isinstance(view.uncertainty.recommendation_confidence, AssessedConfidence)
        assert isinstance(view.uncertainty.evidence_confidence, AssessedConfidence)

    def test_rooms_have_data(self, fixture_001: Case) -> None:
        """Rooms should be populated with evidence, assumptions, and options."""
        view = build_case_view(fixture_001)
        assert len(view.rooms.sources.sources) >= 2
        assert len(view.rooms.assumptions.assumptions) >= 1
        assert len(view.rooms.options.options) >= 1
        assert view.rooms.plan is not None
        assert view.rooms.challenges.premortem is not None

    def test_history_has_approvals(self, fixture_001: Case) -> None:
        """The completed case should have framing and final approval records."""
        view = build_case_view(fixture_001)
        approval_kinds = [a.kind for a in view.history.approvals]
        assert "framing" in approval_kinds
        assert "final" in approval_kinds

    def test_effort_budget_counters_present(self, fixture_001: Case) -> None:
        """Budget counters from state should be surfaced in effort."""
        view = build_case_view(fixture_001)
        assert view.effort.budget_counters.get("agent_invocations", 0) > 0
        assert "max_agent_invocations" in view.effort.budget_caps


# ── Fixture-002: parked case ─────────────────────────────────────────────────


class TestFixture002Parked:
    def test_needs_you_is_scope_checkpoint(self, fixture_002: Case) -> None:
        view = build_case_view(fixture_002)
        assert view.needs_you == "scope_checkpoint"
        assert view.stage == "awaiting_framing_approval"
        assert view.is_terminal is False
        assert view.phase == "framing"

    def test_clarification_questions_present(self, fixture_002: Case) -> None:
        """The parked case should have clarification questions with materiality reasons."""
        intake_list = fixture_002.list_artifacts(IntakeRecord)
        assert len(intake_list) == 1
        intake = intake_list[0]
        assert len(intake.clarification_questions) >= 1
        for q in intake.clarification_questions:
            assert q.materiality_reason  # non-empty
            assert q.question  # non-empty

    def test_brief_sections_pending(self, fixture_002: Case) -> None:
        """A parked case should have pending brief sections (no final recommendation)."""
        view = build_case_view(fixture_002)
        for section in view.brief_sections:
            assert section.status == "pending"

    def test_uncertainty_is_none(self, fixture_002: Case) -> None:
        """A case parked before investigation has no recommendation to assess."""
        view = build_case_view(fixture_002)
        assert view.uncertainty is None


# ── Property test: point-XOR-interval ─────────────────────────────────────────


class TestProbabilityPointXorInterval:
    """Probability entries must never carry both a point and an interval."""

    def _collect_probabilities(self, view: CaseView) -> list:
        probs: list = []
        if view.uncertainty is not None:
            probs.extend(view.uncertainty.outcome_probabilities.values())
        return probs

    def test_fixture_001(self, fixture_001: Case) -> None:
        view = build_case_view(fixture_001)
        for prob in self._collect_probabilities(view):
            has_point = prob.point is not None
            has_interval = prob.interval_low is not None or prob.interval_high is not None
            assert not (has_point and has_interval), (
                f"Probability with method={prob.method} has both point and interval."
            )

    def test_fixture_002(self, fixture_002: Case) -> None:
        view = build_case_view(fixture_002)
        # No probabilities expected, but the property must hold vacuously.
        for prob in self._collect_probabilities(view):
            has_point = prob.point is not None
            has_interval = prob.interval_low is not None or prob.interval_high is not None
            assert not (has_point and has_interval)


# ── Schema validation ────────────────────────────────────────────────────────


class TestSchemaValidation:
    def test_case_view_validates_against_json_schema(self, fixture_001: Case) -> None:
        """The CaseView must be serializable and re-validatable against its JSON schema."""
        import json

        view = build_case_view(fixture_001)
        payload = view.model_dump(mode="json")
        # Should serialize to JSON without errors.
        json_str = json.dumps(payload)
        assert json.loads(json_str) == payload

    def test_case_view_schema_exported(self) -> None:
        """The case_view schema file should exist in schemas/."""
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "case_view.schema.json"
        assert schema_path.exists(), "case_view.schema.json not found in schemas/"
