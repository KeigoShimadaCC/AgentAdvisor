"""Post-delivery monitoring (SPEC-042).

Every case already produces the raw material of an indicators-and-warning set and a risk
register, and then throws all of it away at delivery: ``FailureMode.leading_indicators``
and ``FailureMode.preventive_action`` on each pre-mortem failure mode, plus
``FinalRecommendation.recommendation_change_triggers``.  All three are prose, all three
are rendered once, and no code ever reads them again.

These models make them tracked objects.  Detection and response are two halves of one
artifact: an indicator tells the decision owner what to watch, and the mitigation it
links to says what to do when it fires.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import Field, model_validator

from orchestrator.artifacts.common import ArtifactModel, CaseId, NonEmptyStr

IndicatorId = Annotated[str, Field(pattern=r"^M-\d+$")]
MitigationId = Annotated[str, Field(pattern=r"^R-\d+$")]

#: Cadence bounds. Below a week the user is being asked to babysit a decision; beyond six
#: months the indicator has stopped being a warning and become a reminder.
MIN_CHECK_CADENCE_DAYS = 7
MAX_CHECK_CADENCE_DAYS = 180


class IndicatorSource(StrEnum):
    PREMORTEM_FAILURE_MODE = "premortem_failure_mode"
    CHANGE_TRIGGER = "change_trigger"


class MitigationStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PLACE = "in_place"
    NOT_APPLICABLE = "not_applicable"


class MonitoredIndicator(ArtifactModel):
    """One thing to watch, and what its breach would mean."""

    indicator_id: IndicatorId
    source: IndicatorSource
    #: The failure mode or change trigger this came from, verbatim, so provenance survives.
    source_ref: NonEmptyStr
    #: What to look at. Concretised by the monitor role from the prose indicator; falls
    #: back to the prose itself when that invocation did not run.
    observable: NonEmptyStr
    #: The reading that constitutes a breach.
    threshold: NonEmptyStr
    check_cadence_days: int = Field(ge=MIN_CHECK_CADENCE_DAYS, le=MAX_CHECK_CADENCE_DAYS)
    #: What a breach would imply for the recommendation.
    would_imply: NonEmptyStr
    #: The alternative a breach would point toward, when the source names one.
    implicated_alternative: NonEmptyStr | None = None


class TrackedMitigation(ArtifactModel):
    """A prepared response, with an owner.

    Sourced from ``FailureMode.preventive_action``, which the pipeline generates on every
    case and has never carried into the deliverable.
    """

    mitigation_id: MitigationId
    failure_mode: NonEmptyStr
    mitigation: NonEmptyStr
    owner: NonEmptyStr
    severity: NonEmptyStr
    status: MitigationStatus = MitigationStatus.NOT_STARTED
    #: Indicators whose breach makes this mitigation urgent.
    triggered_by: list[IndicatorId] = Field(default_factory=list)


class MonitoringPlan(ArtifactModel):
    """What to watch after the report is delivered, and what to do about it."""

    case_id: CaseId
    delivered_at: date
    horizon: NonEmptyStr
    indicators: list[MonitoredIndicator] = Field(default_factory=list)
    mitigations: list[TrackedMitigation] = Field(default_factory=list)
    #: False when the monitor invocation failed and the plan carries prose indicators
    #: rather than concrete observables. A degraded plan beats no plan, but the reader
    #: must be able to tell which they have.
    concretized: bool = True

    @model_validator(mode="after")
    def validate_links_resolve(self) -> MonitoringPlan:
        known = {indicator.indicator_id for indicator in self.indicators}
        if len(known) != len(self.indicators):
            raise ValueError("indicators contains duplicate indicator_ids.")

        mitigation_ids = [mitigation.mitigation_id for mitigation in self.mitigations]
        if len(set(mitigation_ids)) != len(mitigation_ids):
            raise ValueError("mitigations contains duplicate mitigation_ids.")

        for mitigation in self.mitigations:
            unknown = sorted(set(mitigation.triggered_by) - known)
            if unknown:
                raise ValueError(
                    f"{mitigation.mitigation_id} is triggered_by unknown indicator(s): {unknown}"
                )
        return self


class IndicatorCheck(ArtifactModel):
    """One observation of one indicator, recorded by the decision owner."""

    indicator_id: IndicatorId
    checked_at: datetime
    observed: NonEmptyStr
    breached: bool = False
    note: NonEmptyStr | None = None
