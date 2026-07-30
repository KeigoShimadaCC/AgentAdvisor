from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TypeGuard

from orchestrator.artifacts import AuditEvent, TaskProposal, TaskProposalBatch, TaskRole
from orchestrator.case_store import Case

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_WHITESPACE_RE = re.compile(r"\s+")
_KNOWN_TASK_ROLES = frozenset(role.value for role in TaskRole)
_PRIORITY_FIELDS = ("materiality", "probability_of_changing_conclusion", "estimated_cost")


@dataclass(frozen=True, slots=True)
class ProposalRejection:
    proposal_index: int
    reason: str
    question: str | None
    normalized_question: str | None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PlanningAcceptanceResult:
    accepted_batch: TaskProposalBatch
    rejections: tuple[ProposalRejection, ...]


def normalize_question_for_dedupe(question: str) -> str:
    """Normalize a proposal question for near-duplicate matching.

    Normalization steps:
    1) Unicode NFKC normalization
    2) lowercase
    3) replace non-alphanumeric runs with spaces
    4) collapse repeated whitespace and trim
    """
    normalized = unicodedata.normalize("NFKC", question).lower()
    normalized = _NON_ALNUM_RE.sub(" ", normalized)
    return _WHITESPACE_RE.sub(" ", normalized).strip()


def _is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _missing_priority_fields(task_payload: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    materiality = task_payload.get("materiality")
    if not isinstance(materiality, str) or not materiality:
        missing.append("materiality")

    probability_raw = task_payload.get("probability_of_changing_conclusion")
    if not _is_number(probability_raw):
        missing.append("probability_of_changing_conclusion")
    else:
        probability = float(probability_raw)
        if probability < 0.0 or probability > 1.0:
            missing.append("probability_of_changing_conclusion")

    estimated_cost_raw = task_payload.get("estimated_cost")
    if not _is_number(estimated_cost_raw):
        missing.append("estimated_cost")
    else:
        estimated_cost = float(estimated_cost_raw)
        if estimated_cost <= 0.0:
            missing.append("estimated_cost")
    return missing


def filter_task_proposals(batch: TaskProposalBatch) -> PlanningAcceptanceResult:
    accepted: list[TaskProposal] = []
    rejections: list[ProposalRejection] = []
    seen_by_normalized_question: dict[str, int] = {}

    for proposal_index, proposal in enumerate(batch.proposals):
        payload = proposal.model_dump(mode="json")
        task_payload_raw = payload.get("task")
        task_payload = task_payload_raw if isinstance(task_payload_raw, dict) else {}
        question_raw = task_payload.get("question")
        question = question_raw if isinstance(question_raw, str) else None
        normalized_question = (
            normalize_question_for_dedupe(question) if question is not None else None
        )

        missing_fields = _missing_priority_fields(task_payload)
        if missing_fields:
            rejections.append(
                ProposalRejection(
                    proposal_index=proposal_index,
                    reason="missing_priority_fields",
                    question=question,
                    normalized_question=normalized_question,
                    details={"missing_fields": missing_fields},
                )
            )
            continue

        role_raw = task_payload.get("role")
        if not isinstance(role_raw, str) or role_raw not in _KNOWN_TASK_ROLES:
            rejections.append(
                ProposalRejection(
                    proposal_index=proposal_index,
                    reason="unknown_role",
                    question=question,
                    normalized_question=normalized_question,
                    details={"role": role_raw, "known_roles": sorted(_KNOWN_TASK_ROLES)},
                )
            )
            continue

        if not normalized_question:
            rejections.append(
                ProposalRejection(
                    proposal_index=proposal_index,
                    reason="missing_question",
                    question=question,
                    normalized_question=normalized_question,
                    details={},
                )
            )
            continue

        duplicate_of_index = seen_by_normalized_question.get(normalized_question)
        if duplicate_of_index is not None:
            rejections.append(
                ProposalRejection(
                    proposal_index=proposal_index,
                    reason="near_duplicate_question",
                    question=question,
                    normalized_question=normalized_question,
                    details={"duplicate_of_index": duplicate_of_index},
                )
            )
            continue

        seen_by_normalized_question[normalized_question] = proposal_index
        accepted.append(proposal)

    accepted_batch = batch.model_copy(update={"proposals": accepted})
    return PlanningAcceptanceResult(accepted_batch=accepted_batch, rejections=tuple(rejections))


def apply_planner_acceptance_filter(
    case: Case,
    batch: TaskProposalBatch,
    *,
    actor: str = "planning_filter",
    event_type: str = "planner_proposal_rejected",
) -> PlanningAcceptanceResult:
    result = filter_task_proposals(batch)
    for rejection in result.rejections:
        case.audit(
            AuditEvent(
                ts=datetime.now(UTC),
                actor=actor,
                event_type=event_type,
                payload={
                    "mode": batch.mode.value,
                    "proposal_index": rejection.proposal_index,
                    "reason": rejection.reason,
                    "question": rejection.question,
                    "normalized_question": rejection.normalized_question,
                    **rejection.details,
                },
            )
        )
    return result
