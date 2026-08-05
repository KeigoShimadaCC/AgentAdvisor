"""Assemble and query the post-delivery monitoring plan (SPEC-042).

**The lifecycle decision.** The obvious design — a ``MONITORING`` stage the case sits in
indefinitely — is rejected. ``orchestrator/state_machine.py`` is built on one-way
transitions to terminal states, and the CLI, supervisor, service and resume path all
assume a case runs to completion. Making a case non-terminal would ripple through every
one of them for no gain in decision quality.

Instead the plan is written *at delivery* and then lives *outside* the pipeline, under the
memory root that already outlives individual cases. The case reaches ``done`` exactly as
it did before.

**A breach does not reopen the case.** It recommends opening a new linked case seeded from
the original. A decision made under different conditions is a different decision, and
reopening a delivered case would corrupt the audit chain that is the product's main claim.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import (
    FinalRecommendation,
    IndicatorCheck,
    IndicatorSource,
    MonitoredIndicator,
    MonitoringPlan,
    PreMortemReport,
    TrackedMitigation,
)
from orchestrator.artifacts.monitoring import (
    MAX_CHECK_CADENCE_DAYS,
    MIN_CHECK_CADENCE_DAYS,
)
from orchestrator.case_store import atomic_write_text

__all__ = [
    "DueCheck",
    "MonitoringStore",
    "assemble_plan",
    "due_checks",
    "mitigations_for",
    "monitoring_root",
]

#: Default cadence when nothing better is known. Monthly is frequent enough to catch a
#: turning market and rare enough that the user does not start ignoring it.
DEFAULT_CADENCE_DAYS = 30


def monitoring_root() -> Path:
    """Where monitoring plans live: under the memory root, which already outlives cases."""
    configured = os.getenv("AGENTADVISOR_MEMORY_ROOT")
    base = Path(configured) if configured else Path(__file__).resolve().parents[1] / "memory"
    return base / "monitoring"


def _clamp_cadence(days: int) -> int:
    return max(MIN_CHECK_CADENCE_DAYS, min(MAX_CHECK_CADENCE_DAYS, days))


def assemble_plan(
    case_id: str,
    *,
    delivered_at: date,
    premortem: PreMortemReport | None,
    recommendation: FinalRecommendation | None,
    owner: str = "user",
    concretized: bool = False,
) -> MonitoringPlan:
    """Build the plan deterministically from artifacts the case already produced.

    No agent call. Every ``leading_indicators`` entry across every failure mode, plus every
    ``recommendation_change_triggers`` entry, becomes a tracked indicator; every
    ``preventive_action`` becomes a mitigation linked to the indicators from its own
    failure mode.

    Duplicate indicator text is collapsed — the pre-mortem and the synthesizer frequently
    name the same warning sign — but the first occurrence keeps its provenance.
    """
    indicators: list[MonitoredIndicator] = []
    mitigations: list[TrackedMitigation] = []
    seen: dict[str, str] = {}

    def add_indicator(text: str, source: IndicatorSource, source_ref: str) -> str:
        key = text.strip().lower()
        if key in seen:
            return seen[key]
        indicator_id = f"M-{len(indicators) + 1:03d}"
        indicators.append(
            MonitoredIndicator(
                indicator_id=indicator_id,
                source=source,
                source_ref=source_ref,
                observable=text,
                threshold=(
                    "Not yet made concrete — treat the indicator text as the threshold."
                    if not concretized
                    else text
                ),
                check_cadence_days=_clamp_cadence(DEFAULT_CADENCE_DAYS),
                would_imply=(
                    f"The '{source_ref}' failure mode is materialising."
                    if source is IndicatorSource.PREMORTEM_FAILURE_MODE
                    else "The recommendation's stated change condition has been met."
                ),
            )
        )
        seen[key] = indicator_id
        return indicator_id

    if premortem is not None:
        for mode in premortem.failure_modes:
            linked = [
                add_indicator(text, IndicatorSource.PREMORTEM_FAILURE_MODE, mode.failure_mode)
                for text in mode.leading_indicators
            ]
            mitigations.append(
                TrackedMitigation(
                    mitigation_id=f"R-{len(mitigations) + 1:03d}",
                    failure_mode=mode.failure_mode,
                    mitigation=mode.preventive_action,
                    owner=owner,
                    severity=mode.severity.value,
                    triggered_by=linked,
                )
            )

    if recommendation is not None:
        for trigger in recommendation.recommendation_change_triggers:
            add_indicator(trigger, IndicatorSource.CHANGE_TRIGGER, trigger)

    return MonitoringPlan(
        case_id=case_id,
        delivered_at=delivered_at,
        horizon=premortem.horizon if premortem is not None else "12 months",
        indicators=indicators,
        mitigations=mitigations,
        concretized=concretized,
    )


@dataclass(frozen=True, slots=True)
class DueCheck:
    """An indicator whose next check is overdue."""

    indicator: MonitoredIndicator
    last_checked: datetime | None
    days_overdue: int


def due_checks(
    plan: MonitoringPlan,
    checks: Sequence[IndicatorCheck],
    *,
    as_of: date | None = None,
) -> list[DueCheck]:
    """Indicators whose cadence has elapsed since their last check.

    An indicator never checked is measured from the delivery date, so a plan nobody has
    touched surfaces as soon as the first cadence passes rather than never.
    """
    today = as_of or datetime.now(UTC).date()
    latest: dict[str, datetime] = {}
    for check in checks:
        current = latest.get(check.indicator_id)
        if current is None or check.checked_at > current:
            latest[check.indicator_id] = check.checked_at

    due: list[DueCheck] = []
    for indicator in plan.indicators:
        last = latest.get(indicator.indicator_id)
        since = last.date() if last else plan.delivered_at
        elapsed = (today - since).days
        overdue = elapsed - indicator.check_cadence_days
        if overdue >= 0:
            due.append(DueCheck(indicator=indicator, last_checked=last, days_overdue=overdue))
    return sorted(due, key=lambda item: (-item.days_overdue, item.indicator.indicator_id))


def mitigations_for(
    plan: MonitoringPlan, breached_indicator_ids: Sequence[str]
) -> list[TrackedMitigation]:
    """The prepared responses a breach makes urgent."""
    breached = set(breached_indicator_ids)
    return [
        mitigation for mitigation in plan.mitigations if breached & set(mitigation.triggered_by)
    ]


class MonitoringStore:
    """File-backed monitoring plans and recorded checks, one file per case."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or monitoring_root()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _plan_path(self, case_id: str) -> Path:
        return self._root / f"{case_id}.yaml"

    def _checks_path(self, case_id: str) -> Path:
        return self._root / f"{case_id}.checks.yaml"

    def write_plan(self, plan: MonitoringPlan) -> Path:
        path = self._plan_path(plan.case_id)
        atomic_write_text(path, yaml.safe_dump(plan.model_dump(mode="json"), sort_keys=True))
        return path

    def read_plan(self, case_id: str) -> MonitoringPlan | None:
        path = self._plan_path(case_id)
        if not path.exists():
            return None
        return MonitoringPlan.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def plans(self) -> list[MonitoringPlan]:
        found: list[MonitoringPlan] = []
        for path in sorted(self._root.glob("*.yaml")):
            if path.name.endswith(".checks.yaml"):
                continue
            found.append(
                MonitoringPlan.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
            )
        return found

    def checks(self, case_id: str) -> list[IndicatorCheck]:
        path = self._checks_path(case_id)
        if not path.exists():
            return []
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        return [IndicatorCheck.model_validate(item) for item in loaded]

    def record_check(self, case_id: str, check: IndicatorCheck) -> Path:
        existing = self.checks(case_id)
        existing.append(check)
        path = self._checks_path(case_id)
        atomic_write_text(
            path,
            yaml.safe_dump([item.model_dump(mode="json") for item in existing], sort_keys=True),
        )
        return path
