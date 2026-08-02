"""Reviewer verification: deterministic pre-checks plus a per-claim citation worksheet.

The reviewer previously received the final recommendation and was asked whether it
looked right, which it always did. It now receives a worksheet that pairs each
sampled claim with the actual excerpts of the evidence that claim cites, and must
return a verdict per item.
"""

from __future__ import annotations

import re
from decimal import Decimal

from orchestrator.artifacts import (
    AssumptionRecord,
    CitationCheckItem,
    EvidenceRecord,
    FinalRecommendation,
    GateFinding,
    GateSeverity,
    Level,
    ObjectionRecord,
    ReviewOutcome,
    ReviewReport,
    VerificationWorksheet,
)
from orchestrator.case_store import Case

_REF_ID_RE = re.compile(r"\b(?:E|A)-\d+\b")

MAX_WORKSHEET_ITEMS = 8
MAX_PROBABILITY_DECIMALS = 2
CONFIDENCE_INVERSION_MARGIN = 0.25
EXCERPT_CHAR_LIMIT = 400

WORKSHEET_INSTRUCTIONS = (
    "For every item below, decide whether the quoted evidence excerpts actually support the "
    "claim as written. Judge support, not plausibility: an excerpt that is merely about the "
    "same topic does not support a specific numeric or causal claim. Return one verdict per "
    "item_id in citation_verdicts. Any item you mark unsupported must also appear as an "
    "unsupported_citation defect, and the report outcome must then be 'fail'."
)


def _decimals(value: float) -> int:
    return max(0, -Decimal(str(value)).as_tuple().exponent)  # type: ignore[operator]


def _check_false_precision(recommendation: FinalRecommendation) -> list[GateFinding]:
    offenders = [
        name
        for name, estimate in recommendation.outcome_probabilities.items()
        for candidate in (estimate.point, estimate.interval_low, estimate.interval_high)
        if candidate is not None and _decimals(candidate) > MAX_PROBABILITY_DECIMALS
    ]
    if not offenders:
        return []
    return [
        GateFinding(
            check_id="verification.false_precision",
            severity=GateSeverity.WARN,
            message=(
                "Outcome probabilities are stated to more than "
                f"{MAX_PROBABILITY_DECIMALS} decimal places, implying precision the method "
                "cannot deliver."
            ),
            target_ids=sorted(set(offenders)),
        )
    ]


def _check_confidence_inversion(recommendation: FinalRecommendation) -> list[GateFinding]:
    gap = recommendation.recommendation_confidence.value - recommendation.evidence_confidence.value
    if gap <= CONFIDENCE_INVERSION_MARGIN:
        return []
    return [
        GateFinding(
            check_id="verification.confidence_inversion",
            severity=GateSeverity.BLOCK,
            message=(
                f"Recommendation confidence ({recommendation.recommendation_confidence.value:.2f}) "
                f"exceeds evidence confidence ({recommendation.evidence_confidence.value:.2f}) "
                f"by more than {CONFIDENCE_INVERSION_MARGIN:.2f}."
            ),
            target_ids=["final_recommendation"],
        )
    ]


def _check_stability_consistency(recommendation: FinalRecommendation) -> list[GateFinding]:
    stability = recommendation.model_stability
    if stability.runs_total <= 1:
        return [
            GateFinding(
                check_id="verification.stability_untested",
                severity=GateSeverity.WARN,
                message=(
                    "Model stability rests on a single run, so it carries no information "
                    "about robustness."
                ),
                target_ids=["final_recommendation.model_stability"],
            )
        ]
    return []


def _check_undisclosed_objections(
    case: Case, recommendation: FinalRecommendation
) -> list[GateFinding]:
    open_material = [
        record
        for record in case.list_artifacts(ObjectionRecord)
        if record.materiality is Level.HIGH and record.resolution_status.value == "open"
    ]
    if not open_material:
        return []
    disclosed = " ".join(
        [
            recommendation.decision_confidence_summary,
            *(item.claim for item in recommendation.strongest_counterarguments),
            *recommendation.recommendation_change_triggers,
        ]
    ).lower()
    undisclosed = [
        record.objection_id
        for record in open_material
        if not _is_disclosed(record.claim, disclosed)
    ]
    if not undisclosed:
        return []
    return [
        GateFinding(
            check_id="verification.undisclosed_open_objection",
            severity=GateSeverity.BLOCK,
            message=(
                f"{len(undisclosed)} open high-materiality objection(s) are not reflected in the "
                "final recommendation's counterarguments or change triggers."
            ),
            target_ids=undisclosed,
        )
    ]


_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "that",
        "with",
        "this",
        "from",
        "have",
        "will",
        "may",
        "could",
        "would",
        "into",
        "than",
        "then",
        "over",
        "under",
        "about",
        "which",
        "their",
        "there",
        "been",
        "were",
        "when",
        "what",
    }
)


def _significant_tokens(text: str, *, limit: int = 6) -> list[str]:
    tokens = [token for token in re.findall(r"[a-z]{4,}", text.lower()) if token not in _STOPWORDS]
    return tokens[:limit]


DISCLOSURE_TOKEN_SHARE = 0.5


def _is_disclosed(claim: str, disclosed_text: str) -> bool:
    """A single shared word is not disclosure; require most of the claim to appear.

    Matching on ``any`` token lets an unrelated sentence that happens to reuse one word
    silently satisfy the check, which is the failure this gate exists to catch.
    """
    tokens = _significant_tokens(claim)
    if not tokens:
        return True
    hits = sum(1 for token in tokens if token in disclosed_text)
    return hits / len(tokens) >= DISCLOSURE_TOKEN_SHARE


def build_verification_worksheet(case: Case) -> VerificationWorksheet:
    recommendation = case.read_artifact(FinalRecommendation)
    evidence_by_id = {record.evidence_id: record for record in case.list_artifacts(EvidenceRecord)}
    assumption_by_id = {
        record.assumption_id: record for record in case.list_artifacts(AssumptionRecord)
    }

    findings: list[GateFinding] = []
    findings.extend(_check_false_precision(recommendation))
    findings.extend(_check_confidence_inversion(recommendation))
    findings.extend(_check_stability_consistency(recommendation))
    findings.extend(_check_undisclosed_objections(case, recommendation))

    claims: list[str] = [
        *recommendation.key_reasons,
        *recommendation.quantitative_findings,
    ]

    items: list[CitationCheckItem] = []
    dangling_all: list[str] = []
    for index, claim in enumerate(claims[:MAX_WORKSHEET_ITEMS], start=1):
        referenced = _REF_ID_RE.findall(claim)
        excerpts: list[str] = []
        dangling: list[str] = []
        for ref_id in referenced:
            if ref_id in evidence_by_id:
                record = evidence_by_id[ref_id]
                excerpts.append(
                    f"{ref_id} [{record.publisher}, {record.publication_date.isoformat()}]: "
                    f"{record.excerpt[:EXCERPT_CHAR_LIMIT]}"
                )
            elif ref_id in assumption_by_id:
                excerpts.append(f"{ref_id} [assumption]: {assumption_by_id[ref_id].claim}")
            else:
                dangling.append(ref_id)
        dangling_all.extend(dangling)
        items.append(
            CitationCheckItem(
                item_id=f"VC-{index}",
                claim=claim,
                cited_ids=referenced,
                dangling_ids=dangling,
                evidence_excerpts=excerpts,
            )
        )

    uncited = [item.item_id for item in items if not item.cited_ids]
    if uncited:
        findings.append(
            GateFinding(
                check_id="verification.uncited_claim",
                severity=GateSeverity.BLOCK,
                message=f"{len(uncited)} sampled claim(s) carry no citation at all.",
                target_ids=uncited,
            )
        )
    if dangling_all:
        findings.append(
            GateFinding(
                check_id="verification.dangling_citation",
                severity=GateSeverity.WARN,
                message=f"{len(set(dangling_all))} cited ID(s) do not resolve on the blackboard.",
                target_ids=sorted(set(dangling_all)),
            )
        )

    worksheet = VerificationWorksheet(
        items=items,
        deterministic_findings=findings,
        instructions=WORKSHEET_INSTRUCTIONS,
    )
    case.write_artifact(worksheet)
    return worksheet


def review_is_acceptable(report: ReviewReport, worksheet: VerificationWorksheet) -> bool:
    """A review passes only if it engaged with the worksheet and found nothing fatal."""
    if report.outcome is ReviewOutcome.FAIL:
        return False
    if any(finding.severity is GateSeverity.BLOCK for finding in worksheet.deterministic_findings):
        return False
    checked = {verdict.item_id for verdict in report.citation_verdicts}
    required = {item.item_id for item in worksheet.items}
    if required and not required.issubset(checked):
        return False
    return all(verdict.supported for verdict in report.citation_verdicts)
