from __future__ import annotations

import re

from pydantic import BaseModel

from orchestrator.artifacts import AssumptionRecord, EvidenceRecord, PreliminaryRecommendation
from orchestrator.case_store import Case
from orchestrator.invoke_role import register_cross_field_validation_hook

_REF_ID_RE = re.compile(r"\b(?:E|A)-\d+\b")


def _extract_reference_ids(text: str) -> list[str]:
    return _REF_ID_RE.findall(text)


def _existing_ids(case: Case) -> tuple[set[str], set[str]]:
    evidence_ids = {record.evidence_id for record in case.list_artifacts(EvidenceRecord)}
    assumption_ids = {record.assumption_id for record in case.list_artifacts(AssumptionRecord)}
    return evidence_ids, assumption_ids


def _filter_dangling_ids(
    ids: list[str],
    evidence_ids: set[str],
    assumption_ids: set[str],
) -> list[str]:
    """Return only IDs that exist in the case blackboard."""
    valid: list[str] = []
    for ref_id in ids:
        if ref_id.startswith("E-") and ref_id in evidence_ids:
            valid.append(ref_id)
        elif ref_id.startswith("A-") and ref_id in assumption_ids:
            valid.append(ref_id)
    return valid


def validate_preliminary_recommendation_citations(artifact: BaseModel, case: Case) -> None:
    if not isinstance(artifact, PreliminaryRecommendation):
        return

    evidence_ids, assumption_ids = _existing_ids(case)

    # Provisional thesis (Stage 3) runs before any evidence or assumptions exist.
    # Citation requirements only apply once the blackboard has evidence/assumptions.
    has_blackboard = bool(evidence_ids or assumption_ids)
    if not has_blackboard:
        return

    for index, reason in enumerate(artifact.rationale, start=1):
        reason_ids = _extract_reference_ids(reason)
        if not reason_ids:
            raise ValueError(
                "key reason missing citation: "
                f"reason[{index}] '{reason}' must include at least one E-* or A-* ID."
            )
        valid_ids = _filter_dangling_ids(reason_ids, evidence_ids, assumption_ids)
        if not valid_ids:
            raise ValueError(
                f"key reason reason[{index}] has no valid citations: "
                f"all referenced IDs are dangling. IDs found: {reason_ids}"
            )

    for outcome_name, estimate in artifact.outcome_probabilities.items():
        outcome_ids = _extract_reference_ids(outcome_name)
        adjustment_ids = [ref_id for adj in estimate.adjustments for ref_id in adj.evidence_ids]
        combined_ids = outcome_ids + adjustment_ids
        if not combined_ids:
            raise ValueError(
                "estimated outcome missing citation: "
                f"outcome '{outcome_name}' must include at least one E-* or A-* ID in the "
                "outcome name or probability adjustments."
            )
        valid_ids = _filter_dangling_ids(combined_ids, evidence_ids, assumption_ids)
        if not valid_ids:
            raise ValueError(
                f"estimated outcome '{outcome_name}' has no valid citations: "
                f"all referenced IDs are dangling. IDs found: {combined_ids}"
            )

    # key_assumptions: filter dangling IDs silently (don't fail on dangling references)
    # The model may reference assumptions that were not created in the case.

    rec_conf = artifact.recommendation_confidence
    ev_conf = artifact.evidence_confidence
    # Heuristic (not proof): identical value and identical basis string is a strong
    # signal that confidence dimensions were collapsed instead of assessed independently.
    if rec_conf.value == ev_conf.value and rec_conf.basis.strip() == ev_conf.basis.strip():
        raise ValueError(
            "confidence collapse detected: recommendation_confidence and evidence_confidence "
            "must be independently assessed (identical value and basis are not allowed)."
        )


def register_citation_hooks() -> None:
    register_cross_field_validation_hook(
        "preliminary_recommendation",
        validate_preliminary_recommendation_citations,
    )
