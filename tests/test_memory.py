from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from orchestrator.artifacts import (
    AlternativeAssessment,
    AssumptionRecord,
    AssumptionStatus,
    AssumptionType,
    ConfidenceAssessment,
    Counterargument,
    DecisionSpec,
    Depth,
    EvidenceRecord,
    FinalRecommendation,
    Level,
    ModelStability,
    OutcomeRecord,
    ProbabilityEstimate,
    ProbabilityMethod,
    Reversibility,
    RiskTolerance,
    ScenarioAssessment,
    SourceType,
)
from orchestrator.case_store import Case, create_case
from orchestrator.memory import (
    MemoryStore,
    is_related,
    keywords,
    overlap,
    registrable_domain,
    write_digests,
)


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(root=tmp_path / "memory")


@pytest.fixture
def cases_root(tmp_path: Path) -> Path:
    return tmp_path / "cases"


def _prob(point: float) -> ProbabilityEstimate:
    return ProbabilityEstimate(method=ProbabilityMethod.SCENARIO_MODEL, point=point)


def _spec(case_id: str, question: str) -> DecisionSpec:
    return DecisionSpec(
        decision_id=case_id,
        question=question,
        owner="user",
        deadline=date(2026, 12, 31),
        alternatives=["act", "wait"],
        objectives=["Grow capital"],
        constraints=["No leverage"],
        risk_tolerance=RiskTolerance.MODERATE,
        reversibility=Reversibility.PARTIALLY_REVERSIBLE,
        depth=Depth.STANDARD,
    )


def _final(action: str = "Enter in three tranches") -> FinalRecommendation:
    return FinalRecommendation(
        recommended_action=action,
        timing="This week",
        decision_confidence_summary="Moderate confidence",
        alternatives_considered=[
            AlternativeAssessment(alternative="act", rank=1, rationale="Balanced"),
            AlternativeAssessment(alternative="wait", rank=2, rationale="Slower"),
        ],
        key_reasons=["Growth is strong [E-001]"],
        scenario_analysis=[
            ScenarioAssessment(scenario_name="base", summary="In line", probability=_prob(0.5))
        ],
        quantitative_findings=[],
        strongest_counterarguments=[
            Counterargument(claim="Concentration risk", resolution="Accepted", resolved=True)
        ],
        critical_assumptions=[],
        recommendation_change_triggers=["Earnings miss"],
        next_actions=[
            {
                "action_id": "N-001",
                "action": "Place the first tranche",
                "owner": "user",
                "by_date": "2026-08-15",
                "first_step": "Block 30 minutes and open the tracking sheet",
                "why_now": "Carries the recommendation into execution",
            }
        ],
        citations=["E-001"],
        outcome_probabilities={"positive_return_12m": _prob(0.58)},
        evidence_confidence=ConfidenceAssessment(value=0.55, basis="Mixed"),
        recommendation_confidence=ConfidenceAssessment(value=0.62, basis="Balanced"),
        model_stability=ModelStability(
            share_of_sensitivity_runs_supporting_recommendation=1.0,
            runs_total=2,
            runs_supporting=2,
        ),
    )


def _evidence(evidence_id: str, url: str, claim: str) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        claim=claim,
        source_title="Annual report",
        publisher="NVIDIA Corporation",
        source_url=url,
        source_type=SourceType.REGULATORY_FILING,
        publication_date=date(2026, 5, 1),
        retrieval_date=date(2026, 8, 1),
        excerpt="Excerpt from the filing.",
        reliability=Level.HIGH,
        directness=Level.HIGH,
        independence_group="sec-filings",
        limitations=["Backward looking"],
        retrieved_by="researcher",
    )


def _assumption(assumption_id: str, claim: str, materiality: Level = Level.MEDIUM):
    return AssumptionRecord(
        assumption_id=assumption_id,
        claim=claim,
        type=AssumptionType.FORECAST,
        estimate=_prob(0.6),
        confidence=Level.MEDIUM,
        materiality=materiality,
        evidence_for=[],
        evidence_against=[],
        status=AssumptionStatus.UNRESOLVED,
    )


def _completed_case(
    cases_root: Path,
    slug: str,
    question: str,
    *,
    evidence: list[EvidenceRecord] | None = None,
    assumptions: list[AssumptionRecord] | None = None,
) -> Case:
    case = create_case(slug, cases_root=cases_root)
    case.write_artifact(_spec(case.root.name, question))
    for record in evidence or []:
        case.write_artifact(record)
    for record in assumptions or []:
        case.write_artifact(record)
    case.write_artifact(_final())
    return case


def test_keywords_drop_stopwords_and_deduplicate() -> None:
    assert keywords("Should I buy the NVIDIA stock and the stock index?") == [
        "buy",
        "nvidia",
        "stock",
        "index",
    ]


def test_overlap_is_jaccard_and_zero_on_empty() -> None:
    assert overlap(["a", "b"], ["a", "b"]) == 1.0
    assert overlap(["a", "b"], ["b", "c"]) == pytest.approx(1 / 3)
    assert overlap([], ["a"]) == 0.0


def test_one_shared_ordinary_word_is_not_relevance() -> None:
    assert not is_related(["buy", "nvidia", "stock"], ["buy", "condo", "mortgage"])
    assert is_related(["buy", "nvidia", "stock"], ["buy", "nvidia", "shares"])


def test_registrable_domain_strips_scheme_port_and_www() -> None:
    assert registrable_domain("https://www.sec.gov:443/filings/x") == "sec.gov"
    assert registrable_domain("not-a-url") == "unknown"


def test_recording_a_case_snapshots_the_recommendation(
    store: MemoryStore, cases_root: Path
) -> None:
    case = _completed_case(cases_root, "nvidia", "Should I buy NVIDIA stock?")

    entry = store.record_case(case, domains=["public-equity"])

    assert entry.case_id == case.root.name
    assert entry.recommended_action == "Enter in three tranches"
    assert entry.alternatives_considered == ["act", "wait"]
    assert entry.headline_outcome_name == "positive_return_12m"
    assert entry.headline_outcome_probability == pytest.approx(0.58)
    assert store.prior_cases()[0].case_id == entry.case_id


def test_recording_the_same_case_twice_does_not_duplicate(
    store: MemoryStore, cases_root: Path
) -> None:
    case = _completed_case(cases_root, "nvidia", "Should I buy NVIDIA stock?")
    store.record_case(case)
    store.record_case(case)

    assert len(store.prior_cases()) == 1


def test_digest_retrieves_a_related_case_and_ignores_an_unrelated_one(
    store: MemoryStore, cases_root: Path
) -> None:
    store.record_case(_completed_case(cases_root, "nvidia", "Should I buy NVIDIA stock now?"))
    store.record_case(
        _completed_case(cases_root, "condo", "Should I buy a condo in Osaka with a mortgage?")
    )

    digest = store.digest_for("Should I buy more NVIDIA stock?")

    assert [entry.decision_question for entry in digest.prior_cases] == [
        "Should I buy NVIDIA stock now?"
    ]


def test_digest_excludes_the_live_case(store: MemoryStore, cases_root: Path) -> None:
    case = _completed_case(cases_root, "nvidia", "Should I buy NVIDIA stock now?")
    store.record_case(case)

    digest = store.digest_for("Should I buy NVIDIA stock now?", exclude_case_id=case.root.name)

    assert digest.prior_cases == []


def test_digest_states_that_nothing_in_it_may_be_cited(store: MemoryStore) -> None:
    digest = store.digest_for("anything")

    assert "may be cited" in digest.usage_note
    assert "may not be cited" in store.prior_evidence_for("anything").staleness_warning


def test_source_reputation_aggregates_across_cases(store: MemoryStore, cases_root: Path) -> None:
    store.record_case(
        _completed_case(
            cases_root,
            "nvidia",
            "Should I buy NVIDIA stock?",
            evidence=[
                _evidence("E-001", "https://www.sec.gov/a", "Revenue grew"),
                _evidence("E-002", "https://sec.gov/b", "Margins held"),
                _evidence("E-003", "https://blog.example.com/c", "Analyst opinion"),
            ],
        )
    )

    reputations = {item.domain: item for item in store.source_reputations()}

    assert reputations["sec.gov"].times_cited == 2
    assert reputations["blog.example.com"].times_cited == 1
    assert 0.0 <= reputations["sec.gov"].mean_authority <= 1.0


def test_an_assumption_repeated_across_cases_is_counted_once_per_case(
    store: MemoryStore, cases_root: Path
) -> None:
    claim = "Data center demand keeps growing through the horizon"
    store.record_case(
        _completed_case(
            cases_root,
            "nvidia",
            "Should I buy NVIDIA stock?",
            assumptions=[_assumption("A-001", claim), _assumption("A-002", claim)],
        )
    )
    store.record_case(
        _completed_case(
            cases_root,
            "amd",
            "Should I buy AMD stock?",
            assumptions=[_assumption("A-001", claim, materiality=Level.HIGH)],
        )
    )

    recurring = store.recurring_assumptions()

    assert len(recurring) == 1
    assert recurring[0].occurrences == 2
    assert recurring[0].max_materiality is Level.HIGH
    assert len(recurring[0].case_ids) == 2


def test_prior_evidence_is_replaced_not_appended_when_a_case_is_rerecorded(
    store: MemoryStore, cases_root: Path
) -> None:
    case = _completed_case(
        cases_root,
        "nvidia",
        "Should I buy NVIDIA stock?",
        evidence=[_evidence("E-001", "https://www.sec.gov/a", "Revenue grew")],
    )
    store.record_case(case)
    store.record_case(case)

    assert len(store.prior_evidence()) == 1


def test_recording_an_outcome_attaches_it_and_feeds_calibration(
    store: MemoryStore, cases_root: Path
) -> None:
    case = _completed_case(cases_root, "nvidia", "Should I buy NVIDIA stock?")
    store.record_case(case)

    updated = store.record_outcome(
        case.root.name,
        OutcomeRecord(
            recorded_at=datetime(2027, 8, 1, tzinfo=UTC),
            outcome_summary="The position gained 20%.",
            recommendation_followed=True,
            forecast_outcome_name="positive_return_12m",
            forecast_probability=0.58,
            realized=True,
        ),
    )

    assert updated.outcome is not None
    assert store.calibration().sample_size == 1


def test_recording_an_outcome_for_an_unknown_case_raises(store: MemoryStore) -> None:
    with pytest.raises(KeyError, match="No prior case recorded"):
        store.record_outcome(
            "case-999-missing",
            OutcomeRecord(
                recorded_at=datetime(2027, 8, 1, tzinfo=UTC),
                outcome_summary="n/a",
                recommendation_followed=False,
                forecast_outcome_name="x",
                forecast_probability=0.5,
                realized=False,
            ),
        )


def test_rerecording_a_case_preserves_an_already_attached_outcome(
    store: MemoryStore, cases_root: Path
) -> None:
    case = _completed_case(cases_root, "nvidia", "Should I buy NVIDIA stock?")
    store.record_case(case)
    store.record_outcome(
        case.root.name,
        OutcomeRecord(
            recorded_at=datetime(2027, 8, 1, tzinfo=UTC),
            outcome_summary="The position gained 20%.",
            recommendation_followed=True,
            forecast_outcome_name="positive_return_12m",
            forecast_probability=0.58,
            realized=True,
        ),
    )

    store.record_case(case)

    assert store.prior_cases()[0].outcome is not None


def test_write_digests_puts_both_digests_on_the_case(store: MemoryStore, cases_root: Path) -> None:
    store.record_case(
        _completed_case(
            cases_root,
            "nvidia",
            "Should I buy NVIDIA stock?",
            evidence=[_evidence("E-001", "https://www.sec.gov/a", "NVIDIA revenue grew")],
        )
    )
    live = create_case("nvidia-again", cases_root=cases_root)

    digest, evidence_digest = write_digests(
        live, question="Should I buy NVIDIA stock again?", store=store
    )

    assert digest.prior_cases
    assert evidence_digest.entries
    assert (live.root / "shared" / "case_memory_digest.yaml").exists()
    assert (live.root / "shared" / "prior_evidence_digest.yaml").exists()


def test_an_empty_store_produces_an_empty_but_valid_digest(store: MemoryStore) -> None:
    digest = store.digest_for("Should I buy NVIDIA stock?")

    assert digest.prior_cases == []
    assert digest.source_reputations == []
    assert digest.calibration is not None
    assert digest.calibration.sample_size == 0
