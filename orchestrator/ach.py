"""Deterministic scoring over an ACH matrix (SPEC-040).

The agent fills the matrix; everything here is arithmetic over it.

Two ideas do the work:

**Diagnosticity.** An evidence record scored identically against every alternative cannot
discriminate between them, so it carries no weight however authoritative it is.
Diagnosticity is the dispersion of a record's scores across alternatives, normalized to
``[0, 1]``.  The set of zero-diagnosticity records is often the most useful output of the
technique: it names the evidence the case spent budget collecting that could never have
changed the answer.

**Ranking by disconfirmation.** Alternatives are ranked by weighted *inconsistent*
evidence, ascending — least disconfirmed first.  Consistency contributes nothing. This is
the part that makes ACH different from counting supporting citations, and it is the
structural antidote to confirmation bias.

Nothing here reorders a recommendation.  The matrix is projected to the Director, who must
confront it; disagreement surfaces as a gate finding.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from orchestrator.artifacts.ach import (
    CONSISTENCY_VALUE,
    INCONSISTENCY_WEIGHT,
    ACHMatrix,
)

__all__ = [
    "AlternativeStanding",
    "diagnosticity",
    "rank_by_disconfirmation",
    "weighted_inconsistency",
    "zero_diagnosticity_records",
]


@dataclass(frozen=True, slots=True)
class AlternativeStanding:
    """One alternative's position under the matrix."""

    alternative: str
    weighted_inconsistency: float
    rank: int
    #: Evidence ids scored inconsistent or strongly inconsistent against this alternative.
    disconfirming_evidence_ids: tuple[str, ...] = ()


def _scores_by_evidence(matrix: ACHMatrix) -> dict[str, dict[str, float]]:
    """``{evidence_id: {alternative: numeric consistency}}``."""
    table: dict[str, dict[str, float]] = {eid: {} for eid in matrix.evidence_ids}
    for cell in matrix.cells:
        table[cell.evidence_id][cell.alternative] = CONSISTENCY_VALUE[cell.consistency]
    return table


def diagnosticity(matrix: ACHMatrix) -> dict[str, float]:
    """Per-evidence diagnosticity in ``[0, 1]``.

    Computed as the spread (max minus min) of a record's consistency scores across
    alternatives, divided by the maximum possible spread (2.0, from strongly inconsistent
    to strongly consistent).  A record scored identically everywhere has spread 0.

    Spread is used rather than variance because it is the quantity an analyst can read off
    the matrix by eye, which keeps the number inspectable — the same reason the memory
    retrieval in SPEC-025 is deliberately keyword overlap rather than embeddings.
    """
    max_spread = CONSISTENCY_VALUE[max(CONSISTENCY_VALUE, key=lambda k: CONSISTENCY_VALUE[k])]
    max_spread -= CONSISTENCY_VALUE[min(CONSISTENCY_VALUE, key=lambda k: CONSISTENCY_VALUE[k])]

    result: dict[str, float] = {}
    for evidence_id, row in _scores_by_evidence(matrix).items():
        if not row:
            result[evidence_id] = 0.0
            continue
        spread = max(row.values()) - min(row.values())
        result[evidence_id] = spread / max_spread if max_spread else 0.0
    return result


def zero_diagnosticity_records(matrix: ACHMatrix) -> tuple[str, ...]:
    """Evidence that could not have discriminated between the alternatives.

    Reported explicitly: this is evidence the case paid to collect and which carried no
    decision value, which is worth knowing for the next case.
    """
    return tuple(sorted(eid for eid, value in diagnosticity(matrix).items() if value == 0.0))


def weighted_inconsistency(matrix: ACHMatrix) -> dict[str, float]:
    """Per-alternative weight of disconfirming evidence, diagnosticity-scaled."""
    weights = diagnosticity(matrix)
    totals: dict[str, float] = dict.fromkeys(matrix.alternatives, 0.0)
    for cell in matrix.cells:
        totals[cell.alternative] += (
            weights[cell.evidence_id] * INCONSISTENCY_WEIGHT[cell.consistency]
        )
    return totals


def rank_by_disconfirmation(matrix: ACHMatrix) -> list[AlternativeStanding]:
    """Rank alternatives ascending by weighted disconfirming evidence.

    Ties keep the order the alternatives were declared in, which is the decision spec's
    order — the only additional information available, and better than inventing a
    distinction the matrix does not support.
    """
    totals = weighted_inconsistency(matrix)
    declared_order = {alt: index for index, alt in enumerate(matrix.alternatives)}

    disconfirming: dict[str, list[str]] = {alt: [] for alt in matrix.alternatives}
    for cell in matrix.cells:
        if INCONSISTENCY_WEIGHT[cell.consistency] > 0:
            disconfirming[cell.alternative].append(cell.evidence_id)

    ordered = sorted(matrix.alternatives, key=lambda alt: (totals[alt], declared_order[alt]))
    return [
        AlternativeStanding(
            alternative=alt,
            weighted_inconsistency=totals[alt],
            rank=position,
            disconfirming_evidence_ids=tuple(sorted(disconfirming[alt])),
        )
        for position, alt in enumerate(ordered, start=1)
    ]


def select_matrix_evidence(
    authority_by_id: Mapping[str, float],
    candidate_ids: Sequence[str],
    *,
    cap: int,
) -> tuple[list[str], list[str]]:
    """Pick the highest-authority records up to ``cap``.

    Returns ``(selected, excluded)``.  Ties break on the id so selection is deterministic
    and a rerun of the same case picks the same matrix.
    """
    ranked = sorted(candidate_ids, key=lambda eid: (-authority_by_id.get(eid, 0.0), eid))
    return ranked[:cap], ranked[cap:]
