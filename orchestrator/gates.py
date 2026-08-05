"""Deterministic process gates run at stage boundaries.

The Process Auditor previously had a mandate but no schedule and no enforcement.
These gates give it both: they run after every substantive stage, they record what
they found, and a blocking finding has consequences (tasks are cancelled, and the
stop evaluator is told that a critical gap is open so the case cannot quietly
conclude on a broken chain).
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

from orchestrator.artifacts import (
    AnalysisResult,
    AssumptionRecord,
    AuditEvent,
    DecisionSpec,
    EvidenceCritique,
    EvidenceRecord,
    FinalRecommendation,
    GateFinding,
    GateReport,
    GateSeverity,
    IssueTree,
    Level,
    ObjectionRecord,
    PreliminaryRecommendation,
    TaskRecord,
    TaskStatus,
    max_severity,
)
from orchestrator.case_store import Case
from orchestrator.task_graph import TaskGraph
from orchestrator.value_model import rank_divergence

_REF_ID_RE = re.compile(r"\b(?:E|A)-\d+\b")

CLUSTER_BLOCK_THRESHOLD = 0.6
CLUSTER_WARN_THRESHOLD = 0.4
CONFIDENCE_OVERCLAIM_MARGIN = 0.25
NEAR_TERM_ACTION_DAYS = 30
_PLACEHOLDER_OWNERS = frozenset(
    {"tbd", "tba", "unknown", "n/a", "na", "none", "someone", "somebody", "unassigned", "owner"}
)
ISSUE_COVERAGE_WARN_THRESHOLD = 0.5


def extract_reference_ids(text: str) -> list[str]:
    return _REF_ID_RE.findall(text)


def _known_ids(case: Case) -> set[str]:
    evidence = {record.evidence_id for record in case.list_artifacts(EvidenceRecord)}
    assumptions = {record.assumption_id for record in case.list_artifacts(AssumptionRecord)}
    return evidence | assumptions


def _check_citation_integrity(case: Case) -> list[GateFinding]:
    known = _known_ids(case)
    if not known:
        return []

    findings: list[GateFinding] = []
    claims: list[tuple[str, str]] = []

    prelim = case.list_artifacts(PreliminaryRecommendation)
    if prelim:
        claims.extend(
            (f"preliminary_recommendation.rationale[{index}]", reason)
            for index, reason in enumerate(prelim[0].rationale)
        )
    final = case.list_artifacts(FinalRecommendation)
    if final:
        claims.extend(
            (f"final_recommendation.key_reasons[{index}]", reason)
            for index, reason in enumerate(final[0].key_reasons)
        )

    uncited: list[str] = []
    dangling: list[str] = []
    for target, text in claims:
        referenced = extract_reference_ids(text)
        if not referenced:
            uncited.append(target)
            continue
        if not any(ref_id in known for ref_id in referenced):
            dangling.append(target)

    if uncited:
        findings.append(
            GateFinding(
                check_id="citation_integrity.uncited_claim",
                severity=GateSeverity.BLOCK,
                message=(
                    f"{len(uncited)} material claim(s) carry no E-/A- citation while "
                    f"{len(known)} citable records exist."
                ),
                target_ids=uncited,
            )
        )
    if dangling:
        findings.append(
            GateFinding(
                check_id="citation_integrity.dangling_only",
                severity=GateSeverity.BLOCK,
                message=f"{len(dangling)} claim(s) cite only IDs that do not exist.",
                target_ids=dangling,
            )
        )
    return findings


def _check_assumption_ledger(case: Case) -> list[GateFinding]:
    assumptions = case.list_artifacts(AssumptionRecord)
    if not assumptions:
        return [
            GateFinding(
                check_id="assumption_ledger.empty",
                severity=GateSeverity.WARN,
                message=(
                    "No assumptions were registered. A recommendation with no recorded "
                    "assumptions is almost certainly hiding them in prose."
                ),
                target_ids=[],
            )
        ]

    unsupported = [
        record.assumption_id
        for record in assumptions
        if record.materiality is Level.HIGH and not record.evidence_for
    ]
    if unsupported:
        return [
            GateFinding(
                check_id="assumption_ledger.unsupported_high_materiality",
                severity=GateSeverity.WARN,
                message=(
                    f"{len(unsupported)} high-materiality assumption(s) carry no supporting "
                    "evidence."
                ),
                target_ids=unsupported,
            )
        ]
    return []


def _check_evidence_independence(case: Case) -> list[GateFinding]:
    critiques = case.list_artifacts(EvidenceCritique)
    if not critiques:
        return []
    critique = critiques[0]
    if critique.evidence_count == 0:
        return [
            GateFinding(
                check_id="evidence.absent",
                severity=GateSeverity.BLOCK,
                message="Investigation produced no evidence records.",
                target_ids=[],
            )
        ]

    findings: list[GateFinding] = []
    if critique.max_cluster_share > CLUSTER_BLOCK_THRESHOLD:
        findings.append(
            GateFinding(
                check_id="evidence.independence_concentration",
                severity=GateSeverity.BLOCK,
                message=(
                    f"One independence group supplies {critique.max_cluster_share:.0%} of the "
                    "corpus; this is one source, not corroboration."
                ),
                target_ids=[],
            )
        )
    elif critique.max_cluster_share > CLUSTER_WARN_THRESHOLD:
        findings.append(
            GateFinding(
                check_id="evidence.independence_concentration",
                severity=GateSeverity.WARN,
                message=(
                    f"One independence group supplies {critique.max_cluster_share:.0%} of the "
                    "corpus."
                ),
                target_ids=[],
            )
        )

    if critique.weakest_evidence_ids:
        findings.append(
            GateFinding(
                check_id="evidence.low_authority_records",
                severity=GateSeverity.WARN,
                message=(
                    f"{len(critique.weakest_evidence_ids)} record(s) fall below the source "
                    "authority floor."
                ),
                target_ids=critique.weakest_evidence_ids,
            )
        )
    return findings


def _check_analysis_presence(case: Case) -> list[GateFinding]:
    if case.list_artifacts(AnalysisResult):
        return []
    return [
        GateFinding(
            check_id="analysis.absent",
            severity=GateSeverity.WARN,
            message=(
                "No reproducible analysis was produced; any quantitative claim downstream "
                "rests on prose arithmetic."
            ),
            target_ids=[],
        )
    ]


def _check_confidence_coherence(case: Case) -> list[GateFinding]:
    findings: list[GateFinding] = []
    for label, records in (
        ("preliminary_recommendation", case.list_artifacts(PreliminaryRecommendation)),
        ("final_recommendation", case.list_artifacts(FinalRecommendation)),
    ):
        if not records:
            continue
        record = records[0]
        gap = record.recommendation_confidence.value - record.evidence_confidence.value
        if gap > CONFIDENCE_OVERCLAIM_MARGIN:
            findings.append(
                GateFinding(
                    check_id="confidence.overclaim",
                    severity=GateSeverity.WARN,
                    message=(
                        f"{label}: recommendation confidence "
                        f"({record.recommendation_confidence.value:.2f}) exceeds evidence "
                        f"confidence ({record.evidence_confidence.value:.2f}) by more than "
                        f"{CONFIDENCE_OVERCLAIM_MARGIN:.2f}."
                    ),
                    target_ids=[label],
                )
            )
    return findings


def _check_objection_resolution(case: Case) -> list[GateFinding]:
    open_material = [
        record.objection_id
        for record in case.list_artifacts(ObjectionRecord)
        if record.materiality is Level.HIGH and record.resolution_status.value == "open"
    ]
    if not open_material:
        return []
    return [
        GateFinding(
            check_id="objections.open_high_materiality",
            severity=GateSeverity.WARN,
            message=f"{len(open_material)} high-materiality objection(s) remain open.",
            target_ids=open_material,
        )
    ]


def _check_issue_coverage(case: Case) -> list[GateFinding]:
    trees = case.list_artifacts(IssueTree)
    if not trees:
        return []
    from orchestrator.issue_tree import compute_coverage

    coverage = compute_coverage(trees[0], case.list_artifacts(TaskRecord))
    if coverage.covered_share >= ISSUE_COVERAGE_WARN_THRESHOLD:
        return []
    return [
        GateFinding(
            check_id="issue_tree.low_coverage",
            severity=GateSeverity.WARN,
            message=(
                f"Only {coverage.covered_share:.0%} of leaf sub-questions have completed work."
            ),
            target_ids=list(coverage.uncovered_node_ids),
        )
    ]


def _check_task_health(case: Case) -> tuple[list[GateFinding], list[str]]:
    """Failed material work blocks; failed immaterial work is cancelled, not retried."""
    failed = [
        record
        for record in case.list_artifacts(TaskRecord)
        if record.status in {TaskStatus.FAILED, TaskStatus.BLOCKED}
    ]
    if not failed:
        return [], []

    material = [record.task_id for record in failed if record.materiality is Level.HIGH]
    immaterial = [record.task_id for record in failed if record.materiality is not Level.HIGH]

    findings: list[GateFinding] = []
    if material:
        findings.append(
            GateFinding(
                check_id="tasks.material_failure",
                severity=GateSeverity.BLOCK,
                message=f"{len(material)} high-materiality task(s) failed or are blocked.",
                target_ids=material,
            )
        )
    if immaterial:
        findings.append(
            GateFinding(
                check_id="tasks.immaterial_failure_cancelled",
                severity=GateSeverity.WARN,
                message=(
                    f"{len(immaterial)} low/medium-materiality task(s) failed and were "
                    "cancelled rather than retried."
                ),
                target_ids=immaterial,
            )
        )
    return findings, immaterial


def _check_missing_critical_assumptions(case: Case) -> list[GateFinding]:
    """Warn when the assumption ledger has high-materiality assumptions but
    FinalRecommendation.critical_assumptions is empty."""
    recs = case.list_artifacts(FinalRecommendation)
    if not recs:
        return []
    rec = recs[0]
    if rec.critical_assumptions:
        return []
    assumptions = case.list_artifacts(AssumptionRecord)
    high_materiality = [a.assumption_id for a in assumptions if a.materiality is Level.HIGH]
    if not high_materiality:
        return []
    return [
        GateFinding(
            check_id="synthesis.missing_critical_assumptions",
            severity=GateSeverity.WARN,
            message=(
                f"The assumption ledger has {len(high_materiality)} high-materiality "
                "assumption(s) but the FinalRecommendation lists no critical assumptions. "
                "The synthesizer should reference load-bearing A- ids."
            ),
            target_ids=high_materiality,
        )
    ]


def _check_action_plan(case: Case, as_of: date) -> list[GateFinding]:
    """Check that the action plan is executable rather than aspirational.

    ``owner`` and ``by_date`` are schema-required, so absence is impossible here.
    What the schema cannot catch is a vacuous owner ("TBD") or a plan whose
    earliest action sits months out, which is the practical form of the same
    failure.
    """
    recs = case.list_artifacts(FinalRecommendation)
    if not recs:
        return []
    actions = recs[0].next_actions
    findings: list[GateFinding] = []

    placeholder = [
        action.action_id
        for action in actions
        if action.owner.strip().lower().rstrip("?.") in _PLACEHOLDER_OWNERS
    ]
    if placeholder:
        findings.append(
            GateFinding(
                check_id="action_plan.missing_owner",
                severity=GateSeverity.WARN,
                message=(
                    f"{len(placeholder)} next action(s) name a placeholder owner. "
                    "An action nobody owns will not happen."
                ),
                target_ids=placeholder,
            )
        )

    earliest = min((action.by_date for action in actions), default=None)
    if earliest is not None and (earliest - as_of).days > NEAR_TERM_ACTION_DAYS:
        findings.append(
            GateFinding(
                check_id="action_plan.no_near_term_action",
                severity=GateSeverity.WARN,
                message=(
                    f"The earliest next action is due {earliest.isoformat()}, more than "
                    f"{NEAR_TERM_ACTION_DAYS} days out. A plan with no near-term step "
                    "gives the decision owner nothing to do now."
                ),
                target_ids=[action.action_id for action in actions],
            )
        )

    stale = [action.action_id for action in actions if action.by_date < as_of]
    if stale:
        findings.append(
            GateFinding(
                check_id="action_plan.date_in_past",
                severity=GateSeverity.WARN,
                message=f"{len(stale)} next action(s) are dated before the case completed.",
                target_ids=stale,
            )
        )
    return findings


def _check_value_model(case: Case) -> list[GateFinding]:
    """Compare the weighted ranking against the ranking the synthesizer stated.

    A mismatch is a finding, never an override: deterministic code does not silently
    reorder a recommendation, because a disagreement usually means the value model is
    wrong rather than the judgment.
    """
    specs = case.list_artifacts(DecisionSpec)
    recs = case.list_artifacts(FinalRecommendation)
    if not specs or not recs:
        return []
    weights = specs[0].objective_weights
    if not weights:
        return []

    assessments = recs[0].alternatives_considered
    divergence = rank_divergence(weights, assessments)
    findings: list[GateFinding] = []

    if divergence.unscored:
        findings.append(
            GateFinding(
                check_id="value_model.unscored_alternative",
                severity=GateSeverity.WARN,
                message=(
                    f"{len(divergence.unscored)} alternative(s) carry no objective_scores, so "
                    "they were excluded from the weighted ranking rather than scored as zero."
                ),
                target_ids=list(divergence.unscored),
            )
        )

    if not divergence.agrees:
        detail = ", ".join(
            f"{alt} (weighted {computed}, stated {stated})"
            for alt, computed, stated in divergence.positions
        )
        findings.append(
            GateFinding(
                check_id="value_model.rank_divergence",
                severity=GateSeverity.WARN,
                message=(
                    "The ranking implied by the decision owner's objective weights disagrees "
                    f"with the ranking the synthesizer stated: {detail}. Either revise the "
                    "scores or say in key_reasons why the weighted model does not capture "
                    "this decision."
                ),
                target_ids=[alt for alt, _, _ in divergence.positions],
            )
        )
    return findings


_CHECKS_BY_STAGE: dict[str, tuple[str, ...]] = {
    "investigation": ("task_health", "analysis_presence"),
    "evidence_critique": ("evidence_independence",),
    "assumption_ledger": ("assumption_ledger", "issue_coverage"),
    "preliminary_recommendation": ("citation_integrity", "confidence_coherence"),
    "challenge": ("objection_resolution",),
    "repair": ("citation_integrity", "task_health"),
    "synthesis": (
        "citation_integrity",
        "confidence_coherence",
        "objection_resolution",
        "missing_critical_assumptions",
        "action_plan",
        "value_model",
    ),
}


def run_stage_gate(
    case: Case,
    stage: str,
    *,
    task_graph: TaskGraph | None = None,
    as_of: date | None = None,
) -> GateReport:
    """Run the checks registered for ``stage`` and persist the report."""
    checks = _CHECKS_BY_STAGE.get(stage, ())
    findings: list[GateFinding] = []
    cancellable: list[str] = []

    for check in checks:
        if check == "citation_integrity":
            findings.extend(_check_citation_integrity(case))
        elif check == "assumption_ledger":
            findings.extend(_check_assumption_ledger(case))
        elif check == "evidence_independence":
            findings.extend(_check_evidence_independence(case))
        elif check == "analysis_presence":
            findings.extend(_check_analysis_presence(case))
        elif check == "confidence_coherence":
            findings.extend(_check_confidence_coherence(case))
        elif check == "objection_resolution":
            findings.extend(_check_objection_resolution(case))
        elif check == "issue_coverage":
            findings.extend(_check_issue_coverage(case))
        elif check == "task_health":
            task_findings, immaterial = _check_task_health(case)
            findings.extend(task_findings)
            cancellable.extend(immaterial)
        elif check == "missing_critical_assumptions":
            findings.extend(_check_missing_critical_assumptions(case))
        elif check == "action_plan":
            findings.extend(_check_action_plan(case, as_of or datetime.now(UTC).date()))
        elif check == "value_model":
            findings.extend(_check_value_model(case))

    cancelled: list[str] = []
    if cancellable and task_graph is not None:
        cancelled = sorted(
            task_graph.cancel_tasks(cancellable, reason=f"gate:{stage}:immaterial_failure")
        )

    report = GateReport(
        stage=stage,
        outcome=max_severity([finding.severity for finding in findings]),
        findings=findings,
        cancelled_task_ids=cancelled,
        checked_at=datetime.now(UTC),
    )
    case.write_artifact(report)
    case.audit(
        AuditEvent(
            ts=datetime.now(UTC),
            actor="process_gate",
            event_type="stage_gate_evaluated",
            payload={
                "stage": stage,
                "outcome": report.outcome.value,
                "finding_count": len(findings),
                "blocking_checks": [
                    finding.check_id
                    for finding in findings
                    if finding.severity is GateSeverity.BLOCK
                ],
                "cancelled_task_ids": cancelled,
            },
        )
    )
    return report


def blocking_findings(case: Case) -> list[GateFinding]:
    """Every blocking finding recorded so far, across all stage gates."""
    return [
        finding
        for report in case.list_artifacts(GateReport)
        for finding in report.findings
        if finding.severity is GateSeverity.BLOCK
    ]
