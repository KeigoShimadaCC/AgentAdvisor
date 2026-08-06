"""SPEC-039 — independent review with blocking authority, and limitations disclosure."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from orchestrator.artifacts import (
    ConfidenceAssessment,
    DecisionSpec,
    Depth,
    EvidenceRecord,
    FinalRecommendation,
    IndependentReview,
    IndependentVerdict,
    Level,
    ModelStability,
    NextAction,
    PreliminaryRecommendation,
    PreMortemReport,
    ProbabilityEstimate,
    ProbabilityMethod,
    Reversibility,
    RiskTolerance,
    SourceType,
    TaskRole,
    ThesisRevision,
    ThesisTrigger,
)
from orchestrator.case_store import Case, create_case
from orchestrator.gates import run_stage_gate
from orchestrator.projection import project
from orchestrator.roles_config import (
    RoleConfigError,
    family,
    load_role_config,
    models_for,
    validate_independent_review_family_diversity,
)


def _prob(point: float) -> ProbabilityEstimate:
    return ProbabilityEstimate(method=ProbabilityMethod.SCENARIO_MODEL, point=point, adjustments=[])


def _final(**overrides: Any) -> FinalRecommendation:
    payload: dict[str, Any] = {
        "recommended_action": "Proceed with a staged allocation.",
        "timing": "Within the quarter.",
        "decision_confidence_summary": "Moderate.",
        "alternatives_considered": [
            {"alternative": "wait", "rank": 2, "rationale": "Lower variance."}
        ],
        "key_reasons": ["Weighted value is highest [E-001]."],
        "scenario_analysis": [
            {"scenario_name": "base", "summary": "Base case.", "probability": _prob(0.6)}
        ],
        "next_actions": [
            NextAction(
                action_id="N-001",
                action="Start",
                owner="user",
                by_date=date(2026, 8, 15),
                first_step="Open the checklist",
                why_now="First step",
            )
        ],
        "outcome_probabilities": {"success": _prob(0.6)},
        "evidence_confidence": ConfidenceAssessment(value=0.6, basis="Mixed"),
        "recommendation_confidence": ConfidenceAssessment(value=0.65, basis="Balanced"),
        "model_stability": ModelStability(
            share_of_sensitivity_runs_supporting_recommendation=0.7,
            runs_total=10,
            runs_supporting=7,
        ),
    }
    payload.update(overrides)
    return FinalRecommendation(**payload)


# ── artifact validation ──────────────────────────────────────────────────────


def test_dissent_requires_a_divergent_conclusion() -> None:
    with pytest.raises(ValidationError, match="divergent_conclusion is required"):
        IndependentReview(
            verdict=IndependentVerdict.DISSENT,
            reasoning="The evidence does not carry this conclusion.",
        )


def test_dissent_with_an_alternative_is_valid() -> None:
    review = IndependentReview(
        verdict=IndependentVerdict.DISSENT,
        reasoning="The evidence does not carry this conclusion.",
        divergent_conclusion="Decline now and revisit after the next filing.",
    )
    assert review.verdict is IndependentVerdict.DISSENT


def test_concur_must_not_carry_a_divergent_conclusion() -> None:
    with pytest.raises(ValidationError, match="must be empty when verdict is 'concur'"):
        IndependentReview(
            verdict=IndependentVerdict.CONCUR,
            reasoning="Same conclusion.",
            divergent_conclusion="Something else",
        )


def test_reservations_may_carry_unsupported_claims_without_a_divergent_conclusion() -> None:
    review = IndependentReview(
        verdict=IndependentVerdict.CONCUR_WITH_RESERVATIONS,
        reasoning="Same action, weaker basis.",
        unsupported_claims=["Demand growth is independently corroborated"],
    )
    assert review.divergent_conclusion is None
    assert len(review.unsupported_claims) == 1


# ── projection: what the reviewer sees, and what it must not ─────────────────


def _seeded_case(tmp_path: Path) -> Case:
    """A case carrying both the packet contents and the reasoning trail."""
    case = create_case("independent", cases_root=tmp_path)
    case.write_artifact(
        DecisionSpec(
            decision_id=case.root.name,
            question="Should I proceed?",
            owner="user",
            deadline=date(2026, 12, 31),
            alternatives=["proceed", "wait"],
            objectives=["return"],
            risk_tolerance=RiskTolerance.MODERATE,
            reversibility=Reversibility.PARTIALLY_REVERSIBLE,
            depth=Depth.STANDARD,
        )
    )
    case.write_artifact(_final())
    case.write_artifact(
        EvidenceRecord(
            evidence_id="E-001",
            claim="Demand grew 18% in 2025.",
            source_title="Annual filing",
            publisher="Registrar",
            source_url="https://example.gov/filing",
            source_type=SourceType.REGULATORY_FILING,
            publication_date=date(2026, 3, 12),
            retrieval_date=date(2026, 7, 29),
            excerpt="Demand grew 18% year over year.",
            reliability=Level.HIGH,
            directness=Level.HIGH,
            independence_group="company_filing",
            limitations=["company-defined market boundary"],
            retrieved_by="researcher-market",
        )
    )
    # The reasoning trail the packet must withhold.
    prelim = PreliminaryRecommendation(
        preferred_alternative="proceed",
        rationale=["Provisional view [E-001]"],
        outcome_probabilities={"success": _prob(0.6)},
        evidence_confidence=ConfidenceAssessment(value=0.5, basis="Thin"),
        recommendation_confidence=ConfidenceAssessment(value=0.5, basis="Provisional"),
        model_stability=ModelStability(
            share_of_sensitivity_runs_supporting_recommendation=1.0,
            runs_total=1,
            runs_supporting=1,
        ),
    )
    case.write_artifact(prelim)
    case.write_artifact(
        ThesisRevision(
            revision=1,
            trigger=ThesisTrigger.PROVISIONAL,
            preferred_alternative="proceed",
            changed=False,
            rationale_digest=["Provisional view"],
            recommendation_confidence=0.5,
            evidence_confidence=0.5,
            recorded_at=datetime(2026, 8, 1, tzinfo=UTC),
        )
    )
    case.write_artifact(
        PreMortemReport(
            horizon="24 months",
            assumed_outcome="The allocation lost money.",
            failure_modes=[
                {
                    "failure_mode": "Demand stalled",
                    "narrative": "Growth did not persist.",
                    "probability": _prob(0.3),
                    "severity": Level.HIGH,
                    "leading_indicators": ["Two consecutive quarters below 5% growth"],
                    "preventive_action": "Stage the entry and hold the second tranche.",
                }
            ],
            most_likely_failure_mode="Demand stalled",
        )
    )
    return case


def test_packet_includes_the_conclusion_and_the_evidence(tmp_path: Path) -> None:
    case = _seeded_case(tmp_path)
    projected = project(case, ["independent_review_packet"], budget_chars=200_000)
    filenames = {artifact.filename for artifact in projected}
    assert "decision_spec.yaml" in filenames
    assert "final_recommendation.yaml" in filenames
    assert any("evidence" in name for name in filenames)


def test_packet_excludes_the_reasoning_trail(tmp_path: Path) -> None:
    """The exclusion is the point of the role: a reviewer that reads the reasoning
    inherits its anchoring."""
    case = _seeded_case(tmp_path)
    projected = project(case, ["independent_review_packet"], budget_chars=200_000)
    blob = "\n".join(artifact.yaml_text for artifact in projected)
    filenames = {artifact.filename for artifact in projected}

    for forbidden in (
        "thesis_revision.yaml",
        "thesis_history.yaml",
        "premortem_report.yaml",
        "track_divergence.yaml",
        "objection",
        "gate_report.yaml",
        "review_report.yaml",
        "preliminary_recommendation.yaml",
    ):
        assert not any(forbidden in name for name in filenames), (
            f"{forbidden} leaked into the independent review packet"
        )

    # Content-level check: the pre-mortem narrative must not appear anywhere.
    assert "Demand stalled" not in blob
    assert "Provisional view" not in blob


def test_reviewer_b_role_config_uses_only_the_packet() -> None:
    config = load_role_config(TaskRole.REVIEWER, "b")
    assert config.projection_include == ("independent_review_packet",)
    assert config.output_artifact_type == "independent_review"


# ── model family diversity ───────────────────────────────────────────────────


@pytest.mark.parametrize("backend", ["cursor", "droid"])
def test_reviewer_b_does_not_share_the_synthesizers_model_family(backend: str) -> None:
    """North star Section 12 names synthesis-vs-review as a diversity boundary.

    It is deliberately not asserted against the Director: only two model families are
    reachable on either backend, so a reviewer differing from both does not exist. The
    Director collision is mitigated by the packet, not by the model table.
    """
    synthesizer = models_for(load_role_config(TaskRole.SYNTHESIZER), backend).default_model
    reviewer_b = models_for(load_role_config(TaskRole.REVIEWER, "b"), backend).default_model
    assert family(synthesizer, canonical=True) != family(reviewer_b, canonical=True)


@pytest.mark.parametrize("backend", ["cursor", "droid"])
def test_family_diversity_guard_passes_on_the_shipped_config(backend: str) -> None:
    validate_independent_review_family_diversity(backend)


def test_family_diversity_guard_raises_when_families_collide(monkeypatch: Any) -> None:
    import orchestrator.roles_config as roles_config

    real = roles_config.models_for

    def collide(config: Any, backend: str = "cursor") -> Any:
        pair = real(config, backend)
        if config.stem == "reviewer-b":
            return real(load_role_config(TaskRole.SYNTHESIZER), backend)
        return pair

    monkeypatch.setattr(roles_config, "models_for", collide)
    with pytest.raises(RoleConfigError, match="not independent"):
        roles_config.validate_independent_review_family_diversity("cursor")


# ── gate checks ──────────────────────────────────────────────────────────────


def _case_for_gate(
    tmp_path: Path,
    *,
    limitations: list[str],
    review: IndependentReview | None,
) -> Case:
    case = create_case("gate", cases_root=tmp_path)
    case.write_artifact(_final(limitations=limitations))
    if review is not None:
        case.write_artifact(review)
    return case


def test_empty_limitations_produces_exactly_one_finding(tmp_path: Path) -> None:
    case = _case_for_gate(tmp_path, limitations=[], review=None)
    report = run_stage_gate(case, "synthesis", as_of=date(2026, 8, 1))
    findings = [f for f in report.findings if f.check_id == "review.empty_limitations"]
    assert len(findings) == 1


def test_stated_limitations_produce_no_finding(tmp_path: Path) -> None:
    case = _case_for_gate(
        tmp_path,
        limitations=["The demand figure rests on one independence group."],
        review=None,
    )
    report = run_stage_gate(case, "synthesis", as_of=date(2026, 8, 1))
    assert not [f for f in report.findings if f.check_id == "review.empty_limitations"]


def test_dissent_produces_a_blocking_finding(tmp_path: Path) -> None:
    case = _case_for_gate(
        tmp_path,
        limitations=["Thin evidence on competitive response."],
        review=IndependentReview(
            verdict=IndependentVerdict.DISSENT,
            reasoning="The evidence does not support proceeding.",
            divergent_conclusion="Decline now and revisit after the next filing.",
        ),
    )
    report = run_stage_gate(case, "synthesis", as_of=date(2026, 8, 1))
    findings = [f for f in report.findings if f.check_id == "review.unaddressed_dissent"]
    assert len(findings) == 1
    assert findings[0].severity.value == "block"
    assert "revisit after the next filing" in findings[0].message


def test_reservations_produce_a_non_blocking_finding(tmp_path: Path) -> None:
    """Resolves the spec's open question: reservations are recorded, not blocking, so
    they surface in the integrity view without costing a synthesis retry."""
    case = _case_for_gate(
        tmp_path,
        limitations=["Thin evidence on competitive response."],
        review=IndependentReview(
            verdict=IndependentVerdict.CONCUR_WITH_RESERVATIONS,
            reasoning="Same action, weaker basis.",
            unsupported_claims=["Demand growth is independently corroborated"],
        ),
    )
    report = run_stage_gate(case, "synthesis", as_of=date(2026, 8, 1))
    findings = [f for f in report.findings if f.check_id == "review.independent_reservations"]
    assert len(findings) == 1
    assert findings[0].severity.value == "warn"


def test_concur_produces_no_review_finding(tmp_path: Path) -> None:
    case = _case_for_gate(
        tmp_path,
        limitations=["Thin evidence on competitive response."],
        review=IndependentReview(
            verdict=IndependentVerdict.CONCUR,
            reasoning="I reach the same conclusion from this evidence.",
        ),
    )
    report = run_stage_gate(case, "synthesis", as_of=date(2026, 8, 1))
    assert not [
        f
        for f in report.findings
        if f.check_id in {"review.unaddressed_dissent", "review.independent_reservations"}
    ]
