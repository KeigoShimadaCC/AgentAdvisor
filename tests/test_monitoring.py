"""SPEC-042 — monitoring plan assembly, due checks, and the store."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from orchestrator.artifacts import (
    ConfidenceAssessment,
    FinalRecommendation,
    IndicatorCheck,
    IndicatorSource,
    Level,
    ModelStability,
    MonitoredIndicator,
    MonitoringPlan,
    NextAction,
    PreMortemReport,
    ProbabilityEstimate,
    ProbabilityMethod,
    TrackedMitigation,
)
from orchestrator.artifacts.monitoring import (
    MAX_CHECK_CADENCE_DAYS,
    MIN_CHECK_CADENCE_DAYS,
)
from orchestrator.monitoring import (
    MonitoringStore,
    assemble_plan,
    due_checks,
    mitigations_for,
)

DELIVERED = date(2026, 8, 4)


def _prob(point: float) -> ProbabilityEstimate:
    return ProbabilityEstimate(method=ProbabilityMethod.SCENARIO_MODEL, point=point, adjustments=[])


def _premortem(**overrides: Any) -> PreMortemReport:
    payload: dict[str, Any] = {
        "horizon": "24 months",
        "assumed_outcome": "The allocation lost money.",
        "failure_modes": [
            {
                "failure_mode": "Demand stalled",
                "narrative": "Growth did not persist.",
                "probability": _prob(0.3),
                "severity": Level.HIGH,
                "leading_indicators": [
                    "Two consecutive quarters below 5% growth",
                    "Order backlog shrinking",
                ],
                "preventive_action": "Stage the entry and hold the second tranche.",
            },
            {
                "failure_mode": "Multiple compressed",
                "narrative": "The market re-rated the sector.",
                "probability": _prob(0.2),
                "severity": Level.MEDIUM,
                "leading_indicators": ["Sector forward P/E below 20x"],
                "preventive_action": "Rebalance toward the diversified vehicle.",
            },
        ],
        "most_likely_failure_mode": "Demand stalled",
    }
    payload.update(overrides)
    return PreMortemReport(**payload)


def _recommendation(triggers: list[str]) -> FinalRecommendation:
    return FinalRecommendation(
        recommended_action="Proceed with a staged allocation.",
        timing="Within the quarter.",
        decision_confidence_summary="Moderate.",
        alternatives_considered=[
            {"alternative": "wait", "rank": 2, "rationale": "Lower variance."}
        ],
        key_reasons=["Weighted value is highest [E-001]."],
        scenario_analysis=[
            {"scenario_name": "base", "summary": "Base case.", "probability": _prob(0.6)}
        ],
        recommendation_change_triggers=triggers,
        next_actions=[
            NextAction(
                action_id="N-001",
                action="Start",
                owner="user",
                by_date=date(2026, 8, 15),
                first_step="Open the checklist",
                why_now="First step",
            )
        ],
        outcome_probabilities={"success": _prob(0.6)},
        evidence_confidence=ConfidenceAssessment(value=0.6, basis="Mixed"),
        recommendation_confidence=ConfidenceAssessment(value=0.65, basis="Balanced"),
        model_stability=ModelStability(
            share_of_sensitivity_runs_supporting_recommendation=0.7,
            runs_total=10,
            runs_supporting=7,
        ),
    )


def _plan(**overrides: Any) -> MonitoringPlan:
    return assemble_plan(
        "case-001-monitor",
        delivered_at=DELIVERED,
        premortem=overrides.pop("premortem", _premortem()),
        recommendation=overrides.pop(
            "recommendation", _recommendation(["Earnings miss above 10%"])
        ),
        **overrides,
    )


# ── assembly ─────────────────────────────────────────────────────────────────


def test_every_leading_indicator_and_change_trigger_becomes_an_indicator() -> None:
    """The exact material the pipeline used to discard."""
    premortem = _premortem()
    recommendation = _recommendation(["Earnings miss above 10%", "Rates above 6%"])
    plan = _plan(premortem=premortem, recommendation=recommendation)

    expected = sum(len(mode.leading_indicators) for mode in premortem.failure_modes) + len(
        recommendation.recommendation_change_triggers
    )
    assert len(plan.indicators) == expected


def test_every_preventive_action_becomes_a_tracked_mitigation() -> None:
    """Gap 14 in the analysis: the pre-mortem is equally a source of *responses*."""
    premortem = _premortem()
    plan = _plan(premortem=premortem)
    assert len(plan.mitigations) == len(premortem.failure_modes)
    assert {m.mitigation for m in plan.mitigations} == {
        mode.preventive_action for mode in premortem.failure_modes
    }


def test_mitigations_link_to_the_indicators_from_their_own_failure_mode() -> None:
    plan = _plan()
    by_mode = {m.failure_mode: m for m in plan.mitigations}
    stalled = by_mode["Demand stalled"]
    linked = {i.indicator_id for i in plan.indicators if i.source_ref == "Demand stalled"}
    assert set(stalled.triggered_by) == linked
    assert len(stalled.triggered_by) == 2


def test_indicator_provenance_is_preserved() -> None:
    plan = _plan()
    premortem_sourced = [
        i for i in plan.indicators if i.source is IndicatorSource.PREMORTEM_FAILURE_MODE
    ]
    trigger_sourced = [i for i in plan.indicators if i.source is IndicatorSource.CHANGE_TRIGGER]
    assert len(premortem_sourced) == 3
    assert len(trigger_sourced) == 1


def test_duplicate_indicator_text_is_collapsed_but_keeps_first_provenance() -> None:
    """The pre-mortem and the synthesizer often name the same warning sign."""
    plan = _plan(recommendation=_recommendation(["Two consecutive quarters below 5% growth"]))
    texts = [i.observable for i in plan.indicators]
    assert len(texts) == len(set(texts))
    duplicated = next(i for i in plan.indicators if "5% growth" in i.observable)
    assert duplicated.source is IndicatorSource.PREMORTEM_FAILURE_MODE


def test_assembly_without_a_premortem_still_tracks_change_triggers() -> None:
    plan = _plan(premortem=None)
    assert len(plan.indicators) == 1
    assert plan.mitigations == []


def test_assembly_with_nothing_to_track_yields_an_empty_plan() -> None:
    plan = _plan(premortem=None, recommendation=_recommendation([]))
    assert plan.indicators == []


def test_plan_is_marked_unconcretized_until_the_monitor_runs() -> None:
    plan = _plan()
    assert plan.concretized is False
    assert all("Not yet made concrete" in i.threshold for i in plan.indicators)


# ── schema validation ────────────────────────────────────────────────────────


def test_cadence_below_the_floor_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MonitoredIndicator(
            indicator_id="M-001",
            source=IndicatorSource.CHANGE_TRIGGER,
            source_ref="x",
            observable="x",
            threshold="x",
            check_cadence_days=MIN_CHECK_CADENCE_DAYS - 1,
            would_imply="x",
        )


def test_cadence_above_the_ceiling_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MonitoredIndicator(
            indicator_id="M-001",
            source=IndicatorSource.CHANGE_TRIGGER,
            source_ref="x",
            observable="x",
            threshold="x",
            check_cadence_days=MAX_CHECK_CADENCE_DAYS + 1,
            would_imply="x",
        )


def test_mitigation_triggered_by_an_unknown_indicator_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown indicator"):
        MonitoringPlan(
            case_id="case-001-monitor",
            delivered_at=DELIVERED,
            horizon="12 months",
            indicators=[],
            mitigations=[
                TrackedMitigation(
                    mitigation_id="R-001",
                    failure_mode="x",
                    mitigation="y",
                    owner="user",
                    severity="high",
                    triggered_by=["M-999"],
                )
            ],
        )


# ── due checks ───────────────────────────────────────────────────────────────


def _concretized(plan: MonitoringPlan, cadence: int = 30) -> MonitoringPlan:
    return plan.model_copy(
        update={
            "concretized": True,
            "indicators": [
                i.model_copy(update={"check_cadence_days": cadence, "threshold": "t"})
                for i in plan.indicators
            ],
        }
    )


def test_never_checked_indicator_comes_due_after_one_cadence() -> None:
    plan = _concretized(_plan(), cadence=30)
    assert due_checks(plan, [], as_of=DELIVERED + timedelta(days=29)) == []
    assert len(due_checks(plan, [], as_of=DELIVERED + timedelta(days=30))) == len(plan.indicators)


def test_recent_check_clears_the_indicator() -> None:
    plan = _concretized(_plan(), cadence=30)
    target = plan.indicators[0].indicator_id
    checks = [
        IndicatorCheck(
            indicator_id=target,
            checked_at=datetime(2026, 9, 1, tzinfo=UTC),
            observed="Growth held",
        )
    ]
    due_ids = {d.indicator.indicator_id for d in due_checks(plan, checks, as_of=date(2026, 9, 15))}
    assert target not in due_ids


def test_stale_check_comes_due_again() -> None:
    plan = _concretized(_plan(), cadence=30)
    target = plan.indicators[0].indicator_id
    checks = [
        IndicatorCheck(
            indicator_id=target,
            checked_at=datetime(2026, 9, 1, tzinfo=UTC),
            observed="Growth held",
        )
    ]
    due = due_checks(plan, checks, as_of=date(2026, 10, 5))
    entry = next(d for d in due if d.indicator.indicator_id == target)
    assert entry.days_overdue == 4
    assert entry.last_checked is not None


def test_as_of_before_delivery_yields_nothing_due() -> None:
    plan = _concretized(_plan(), cadence=30)
    assert due_checks(plan, [], as_of=DELIVERED - timedelta(days=1)) == []


def test_only_the_latest_check_counts() -> None:
    plan = _concretized(_plan(), cadence=30)
    target = plan.indicators[0].indicator_id
    checks = [
        IndicatorCheck(
            indicator_id=target, checked_at=datetime(2026, 8, 5, tzinfo=UTC), observed="old"
        ),
        IndicatorCheck(
            indicator_id=target, checked_at=datetime(2026, 9, 20, tzinfo=UTC), observed="new"
        ),
    ]
    due_ids = {d.indicator.indicator_id for d in due_checks(plan, checks, as_of=date(2026, 10, 1))}
    assert target not in due_ids


def test_due_checks_are_sorted_most_overdue_first() -> None:
    plan = _plan()
    plan = plan.model_copy(
        update={
            "indicators": [
                plan.indicators[0].model_copy(update={"check_cadence_days": 7}),
                plan.indicators[1].model_copy(update={"check_cadence_days": 90}),
            ]
        }
    )
    due = due_checks(plan, [], as_of=DELIVERED + timedelta(days=120))
    assert due[0].days_overdue > due[1].days_overdue


# ── mitigations_for ──────────────────────────────────────────────────────────


def test_breach_surfaces_the_linked_response() -> None:
    plan = _plan()
    stalled = next(m for m in plan.mitigations if m.failure_mode == "Demand stalled")
    responses = mitigations_for(plan, [stalled.triggered_by[0]])
    assert [m.mitigation_id for m in responses] == [stalled.mitigation_id]


def test_unlinked_indicator_surfaces_no_response() -> None:
    plan = _plan()
    trigger = next(i for i in plan.indicators if i.source is IndicatorSource.CHANGE_TRIGGER)
    assert mitigations_for(plan, [trigger.indicator_id]) == []


# ── store ────────────────────────────────────────────────────────────────────


def test_plan_round_trips_through_the_store(tmp_path: Path) -> None:
    store = MonitoringStore(tmp_path)
    plan = _plan()
    store.write_plan(plan)
    loaded = store.read_plan(plan.case_id)
    assert loaded is not None
    assert loaded.model_dump() == plan.model_dump()


def test_reading_an_unknown_case_returns_none(tmp_path: Path) -> None:
    assert MonitoringStore(tmp_path).read_plan("case-999-nope") is None


def test_checks_accumulate_and_do_not_appear_in_the_plan_listing(tmp_path: Path) -> None:
    store = MonitoringStore(tmp_path)
    plan = _plan()
    store.write_plan(plan)
    for observed in ("first", "second"):
        store.record_check(
            plan.case_id,
            IndicatorCheck(
                indicator_id=plan.indicators[0].indicator_id,
                checked_at=datetime.now(UTC),
                observed=observed,
            ),
        )
    assert len(store.checks(plan.case_id)) == 2
    # The checks file must not be mistaken for a plan.
    assert [p.case_id for p in store.plans()] == [plan.case_id]


def test_store_lists_plans_across_cases(tmp_path: Path) -> None:
    store = MonitoringStore(tmp_path)
    store.write_plan(_plan())
    store.write_plan(_plan().model_copy(update={"case_id": "case-002-other"}))
    assert {p.case_id for p in store.plans()} == {"case-001-monitor", "case-002-other"}


# ── service endpoint and record_outcome prompting (SPEC-042 scope items) ─────


def test_monitoring_endpoint_returns_the_plan_and_due_checks(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from orchestrator.case_store import create_case
    from orchestrator.service.app import create_app

    cases_root = tmp_path / "cases"
    case = create_case("watched", cases_root=cases_root)
    plan = _plan().model_copy(
        update={"case_id": case.root.name, "delivered_at": date(2026, 1, 1), "concretized": True}
    )
    MonitoringStore(tmp_path / "monitoring").write_plan(plan)

    app = create_app(cases_root, monitoring_root=tmp_path / "monitoring")
    with TestClient(app) as client:
        response = client.get(f"/api/cases/{case.root.name}/monitoring")
    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["case_id"] == case.root.name
    # Delivered in January against a 30-day cadence, so everything is overdue.
    assert len(body["due"]) == len(plan.indicators)


def test_monitoring_endpoint_reports_no_plan_without_erroring(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from orchestrator.case_store import create_case
    from orchestrator.service.app import create_app

    cases_root = tmp_path / "cases"
    case = create_case("unwatched", cases_root=cases_root)
    app = create_app(cases_root, monitoring_root=tmp_path / "monitoring")
    with TestClient(app) as client:
        response = client.get(f"/api/cases/{case.root.name}/monitoring")
    assert response.status_code == 200
    assert response.json() == {"plan": None, "due": []}


# ── A pinned "today" for fixtures (SPEC-056) ─────────────────────────────────
#
# Dueness is ``(today - delivered_at) >= cadence``, so a committed monitoring plan
# renders differently as the calendar advances.  The e2e fixture showed "1 check is
# due now" and would have said "2" from 2026-08-23, failing the delivery visual
# baseline with no code change behind it.  These tests exist so that expiry cannot
# come back silently.


def _two_cadence_plan(case_id: str) -> MonitoringPlan:
    """One 30-day and one 14-day indicator, delivered 2026-07-24.

    Between +14 and +30 days exactly one is due, which is the state the committed
    delivery baseline was captured in. The plan's own indicator IDs are kept, because
    ``MonitoringPlan`` validates that every mitigation's ``triggered_by`` resolves —
    renaming them orphans the mitigations.
    """
    base = _plan().model_copy(update={"case_id": case_id, "delivered_at": date(2026, 7, 24)})
    kept = [
        base.indicators[0].model_copy(update={"check_cadence_days": 30}),
        base.indicators[1].model_copy(update={"check_cadence_days": 14}),
    ]
    kept_ids = {i.indicator_id for i in kept}
    return base.model_copy(
        update={
            "indicators": kept,
            "mitigations": [m for m in base.mitigations if set(m.triggered_by).issubset(kept_ids)],
        }
    )


def test_as_of_freezes_dueness_against_the_calendar() -> None:
    plan = _two_cadence_plan("case-001-fixture-001")
    # The window the baseline lives in: one due, one not.
    assert len(due_checks(plan, [], as_of=date(2026, 8, 7))) == 1
    # ...and the day the real clock would have broken it.
    assert len(due_checks(plan, [], as_of=date(2026, 8, 23))) == 2
    # Pinning the date is therefore the difference between a reproducible fixture
    # and one with a silent expiry.
    assert len(due_checks(plan, [], as_of=date(2026, 8, 7))) == 1


def test_service_honours_a_pinned_as_of(tmp_path: Path, monkeypatch: Any) -> None:
    from fastapi.testclient import TestClient

    from orchestrator.case_store import create_case
    from orchestrator.service.app import create_app

    cases_root = tmp_path / "cases"
    case = create_case("watched", cases_root=cases_root)
    MonitoringStore(tmp_path / "monitoring").write_plan(_two_cadence_plan(case.root.name))

    # Pinned to the day *after* delivery, when neither cadence has elapsed and the
    # honest answer is zero.
    #
    # The date matters, and an earlier version of this test got it wrong: pinning to
    # 2026-08-07 asserted "1 due", which is also what the real clock said on the day
    # the test was written — so it passed whether or not the pin was honoured, and
    # would only have started failing after 2026-08-23, the very date it exists to
    # defend. A pin in the past stays distinguishable forever, because the real clock
    # only ever moves further from it.
    monkeypatch.setenv("AGENTADVISOR_MONITORING_AS_OF", "2026-07-25")
    app = create_app(cases_root, monitoring_root=tmp_path / "monitoring")
    with TestClient(app) as client:
        body = client.get(f"/api/cases/{case.root.name}/monitoring").json()
    assert body["due"] == []


def test_an_unset_or_malformed_as_of_falls_back_to_the_real_clock(monkeypatch: Any) -> None:
    from orchestrator.service.app import _monitoring_as_of_from_env

    monkeypatch.delenv("AGENTADVISOR_MONITORING_AS_OF", raising=False)
    assert _monitoring_as_of_from_env() is None
    # A malformed hook must not take down a real service, so it degrades to the
    # real clock rather than raising at construction.
    monkeypatch.setenv("AGENTADVISOR_MONITORING_AS_OF", "not-a-date")
    assert _monitoring_as_of_from_env() is None
    monkeypatch.setenv("AGENTADVISOR_MONITORING_AS_OF", "2026-08-07")
    assert _monitoring_as_of_from_env() == date(2026, 8, 7)


def test_a_real_deployment_still_uses_the_real_clock(tmp_path: Path, monkeypatch: Any) -> None:
    from fastapi.testclient import TestClient

    from orchestrator.case_store import create_case
    from orchestrator.service.app import create_app

    monkeypatch.delenv("AGENTADVISOR_MONITORING_AS_OF", raising=False)
    cases_root = tmp_path / "cases"
    case = create_case("watched", cases_root=cases_root)
    # Delivered long ago against any cadence: everything is overdue today, which is
    # only true if the service is reading the real clock.
    plan = _two_cadence_plan(case.root.name).model_copy(update={"delivered_at": date(2020, 1, 1)})
    MonitoringStore(tmp_path / "monitoring").write_plan(plan)

    app = create_app(cases_root, monitoring_root=tmp_path / "monitoring")
    with TestClient(app) as client:
        body = client.get(f"/api/cases/{case.root.name}/monitoring").json()
    assert len(body["due"]) == 2
