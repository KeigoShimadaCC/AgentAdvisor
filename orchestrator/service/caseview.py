"""CaseView projection — the frontend's read model.

``CaseView`` is a versioned Pydantic document assembled server-side from a
case directory.  It isolates the UI from orchestrator internals: stage enums,
file layout, and coercion quirks do not leak into client code, and sentinel
detection (north star Section 9) happens once, here.

Everything presentation-shaped but engine-owned (renderer section order,
provenance labels, sentinel predicates) is imported from the engine so
export and UI cannot diverge.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from orchestrator.artifacts import (
    AnalysisResult,
    AssumptionRecord,
    DisclosureRecord,
    EvidenceCritique,
    EvidenceRecord,
    FinalApproval,
    FinalRecommendation,
    FramingApproval,
    GateReport,
    GateSeverity,
    IntakeRecord,
    IssueTree,
    ObjectionRecord,
    PreliminaryRecommendation,
    PreMortemReport,
    ReviewReport,
    TaskRecord,
    ThesisRevision,
    TrackDivergence,
    VerificationWorksheet,
)
from orchestrator.artifacts.confidence import ConfidenceAssessment
from orchestrator.artifacts.evidence_critique import EvidenceAuthorityScore
from orchestrator.artifacts.objections import ObjectionResolutionStatus
from orchestrator.artifacts.probability import ProbabilityEstimate
from orchestrator.artifacts.sentinels import (
    is_confidence_placeholder,
    is_model_stability_placeholder,
)
from orchestrator.artifacts.stability import ModelStability
from orchestrator.case_store import Case
from orchestrator.state_machine import CaseStage, CaseState, load_case_state

__all__ = ["CaseView", "build_case_view"]

# Provenance labels — mirrored from orchestrator.render to avoid a circular
# import (render -> citations -> invoke_role -> schema_export -> service).
# These must stay in sync with the renderer's constants.
PROVENANCE_SOURCED_FACT = "sourced_fact"
PROVENANCE_ASSUMPTION = "assumption"
PROVENANCE_CALCULATION = "calculation"
PROVENANCE_USER_INPUT = "user_input"
PROVENANCE_INTERPRETATION = "interpretation"
PROVENANCE_RECOMMENDATION = "recommendation"


# ── Presentation phase mapping ───────────────────────────────────────────────

Phase = Literal["intake", "framing", "investigation", "challenge", "synthesis", "complete"]
NeedsYou = Literal["scope_checkpoint", "delivery_checkpoint", "interrupted", "none"]

_STAGE_TO_PHASE: dict[CaseStage, Phase] = {
    CaseStage.INTAKE: "intake",
    CaseStage.FRAMING: "framing",
    CaseStage.AWAITING_FRAMING_APPROVAL: "framing",
    CaseStage.STRUCTURING: "investigation",
    CaseStage.PROVISIONAL_THESIS: "investigation",
    CaseStage.PLANNING: "investigation",
    CaseStage.INVESTIGATION: "investigation",
    CaseStage.EVIDENCE_CRITIQUE: "investigation",
    CaseStage.ASSUMPTION_LEDGER: "investigation",
    CaseStage.PRELIMINARY_RECOMMENDATION: "investigation",
    CaseStage.PRE_MORTEM: "challenge",
    CaseStage.CHALLENGE: "challenge",
    CaseStage.REPAIR: "challenge",
    CaseStage.STOP_DECISION: "challenge",
    CaseStage.SYNTHESIS: "synthesis",
    CaseStage.REVIEW: "synthesis",
    CaseStage.AWAITING_FINAL_APPROVAL: "synthesis",
    CaseStage.DONE: "complete",
    CaseStage.FAILED: "complete",
}

_TERMINAL_STAGES = frozenset({CaseStage.DONE, CaseStage.FAILED})


def _phase_for_stage(stage: CaseStage) -> Phase:
    return _STAGE_TO_PHASE[stage]


def _needs_you_for_state(state: CaseState) -> NeedsYou:
    if state.stage is CaseStage.AWAITING_FRAMING_APPROVAL:
        return "scope_checkpoint"
    if state.stage is CaseStage.AWAITING_FINAL_APPROVAL:
        return "delivery_checkpoint"
    if state.stage is CaseStage.FAILED:
        return "interrupted"
    return "none"


# ── Brief sections ───────────────────────────────────────────────────────────

BriefSectionStatus = Literal["pending", "partial", "final", "not_assessed"]

# The renderer section order, mirrored from orchestrator.render.
BRIEF_SECTION_ORDER: tuple[str, ...] = (
    "executive_recommendation",
    "decision_confidence",
    "alternatives_considered",
    "key_reasons",
    "scenario_analysis",
    "quantitative_findings",
    "strongest_counterarguments",
    "premortem",
    "critical_assumptions",
    "recommendation_change_triggers",
    "next_actions",
    "user_supplied_inputs",
    "budget_depth_stop_disclosure",
    "evidence_and_citations",
)


class BriefBlock(BaseModel):
    """One rendered line/element within a brief section, carrying provenance."""

    model_config = ConfigDict(extra="forbid")

    provenance: str
    text: str
    citation_ids: list[str] = Field(default_factory=list)


class BriefSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    status: BriefSectionStatus
    blocks: list[BriefBlock] = Field(default_factory=list)


# ── Uncertainty tagged unions ────────────────────────────────────────────────


class AssessedConfidence(BaseModel):
    """A confidence that was actually assessed (not a coercion default)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["assessed"] = "assessed"
    value: float = Field(ge=0.0, le=1.0)
    basis: str


class NotAssessed(BaseModel):
    """A confidence/stability that is a sentinel placeholder."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["not_assessed"] = "not_assessed"
    reason: str


class AssessedStability(BaseModel):
    """Model stability that was actually assessed (multiple sensitivity runs)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["assessed"] = "assessed"
    runs_supporting: int = Field(ge=0)
    runs_total: int = Field(ge=1)
    share: float = Field(ge=0.0, le=1.0)


# Discriminated unions for the four uncertainty measures.
ConfidenceUnion = Annotated[AssessedConfidence | NotAssessed, Field(discriminator="kind")]
StabilityUnion = Annotated[AssessedStability | NotAssessed, Field(discriminator="kind")]


class ProbabilityView(BaseModel):
    """One outcome probability entry, preserving point-XOR-interval."""

    model_config = ConfigDict(extra="forbid")

    method: str
    point: float | None = Field(default=None, ge=0.0, le=1.0)
    interval_low: float | None = Field(default=None, ge=0.0, le=1.0)
    interval_high: float | None = Field(default=None, ge=0.0, le=1.0)
    adjustments: list[dict[str, object]] = Field(default_factory=list)


class UncertaintyView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_confidence: ConfidenceUnion
    evidence_confidence: ConfidenceUnion
    model_stability: StabilityUnion
    outcome_probabilities: dict[str, ProbabilityView] = Field(default_factory=dict)


# ── Rooms ────────────────────────────────────────────────────────────────────


class SourceView(BaseModel):
    """An evidence record joined with its critique scores/tiers/flags."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    claim: str
    publisher: str
    source_url: str
    source_type: str
    publication_date: str
    independence_group: str
    reliability: str
    directness: str
    # The record's own stated limitations.  Carried verbatim (SPEC-036): the
    # room previously showed only a grade-derived line, which read as a
    # limitation while actually restating the record's strengths.
    limitations: list[str] = Field(default_factory=list)
    source_tier: str | None = None
    authority_score: float | None = None
    flags: list[str] = Field(default_factory=list)
    cluster_share: float | None = None


class AssumptionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assumption_id: str
    claim: str
    type: str
    status: str
    materiality: str
    confidence: str
    evidence_for: list[str] = Field(default_factory=list)
    evidence_against: list[str] = Field(default_factory=list)
    estimate_point: float | None = None


class OptionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alternative: str
    rank: int
    rationale: str
    expected_value: float | None = None
    #: Whether this alternative was ruled out rather than ranked against the others.
    #: Derived here (see :func:`_is_eliminated`) so the presentation layer consumes a
    #: field instead of re-deriving it from prose.
    eliminated: bool = False


class ObjectionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objection_id: str
    target_section: str
    claim: str
    materiality: str
    resolution_status: str
    reasoning: str


class PreMortemView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    horizon: str
    assumed_outcome: str
    most_likely_failure_mode: str
    failure_modes: list[dict[str, object]] = Field(default_factory=list)


class TrackDivergenceView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    agreement: bool
    divergence_summary: str
    reconciled_alternative: str | None = None
    positions: list[dict[str, object]] = Field(default_factory=list)


class IssueNodeView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    parent_id: str | None = None
    question: str
    node_type: str
    materiality: str
    resolution_criteria: str
    covered: bool = False


class PlanView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_question: str
    nodes: list[IssueNodeView] = Field(default_factory=list)
    coverage_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    mece_justification: str = ""


class SourcesRoom(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[SourceView] = Field(default_factory=list)
    corpus_authority_mean: float | None = None
    independent_group_count: int | None = None
    max_cluster_share: float | None = None
    primary_source_share: float | None = None


class AssumptionsRoom(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assumptions: list[AssumptionView] = Field(default_factory=list)


class OptionsRoom(BaseModel):
    model_config = ConfigDict(extra="forbid")

    options: list[OptionView] = Field(default_factory=list)
    ev_table: dict[str, float] = Field(default_factory=dict)


class ChallengesRoom(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objections: list[ObjectionView] = Field(default_factory=list)
    premortem: PreMortemView | None = None
    track_divergence: TrackDivergenceView | None = None


class RoomsView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: SourcesRoom = Field(default_factory=SourcesRoom)
    assumptions: AssumptionsRoom = Field(default_factory=AssumptionsRoom)
    options: OptionsRoom = Field(default_factory=OptionsRoom)
    challenges: ChallengesRoom = Field(default_factory=ChallengesRoom)
    plan: PlanView | None = None


# ── Integrity ────────────────────────────────────────────────────────────────


class GateSummaryView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    outcome: str
    findings: list[dict[str, object]] = Field(default_factory=list)


class IntegrityView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gates: list[GateSummaryView] = Field(default_factory=list)
    review_accepted: bool | None = None
    review_outcome: str | None = None
    review_defects: list[dict[str, object]] = Field(default_factory=list)
    # Deterministic block-severity findings from the verification worksheet.
    # A review can be rejected purely on these while the reviewer's own
    # ``outcome`` is "pass", so without them the UI can only say "Rejected"
    # with no reason attached.
    review_blocking_findings: list[dict[str, object]] = Field(default_factory=list)
    disclosure: dict[str, object] | None = None


# ── History ──────────────────────────────────────────────────────────────────


class ThesisRevisionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int
    trigger: str
    preferred_alternative: str
    previous_alternative: str | None = None
    changed: bool
    rationale_digest: list[str] = Field(default_factory=list)
    recommendation_confidence: float
    evidence_confidence: float


class ApprovalRecordView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["framing", "final"]
    decision: str
    approved_by: str
    approved_at: str


class HistoryView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thesis_revisions: list[ThesisRevisionView] = Field(default_factory=list)
    approvals: list[ApprovalRecordView] = Field(default_factory=list)


# ── Effort ───────────────────────────────────────────────────────────────────


class EffortView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invocation_attempts: int = 0
    invocation_successes: int = 0
    retries: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    wall_clock_s: float | None = None
    budget_counters: dict[str, int] = Field(default_factory=dict)
    budget_caps: dict[str, int] = Field(default_factory=dict)
    by_role: dict[str, dict[str, int]] = Field(default_factory=dict)
    event_counts: dict[str, int] = Field(default_factory=dict)


# ── CaseView ─────────────────────────────────────────────────────────────────


class CaseView(BaseModel):
    """Versioned read model for one case, assembled from disk."""

    model_config = ConfigDict(extra="forbid")

    view_version: int = 1
    case_id: str
    phase: Phase
    needs_you: NeedsYou
    stage: str
    is_terminal: bool
    brief_sections: list[BriefSection] = Field(default_factory=list)
    uncertainty: UncertaintyView | None = None
    rooms: RoomsView = Field(default_factory=RoomsView)
    integrity: IntegrityView = Field(default_factory=IntegrityView)
    history: HistoryView = Field(default_factory=HistoryView)
    effort: EffortView = Field(default_factory=EffortView)


# ── Helpers ──────────────────────────────────────────────────────────────────

# Status-sort order for objections: open first.
_OBJECTION_STATUS_ORDER: dict[ObjectionResolutionStatus, int] = {
    ObjectionResolutionStatus.OPEN: 0,
    ObjectionResolutionStatus.PARTIALLY_RESOLVED: 1,
    ObjectionResolutionStatus.RESOLVED: 2,
    ObjectionResolutionStatus.DISMISSED: 3,
}


def _confidence_to_union(confidence: ConfidenceAssessment) -> ConfidenceUnion:
    if is_confidence_placeholder(confidence):
        return NotAssessed(reason=confidence.basis)
    return AssessedConfidence(value=confidence.value, basis=confidence.basis)


def _stability_to_union(stability: ModelStability) -> StabilityUnion:
    if is_model_stability_placeholder(stability):
        return NotAssessed(reason="single run; no sensitivity variation assessed")
    return AssessedStability(
        runs_supporting=stability.runs_supporting,
        runs_total=stability.runs_total,
        share=stability.share_of_sensitivity_runs_supporting_recommendation,
    )


def _probability_to_view(
    name: str,  # noqa: ARG001
    estimate: ProbabilityEstimate,
) -> ProbabilityView:
    adjustments: list[dict[str, object]] = []
    for adj in estimate.adjustments:
        adjustments.append(
            {
                "delta": adj.delta,
                "description": adj.description,
                "evidence_ids": list(adj.evidence_ids),
            }
        )
    return ProbabilityView(
        method=estimate.method.value,
        point=estimate.point,
        interval_low=estimate.interval_low,
        interval_high=estimate.interval_high,
        adjustments=adjustments,
    )


def _build_brief_sections(
    case: Case,
    final: FinalRecommendation | None,
    premortem: PreMortemReport | None,
    disclosure: DisclosureRecord | None,
    intake: IntakeRecord | None,
) -> list[BriefSection]:
    sections: list[BriefSection] = []
    if final is None:
        # No final recommendation yet — all sections pending.
        for key in BRIEF_SECTION_ORDER:
            sections.append(BriefSection(key=key, status="pending"))
        return sections

    def _block(provenance: str, text: str, citations: list[str] | None = None) -> BriefBlock:
        return BriefBlock(provenance=provenance, text=text, citation_ids=citations or [])

    # executive_recommendation
    sections.append(
        BriefSection(
            key="executive_recommendation",
            status="final",
            blocks=[
                _block(
                    PROVENANCE_RECOMMENDATION,
                    f"Recommended action: {final.recommended_action}",
                ),
                _block(PROVENANCE_RECOMMENDATION, f"Timing: {final.timing}"),
            ],
        )
    )

    # decision_confidence
    sections.append(
        BriefSection(
            key="decision_confidence",
            status="final",
            blocks=[
                _block(PROVENANCE_INTERPRETATION, final.decision_confidence_summary),
            ],
        )
    )

    # alternatives_considered
    alt_blocks: list[BriefBlock] = []
    for alt in sorted(final.alternatives_considered, key=lambda item: item.rank):
        alt_blocks.append(
            _block(
                PROVENANCE_INTERPRETATION,
                f"Rank {alt.rank}: `{alt.alternative}` — {alt.rationale}",
            )
        )
    sections.append(BriefSection(key="alternatives_considered", status="final", blocks=alt_blocks))

    # key_reasons
    sections.append(
        BriefSection(
            key="key_reasons",
            status="final",
            blocks=[_block(PROVENANCE_INTERPRETATION, reason) for reason in final.key_reasons],
        )
    )

    # scenario_analysis
    scenario_blocks: list[BriefBlock] = []
    for scenario in final.scenario_analysis:
        citations: list[str] = []
        for adj in scenario.probability.adjustments:
            citations.extend(adj.evidence_ids)
        scenario_blocks.append(
            _block(
                PROVENANCE_CALCULATION,
                f"`{scenario.scenario_name}`: {scenario.summary}",
                citations,
            )
        )
    sections.append(BriefSection(key="scenario_analysis", status="final", blocks=scenario_blocks))

    # quantitative_findings
    qf_blocks = (
        [_block(PROVENANCE_CALCULATION, finding) for finding in final.quantitative_findings]
        if final.quantitative_findings
        else [_block(PROVENANCE_CALCULATION, "No additional quantitative findings were provided.")]
    )
    sections.append(BriefSection(key="quantitative_findings", status="final", blocks=qf_blocks))

    # strongest_counterarguments
    if final.strongest_counterarguments:
        ca_blocks: list[BriefBlock] = []
        for ca in final.strongest_counterarguments:
            status = "resolved" if ca.resolved else "unresolved"
            ca_blocks.append(
                _block(
                    PROVENANCE_INTERPRETATION,
                    f"Counterargument ({status}): {ca.claim}",
                )
            )
            ca_blocks.append(
                _block(
                    PROVENANCE_INTERPRETATION,
                    f"Resolution/status detail: {ca.resolution}",
                )
            )
        sections.append(
            BriefSection(key="strongest_counterarguments", status="final", blocks=ca_blocks)
        )
    else:
        sections.append(
            BriefSection(
                key="strongest_counterarguments",
                status="final",
                blocks=[
                    _block(
                        PROVENANCE_INTERPRETATION,
                        "No material counterarguments were provided.",
                    )
                ],
            )
        )

    # premortem
    if premortem is not None:
        pm_blocks: list[BriefBlock] = []
        pm_blocks.append(_block(PROVENANCE_INTERPRETATION, f"Horizon: {premortem.horizon}"))
        pm_blocks.append(
            _block(
                PROVENANCE_INTERPRETATION,
                f"Assumed outcome: {premortem.assumed_outcome}",
            )
        )
        for mode in premortem.failure_modes:
            pm_blocks.append(
                _block(
                    PROVENANCE_INTERPRETATION,
                    f"{mode.failure_mode} (severity: {mode.severity.value})",
                    list(mode.referenced_evidence_ids),
                )
            )
        pm_blocks.append(
            _block(
                PROVENANCE_INTERPRETATION,
                f"Most likely failure mode: {premortem.most_likely_failure_mode}",
            )
        )
        sections.append(BriefSection(key="premortem", status="final", blocks=pm_blocks))
    else:
        sections.append(BriefSection(key="premortem", status="not_assessed"))

    # critical_assumptions
    if final.critical_assumptions:
        sections.append(
            BriefSection(
                key="critical_assumptions",
                status="final",
                blocks=[_block(PROVENANCE_ASSUMPTION, aid) for aid in final.critical_assumptions],
            )
        )
    else:
        sections.append(
            BriefSection(
                key="critical_assumptions",
                status="final",
                blocks=[_block(PROVENANCE_ASSUMPTION, "No critical assumptions were listed.")],
            )
        )

    # recommendation_change_triggers
    if final.recommendation_change_triggers:
        sections.append(
            BriefSection(
                key="recommendation_change_triggers",
                status="final",
                blocks=[
                    _block(PROVENANCE_INTERPRETATION, trigger)
                    for trigger in final.recommendation_change_triggers
                ],
            )
        )
    else:
        sections.append(
            BriefSection(
                key="recommendation_change_triggers",
                status="final",
                blocks=[
                    _block(
                        PROVENANCE_INTERPRETATION,
                        "No explicit recommendation-change triggers were provided.",
                    )
                ],
            )
        )

    # next_actions
    sections.append(
        BriefSection(
            key="next_actions",
            status="final",
            blocks=[
                _block(
                    PROVENANCE_RECOMMENDATION,
                    f"{action.action} — {action.owner}, by {action.by_date.isoformat()}. "
                    f"First step: {action.first_step}",
                )
                for action in final.next_actions
            ],
        )
    )

    # user_supplied_inputs
    user_inputs = _user_supplied_inputs(intake)
    if user_inputs:
        sections.append(
            BriefSection(
                key="user_supplied_inputs",
                status="final",
                blocks=[_block(PROVENANCE_USER_INPUT, ui) for ui in user_inputs],
            )
        )
    else:
        sections.append(BriefSection(key="user_supplied_inputs", status="not_assessed"))

    # budget_depth_stop_disclosure
    if disclosure is not None:
        stop_reasons = ", ".join(reason.value for reason in disclosure.stop_reasons)
        exhausted = ", ".join(disclosure.exhausted_dimensions)
        sections.append(
            BriefSection(
                key="budget_depth_stop_disclosure",
                status="final",
                blocks=[
                    _block(
                        PROVENANCE_INTERPRETATION,
                        f"Stop reasons: {stop_reasons}.",
                    ),
                    _block(
                        PROVENANCE_INTERPRETATION,
                        f"Exhausted dimensions: {exhausted}.",
                    ),
                ],
            )
        )
    else:
        sections.append(BriefSection(key="budget_depth_stop_disclosure", status="not_assessed"))

    # evidence_and_citations
    sections.append(
        BriefSection(
            key="evidence_and_citations",
            status="final",
            blocks=[
                _block(
                    PROVENANCE_SOURCED_FACT,
                    f"Inline evidence references: {len(final.citations)} citation(s).",
                    list(final.citations),
                )
            ],
        )
    )

    return sections


def _user_supplied_inputs(intake: IntakeRecord | None) -> list[str]:
    if intake is None:
        return []
    inputs: list[str] = []
    if intake.decision_question:
        inputs.append(f"Decision question: {intake.decision_question}")
    if intake.alternatives_mentioned:
        inputs.append(f"Alternatives mentioned: {', '.join(intake.alternatives_mentioned)}")
    if intake.objectives:
        inputs.append(f"Objectives: {', '.join(intake.objectives)}")
    if intake.constraints:
        inputs.append(f"Constraints: {', '.join(intake.constraints)}")
    return inputs


def _build_uncertainty(
    final: FinalRecommendation | None,
    prelim: PreliminaryRecommendation | None,
) -> UncertaintyView | None:
    source = final or prelim
    if source is None:
        return None
    return UncertaintyView(
        recommendation_confidence=_confidence_to_union(source.recommendation_confidence),
        evidence_confidence=_confidence_to_union(source.evidence_confidence),
        model_stability=_stability_to_union(source.model_stability),
        outcome_probabilities={
            name: _probability_to_view(name, est)
            for name, est in sorted(source.outcome_probabilities.items())
        },
    )


def _build_sources_room(
    case: Case,
    critique: EvidenceCritique | None,
) -> SourcesRoom:
    evidence = case.list_artifacts(EvidenceRecord)
    if not evidence:
        return SourcesRoom()

    # Join critique scores/tiers/flags by evidence_id.
    score_by_id: dict[str, EvidenceAuthorityScore] = {}
    flags_by_id: dict[str, list[str]] = {}
    cluster_share_by_group: dict[str, float] = {}
    if critique is not None:
        for score in critique.scored:
            score_by_id[score.evidence_id] = score
            flags_by_id[score.evidence_id] = [flag.value for flag in score.flags]
        for cluster in critique.clusters:
            cluster_share_by_group[cluster.independence_group] = cluster.share_of_corpus

    sources: list[SourceView] = []
    for record in evidence:
        auth_score: EvidenceAuthorityScore | None = score_by_id.get(record.evidence_id)
        source_tier = auth_score.source_tier if auth_score is not None else None
        authority_score = auth_score.authority_score if auth_score is not None else None
        flags = flags_by_id.get(record.evidence_id, [])
        cluster_share = cluster_share_by_group.get(record.independence_group)
        sources.append(
            SourceView(
                evidence_id=record.evidence_id,
                claim=record.claim,
                publisher=record.publisher,
                source_url=record.source_url,
                source_type=record.source_type.value,
                publication_date=record.publication_date.isoformat(),
                independence_group=record.independence_group,
                reliability=record.reliability.value,
                directness=record.directness.value,
                limitations=list(record.limitations),
                source_tier=str(source_tier.value) if source_tier is not None else None,
                authority_score=float(authority_score) if authority_score is not None else None,
                flags=flags,
                cluster_share=cluster_share,
            )
        )

    return SourcesRoom(
        sources=sources,
        corpus_authority_mean=critique.corpus_authority_mean if critique else None,
        independent_group_count=critique.independent_group_count if critique else None,
        max_cluster_share=critique.max_cluster_share if critique else None,
        primary_source_share=critique.primary_source_share if critique else None,
    )


def _build_assumptions_room(case: Case) -> AssumptionsRoom:
    records = case.list_artifacts(AssumptionRecord)
    views: list[AssumptionView] = []
    for record in records:
        views.append(
            AssumptionView(
                assumption_id=record.assumption_id,
                claim=record.claim,
                type=record.type.value,
                status=record.status.value,
                materiality=record.materiality.value,
                confidence=record.confidence.value,
                evidence_for=list(record.evidence_for),
                evidence_against=list(record.evidence_against),
                estimate_point=record.estimate.point,
            )
        )
    return AssumptionsRoom(assumptions=views)


#: Words a synthesizer uses when an alternative was ruled out rather than ranked.
#: `AlternativeAssessment` carries no elimination flag, so this is inferred. Keeping
#: the inference here — one place, tested — is the point: the room used to run its own
#: regex over the same prose, which put an undeclared rule in the presentation layer.
#: Promoting this to a field the synthesizer states outright needs a spec; until then
#: `eliminated` is a derived hint, not an agent assertion.
_ELIMINATION_MARKERS = (
    "eliminat",
    "ruled out",
    "rule out",
    "discarded",
    "not viable",
    "non-viable",
    "nonviable",
    "dropped",
    "excluded",
    "infeasible",
    "not feasible",
)


def _is_eliminated(rationale: str) -> bool:
    """True when the rationale says this alternative was ruled out, not ranked."""
    lowered = rationale.lower()
    return any(marker in lowered for marker in _ELIMINATION_MARKERS)


def _build_options_room(
    final: FinalRecommendation | None,
    analysis_results: list[AnalysisResult],
) -> OptionsRoom:
    options: list[OptionView] = []
    if final is not None:
        for alt in sorted(final.alternatives_considered, key=lambda item: item.rank):
            options.append(
                OptionView(
                    alternative=alt.alternative,
                    rank=alt.rank,
                    rationale=alt.rationale,
                    eliminated=_is_eliminated(alt.rationale),
                )
            )

    ev_table: dict[str, float] = {}
    if analysis_results:
        # Use the first analysis result's EV table (canonical for single-decision cases).
        ev_table = dict(analysis_results[0].expected_values_by_alternative)
        # Join EV onto options.
        for opt in options:
            opt.expected_value = ev_table.get(opt.alternative)

    return OptionsRoom(options=options, ev_table=ev_table)


def _build_challenges_room(
    case: Case,
    premortem: PreMortemReport | None,
    track_divergence: TrackDivergence | None,
) -> ChallengesRoom:
    objections = case.list_artifacts(ObjectionRecord)
    objection_views = sorted(
        objections,
        key=lambda o: (_OBJECTION_STATUS_ORDER.get(o.resolution_status, 99), o.objection_id),
    )
    ov_list = [
        ObjectionView(
            objection_id=o.objection_id,
            target_section=o.target_section,
            claim=o.claim,
            materiality=o.materiality.value,
            resolution_status=o.resolution_status.value,
            reasoning=o.reasoning,
        )
        for o in objection_views
    ]

    pm_view: PreMortemView | None = None
    if premortem is not None:
        pm_view = PreMortemView(
            horizon=premortem.horizon,
            assumed_outcome=premortem.assumed_outcome,
            most_likely_failure_mode=premortem.most_likely_failure_mode,
            failure_modes=[
                {
                    "failure_mode": mode.failure_mode,
                    "severity": mode.severity.value,
                    "probability_point": mode.probability.point,
                    "narrative": mode.narrative,
                    "leading_indicators": list(mode.leading_indicators),
                }
                for mode in premortem.failure_modes
            ],
        )

    td_view: TrackDivergenceView | None = None
    if track_divergence is not None:
        td_view = TrackDivergenceView(
            stage=track_divergence.stage,
            agreement=track_divergence.agreement,
            divergence_summary=track_divergence.divergence_summary,
            reconciled_alternative=track_divergence.reconciled_alternative,
            positions=[
                {
                    "track_id": pos.track_id,
                    "model": pos.model,
                    "model_family": pos.model_family,
                    "preferred_alternative": pos.preferred_alternative,
                    "top_reason": pos.top_reason,
                    "recommendation_confidence": pos.recommendation_confidence,
                }
                for pos in track_divergence.positions
            ],
        )

    return ChallengesRoom(objections=ov_list, premortem=pm_view, track_divergence=td_view)


def _build_plan_view(
    issue_tree: IssueTree | None,
    tasks: list[TaskRecord],
) -> PlanView | None:
    if issue_tree is None:
        return None

    # Coverage: a leaf node is covered if at least one completed task references it.
    # TaskRecord does not carry node_id directly, but we approximate coverage by
    # counting completed tasks vs total leaf nodes.  A more precise join would
    # require a task->node mapping which the current schema does not store.
    leaf_ids = set(issue_tree.leaf_node_ids())
    completed_task_count = sum(1 for t in tasks if t.status.value == "completed")
    # Heuristic: each leaf needs at least one completed task.
    coverage = min(completed_task_count / len(leaf_ids), 1.0) if leaf_ids else 0.0

    # Mark nodes covered if there are completed tasks (simple heuristic).
    covered = completed_task_count > 0
    nodes = [
        IssueNodeView(
            node_id=node.node_id,
            parent_id=node.parent_id,
            question=node.question,
            node_type=node.node_type.value,
            materiality=node.materiality.value,
            resolution_criteria=node.resolution_criteria,
            covered=covered if node.node_id in leaf_ids else True,
        )
        for node in issue_tree.nodes
    ]

    return PlanView(
        decision_question=issue_tree.decision_question,
        nodes=nodes,
        coverage_fraction=coverage,
        mece_justification=issue_tree.mece_justification,
    )


def _build_integrity(
    case: Case,
    state: CaseState,
    review: ReviewReport | None,
    disclosure: DisclosureRecord | None,
) -> IntegrityView:
    gate_reports = case.list_artifacts(GateReport)
    gates = [
        GateSummaryView(
            stage=report.stage,
            outcome=report.outcome.value,
            findings=[
                {
                    "check_id": f.check_id,
                    "severity": f.severity.value,
                    "message": f.message,
                    "target_ids": list(f.target_ids),
                }
                for f in report.findings
            ],
        )
        for report in sorted(gate_reports, key=lambda r: r.stage)
    ]

    review_defects: list[dict[str, object]] = []
    review_outcome: str | None = None
    if review is not None:
        review_outcome = review.outcome.value
        review_defects = [
            {
                "defect_type": d.defect_type.value,
                "target_id": d.target_id,
                "explanation": d.explanation,
            }
            for d in review.defects
        ]

    # The worksheet's block-severity findings are the other way a review can be
    # rejected (see ``review_is_acceptable``), so surface them alongside the
    # reviewer-reported defects.
    worksheets = case.list_artifacts(VerificationWorksheet)
    review_blocking_findings: list[dict[str, object]] = [
        {
            "check_id": f.check_id,
            "severity": f.severity.value,
            "message": f.message,
            "target_ids": list(f.target_ids),
        }
        for worksheet in worksheets
        for f in worksheet.deterministic_findings
        if f.severity is GateSeverity.BLOCK
    ]

    disclosure_dict: dict[str, object] | None = None
    if disclosure is not None:
        disclosure_dict = {
            "stop_reasons": [reason.value for reason in disclosure.stop_reasons],
            "exhausted_dimensions": list(disclosure.exhausted_dimensions),
        }

    return IntegrityView(
        gates=gates,
        review_accepted=state.review_accepted,
        review_outcome=review_outcome,
        review_defects=review_defects,
        review_blocking_findings=review_blocking_findings,
        disclosure=disclosure_dict,
    )


def _build_history(
    case: Case,
    framing_approval: FramingApproval | None,
    final_approval: FinalApproval | None,
) -> HistoryView:
    revisions = sorted(case.list_artifacts(ThesisRevision), key=lambda item: item.revision)
    rev_views = [
        ThesisRevisionView(
            revision=r.revision,
            trigger=r.trigger.value,
            preferred_alternative=r.preferred_alternative,
            previous_alternative=r.previous_alternative,
            changed=r.changed,
            rationale_digest=list(r.rationale_digest),
            recommendation_confidence=r.recommendation_confidence,
            evidence_confidence=r.evidence_confidence,
        )
        for r in revisions
    ]

    approvals: list[ApprovalRecordView] = []
    if framing_approval is not None:
        approvals.append(
            ApprovalRecordView(
                kind="framing",
                decision=framing_approval.decision.value,
                approved_by=framing_approval.approved_by,
                approved_at=framing_approval.approved_at.isoformat(),
            )
        )
    if final_approval is not None:
        approvals.append(
            ApprovalRecordView(
                kind="final",
                decision=final_approval.decision.value,
                approved_by=final_approval.approved_by,
                approved_at=final_approval.approved_at.isoformat(),
            )
        )

    return HistoryView(thesis_revisions=rev_views, approvals=approvals)


def _read_audit_events(case: Case) -> list[dict[str, Any]]:
    audit_path = case.root / "audit.jsonl"
    if not audit_path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            events.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return events


def _build_effort(case: Case, state: CaseState) -> EffortView:
    events = _read_audit_events(case)

    # Deduplicate role_invocation_attempt events (same ts+actor+attempt).
    seen: set[tuple[str, str, int]] = set()
    invocations: list[dict[str, Any]] = []
    for event in events:
        if event.get("event_type") != "role_invocation_attempt":
            continue
        payload: dict[str, Any] = event.get("payload") or {}
        key = (
            str(event.get("ts")),
            str(event.get("actor")),
            int(payload.get("attempt") or 0),
        )
        if key in seen:
            continue
        seen.add(key)
        invocations.append(event)

    attempts = len(invocations)
    successes = sum(1 for e in invocations if (e.get("payload") or {}).get("status") == "ok")
    retries = sum(1 for e in invocations if int((e.get("payload") or {}).get("attempt") or 1) > 1)

    input_tokens = 0
    output_tokens = 0
    for e in invocations:
        usage = e.get("usage") or {}
        if isinstance(usage, dict):
            input_tokens += int(usage.get("input_tokens") or 0)
            output_tokens += int(usage.get("output_tokens") or 0)

    # Wall clock from event timestamps.
    timestamps: list[datetime] = []
    for e in events:
        ts_raw = e.get("ts")
        if isinstance(ts_raw, str):
            try:
                timestamps.append(datetime.fromisoformat(ts_raw.replace("Z", "+00:00")))
            except ValueError:
                pass
    wall_clock_s: float | None = None
    if len(timestamps) >= 2:
        wall_clock_s = (max(timestamps) - min(timestamps)).total_seconds()

    # Per-role breakdown.
    by_role: dict[str, dict[str, int]] = {}
    for e in invocations:
        actor = str(e.get("actor") or "unknown")
        usage = e.get("usage") or {}
        entry = by_role.setdefault(
            actor,
            {"attempts": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        )
        entry["attempts"] += 1
        if isinstance(usage, dict):
            entry["input_tokens"] += int(usage.get("input_tokens") or 0)
            entry["output_tokens"] += int(usage.get("output_tokens") or 0)
            entry["total_tokens"] += int(usage.get("total_tokens") or 0)

    event_counts = dict(Counter(str(e.get("event_type")) for e in events).most_common())

    # Budget caps from BudgetConfig defaults (the standard profile).
    from orchestrator.budget import BudgetConfig  # noqa: PLC0415

    default_config = BudgetConfig()
    budget_caps = {
        "max_agent_invocations": default_config.max_agent_invocations,
        "max_concurrent_workers": default_config.max_concurrent_workers,
        "max_repair_cycles": default_config.max_repair_cycles,
        "max_research_tasks": default_config.max_research_tasks,
        "max_high_tier_calls": default_config.max_high_tier_calls,
        "max_wall_clock_s": default_config.max_wall_clock_s,
    }

    return EffortView(
        invocation_attempts=attempts,
        invocation_successes=successes,
        retries=retries,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        wall_clock_s=wall_clock_s,
        budget_counters=dict(state.budget_counters),
        budget_caps=budget_caps,
        by_role=by_role,
        event_counts=event_counts,
    )


# ── Main entry point ─────────────────────────────────────────────────────────


def build_case_view(case: Case) -> CaseView:
    """Assemble a CaseView from a case directory.

    Reads all artifacts from the case and projects them into a single
    versioned document.  Pure function: no side effects, no caching.
    """
    state = load_case_state(case)

    # Load all artifacts (each is a no-op if the file is absent).
    intake_list = case.list_artifacts(IntakeRecord)
    intake = intake_list[0] if intake_list else None
    final_list = case.list_artifacts(FinalRecommendation)
    final = final_list[0] if final_list else None
    prelim_list = case.list_artifacts(PreliminaryRecommendation)
    prelim = prelim_list[0] if prelim_list else None

    premortem_list = case.list_artifacts(PreMortemReport)
    premortem = premortem_list[0] if premortem_list else None
    track_div_list = case.list_artifacts(TrackDivergence)
    track_divergence = track_div_list[0] if track_div_list else None
    issue_tree_list = case.list_artifacts(IssueTree)
    issue_tree = issue_tree_list[0] if issue_tree_list else None
    critique_list = case.list_artifacts(EvidenceCritique)
    critique = critique_list[0] if critique_list else None
    review_list = case.list_artifacts(ReviewReport)
    review = review_list[0] if review_list else None
    disclosure_list = case.list_artifacts(DisclosureRecord)
    disclosure = disclosure_list[0] if disclosure_list else None

    framing_approval_list = case.list_artifacts(FramingApproval)
    framing_approval = framing_approval_list[0] if framing_approval_list else None
    final_approval_list = case.list_artifacts(FinalApproval)
    final_approval = final_approval_list[0] if final_approval_list else None

    analysis_results = case.list_artifacts(AnalysisResult)
    tasks = case.list_artifacts(TaskRecord)

    # Assemble sections.
    brief_sections = _build_brief_sections(case, final, premortem, disclosure, intake)
    uncertainty = _build_uncertainty(final, prelim)

    rooms = RoomsView(
        sources=_build_sources_room(case, critique),
        assumptions=_build_assumptions_room(case),
        options=_build_options_room(final, analysis_results),
        challenges=_build_challenges_room(case, premortem, track_divergence),
        plan=_build_plan_view(issue_tree, tasks),
    )

    integrity = _build_integrity(case, state, review, disclosure)
    history = _build_history(case, framing_approval, final_approval)
    effort = _build_effort(case, state)

    return CaseView(
        case_id=case.root.name,
        phase=_phase_for_stage(state.stage),
        needs_you=_needs_you_for_state(state),
        stage=state.stage.value,
        is_terminal=state.stage in _TERMINAL_STAGES,
        brief_sections=brief_sections,
        uncertainty=uncertainty,
        rooms=rooms,
        integrity=integrity,
        history=history,
        effort=effort,
    )
