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
_ELLIPSIS = "…"


def _digest(reason: str) -> str:
    """Shorten a rationale to the digest length, cutting between words.

    A mid-word cut reads as corrupted text and can truncate a citation id into
    something that looks like a different id, so the cut falls back to the last
    word boundary and says it was shortened.
    """
    if len(reason) <= _RATIONALE_DIGEST_CHARS:
        return reason
    window = reason[: _RATIONALE_DIGEST_CHARS - len(_ELLIPSIS)]
    boundary = window.rfind(" ")
    head = window[:boundary] if boundary > 0 else window
    return f"{head.rstrip()}{_ELLIPSIS}"


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
        rationale_digest=[_digest(reason) for reason in recommendation.rationale[:3]],
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
