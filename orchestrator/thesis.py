"""Append-only thesis ledger.

The thesis used to be written once and silently overwritten. Recording every
revision makes belief movement inspectable: an auditor can see whether evidence
actually moved the conclusion or whether the system anchored on its first guess.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from orchestrator.artifacts import (
    AuditEvent,
    PreliminaryRecommendation,
    ThesisRevision,
    ThesisTrigger,
)
from orchestrator.case_store import Case

_EVIDENCE_RE = re.compile(r"\bE-\d+\b")
_ASSUMPTION_RE = re.compile(r"\bA-\d+\b")
_RATIONALE_DIGEST_CHARS = 220


def _truncate_at_word_boundary(text: str, max_chars: int) -> str:
    """Truncate text to at most max_chars, breaking at a word boundary with ellipsis."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    # Walk back to the last whitespace
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.5:  # only break at word if we keep >50% of the budget
        truncated = truncated[:last_space]
    return truncated.rstrip() + "…"


def load_ledger(case: Case) -> list[ThesisRevision]:
    return sorted(case.list_artifacts(ThesisRevision), key=lambda entry: entry.revision)


def current_head(case: Case) -> ThesisRevision | None:
    ledger = load_ledger(case)
    return ledger[-1] if ledger else None


def record_thesis_revision(
    case: Case,
    recommendation: PreliminaryRecommendation,
    *,
    trigger: ThesisTrigger,
    objection_ids: list[str] | None = None,
) -> ThesisRevision:
    """Append the current thesis to the ledger and return the new entry."""
    ledger = load_ledger(case)
    previous = ledger[-1] if ledger else None
    previous_alternative = previous.preferred_alternative if previous else None

    joined_rationale = " ".join(recommendation.rationale)
    revision = ThesisRevision(
        revision=len(ledger) + 1,
        trigger=trigger,
        preferred_alternative=recommendation.preferred_alternative,
        previous_alternative=previous_alternative,
        changed=(
            previous_alternative is not None
            and previous_alternative != recommendation.preferred_alternative
        ),
        rationale_digest=[
            _truncate_at_word_boundary(reason, _RATIONALE_DIGEST_CHARS)
            for reason in recommendation.rationale[:3]
        ],
        changed_because_evidence_ids=sorted(set(_EVIDENCE_RE.findall(joined_rationale))),
        changed_because_assumption_ids=sorted(set(_ASSUMPTION_RE.findall(joined_rationale))),
        changed_because_objection_ids=sorted(set(objection_ids or [])),
        recommendation_confidence=recommendation.recommendation_confidence.value,
        evidence_confidence=recommendation.evidence_confidence.value,
        recorded_at=datetime.now(UTC),
    )
    case.write_artifact(revision)
    case.audit(
        AuditEvent(
            ts=datetime.now(UTC),
            actor="thesis_ledger",
            event_type="thesis_revision_recorded",
            payload={
                "revision": revision.revision,
                "trigger": trigger.value,
                "preferred_alternative": revision.preferred_alternative,
                "previous_alternative": previous_alternative,
                "changed": revision.changed,
            },
        )
    )
    return revision


def write_thesis(
    case: Case,
    recommendation: PreliminaryRecommendation,
    *,
    trigger: ThesisTrigger,
    objection_ids: list[str] | None = None,
) -> ThesisRevision:
    """Persist the thesis as the current head and append it to the ledger."""
    case.write_artifact(recommendation)
    return record_thesis_revision(
        case, recommendation, trigger=trigger, objection_ids=objection_ids
    )


def drift_summary(case: Case) -> dict[str, object]:
    ledger = load_ledger(case)
    if not ledger:
        return {"revisions": 0, "changed_count": 0, "path": []}
    return {
        "revisions": len(ledger),
        "changed_count": sum(1 for entry in ledger if entry.changed),
        "path": [
            {
                "revision": entry.revision,
                "trigger": entry.trigger.value,
                "preferred_alternative": entry.preferred_alternative,
                "changed": entry.changed,
                "recommendation_confidence": entry.recommendation_confidence,
            }
            for entry in ledger
        ],
    }
