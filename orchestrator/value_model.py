"""SPEC-038 — the deterministic half of the north star's decision model.

North star Section 8 specifies ``EU(a) = Σ P(s | E) × U(a, s)`` and an explicit
division of labor: language models supply the scenarios, assumptions and value
judgments; deterministic code computes the expected values, thresholds and
sensitivities.  The ``U(a, s)`` half had no implementation, so the user's stated
objectives never reached the ranking by any mechanical path.

This module closes that.  Agents supply the weights (proposed) and the per-objective
scores; everything here is pure arithmetic over those inputs.

Nothing in this module reorders a recommendation.  A disagreement between the
computed ranking and the ranking the synthesizer stated is reported as a gate
finding, because a mismatch usually means the value model is wrong rather than
that the judgment is.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from orchestrator.artifacts import AlternativeAssessment

#: Fraction by which each weight is perturbed, in isolation, to test robustness.
WEIGHT_PERTURBATION = 0.25

__all__ = [
    "WEIGHT_PERTURBATION",
    "RankDivergence",
    "RankedAlternative",
    "WeightSensitivity",
    "compute_ranking",
    "normalize_weights",
    "rank_divergence",
    "weight_sensitivity",
    "weighted_score",
]


@dataclass(frozen=True, slots=True)
class RankedAlternative:
    """One alternative's computed position under the elicited value model."""

    alternative: str
    score: float
    computed_rank: int
    stated_rank: int
    #: Objectives the agent left unscored for this alternative.  A scored-but-incomplete
    #: alternative still ranks; a wholly unscored one is excluded (see ``compute_ranking``).
    missing_objectives: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RankDivergence:
    """Where the computed order and the stated order disagree."""

    agrees: bool
    #: ``(alternative, computed_rank, stated_rank)`` for each disagreeing position.
    positions: tuple[tuple[str, int, int], ...] = ()
    #: Alternatives excluded from the computation because they carried no scores.
    unscored: tuple[str, ...] = ()

    @property
    def top_choice_differs(self) -> bool:
        return any(computed == 1 or stated == 1 for _, computed, stated in self.positions)


@dataclass(frozen=True, slots=True)
class WeightSensitivity:
    """How robust the top-ranked alternative is to the weights themselves.

    The analyst varies model parameters; nothing varied the decision owner's own
    weights, which is usually what actually flips a personal decision.
    """

    top_alternative: str
    runs_total: int
    runs_preserving_top: int
    #: Smallest single-weight change (as a signed fraction) that flips the top choice,
    #: or ``None`` when no tested perturbation flips it.
    smallest_flip: tuple[str, float] | None = None
    flipped_by: tuple[str, ...] = field(default_factory=tuple)

    @property
    def share_preserving_top(self) -> float:
        if self.runs_total == 0:
            return 1.0
        return self.runs_preserving_top / self.runs_total


def normalize_weights(weights: Mapping[str, float]) -> dict[str, float]:
    """Scale positive weights to sum to 1.0.

    Raises on an empty mapping or a non-positive total, both of which mean the
    caller has an elicitation bug rather than a degenerate but valid decision.
    """
    if not weights:
        raise ValueError("Cannot normalize an empty weight mapping.")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError(f"Weights must sum to a positive number; got {total}.")
    return {name: value / total for name, value in weights.items()}


def weighted_score(
    weights: Mapping[str, float],
    scores: Mapping[str, float],
) -> tuple[float, tuple[str, ...]]:
    """Return ``(Σ weight × score, objectives that were not scored)``.

    Unscored objectives contribute nothing rather than zero-by-default: the score is
    renormalized over the objectives actually scored, so a partially scored
    alternative is not silently penalized for the gap.  The gap is returned so the
    caller can surface it.
    """
    normalized = normalize_weights(weights)
    missing = tuple(sorted(name for name in normalized if name not in scores))
    covered = {name: w for name, w in normalized.items() if name in scores}
    if not covered:
        return 0.0, missing
    covered_total = sum(covered.values())
    return (
        sum(w * scores[name] for name, w in covered.items()) / covered_total,
        missing,
    )


def compute_ranking(
    weights: Mapping[str, float],
    assessments: Sequence[AlternativeAssessment],
) -> list[RankedAlternative]:
    """Rank alternatives by weighted score, descending.

    Alternatives carrying no ``objective_scores`` at all are excluded rather than
    scored as zero, so a missing score is visible as an omission instead of being
    read as "this option is worthless" (resolves the spec's open question).

    Ties keep the agent's stated order, which is the only additional information
    available and avoids inventing a distinction the model did not make.
    """
    scored = [a for a in assessments if a.objective_scores]
    if not scored:
        return []

    rows: list[tuple[float, int, str, tuple[str, ...]]] = []
    for assessment in scored:
        score, missing = weighted_score(weights, assessment.objective_scores or {})
        rows.append((score, assessment.rank, assessment.alternative, missing))

    rows.sort(key=lambda row: (-row[0], row[1]))
    return [
        RankedAlternative(
            alternative=alternative,
            score=score,
            computed_rank=position,
            stated_rank=stated,
            missing_objectives=missing,
        )
        for position, (score, stated, alternative, missing) in enumerate(rows, start=1)
    ]


def rank_divergence(
    weights: Mapping[str, float],
    assessments: Sequence[AlternativeAssessment],
) -> RankDivergence:
    """Compare the computed ranking against the ranking the agent stated.

    The stated ranks are compared by *order*, not by literal value, so a plan that
    ranks 2/4/6 rather than 1/2/3 is not reported as a disagreement.
    """
    ranked = compute_ranking(weights, assessments)
    unscored = tuple(sorted(a.alternative for a in assessments if not a.objective_scores))
    if not ranked:
        return RankDivergence(agrees=True, positions=(), unscored=unscored)

    stated_order = sorted(ranked, key=lambda row: row.stated_rank)
    stated_position = {row.alternative: i for i, row in enumerate(stated_order, start=1)}

    positions = tuple(
        (row.alternative, row.computed_rank, stated_position[row.alternative])
        for row in ranked
        if row.computed_rank != stated_position[row.alternative]
    )
    return RankDivergence(agrees=not positions, positions=positions, unscored=unscored)


def weight_sensitivity(
    weights: Mapping[str, float],
    assessments: Sequence[AlternativeAssessment],
    *,
    perturbation: float = WEIGHT_PERTURBATION,
) -> WeightSensitivity | None:
    """Perturb each weight in isolation by ±``perturbation`` and re-rank.

    Returns ``None`` when there is nothing to test — no scored alternatives, or a
    single objective, where scaling the only weight cannot change the order.
    """
    if not 0 < perturbation < 1:
        raise ValueError(f"perturbation must lie in (0, 1); got {perturbation}.")

    baseline = compute_ranking(weights, assessments)
    if not baseline or len(weights) < 2:
        return None
    top = baseline[0].alternative

    runs = 0
    preserved = 0
    flipped_by: list[str] = []
    smallest: tuple[str, float] | None = None

    for name in sorted(weights):
        for direction in (perturbation, -perturbation):
            candidate = dict(weights)
            candidate[name] = weights[name] * (1.0 + direction)
            if candidate[name] <= 0:
                continue
            runs += 1
            ranked = compute_ranking(candidate, assessments)
            if ranked and ranked[0].alternative == top:
                preserved += 1
                continue
            flipped_by.append(name)
            if smallest is None or abs(direction) < abs(smallest[1]):
                smallest = (name, direction)

    return WeightSensitivity(
        top_alternative=top,
        runs_total=runs,
        runs_preserving_top=preserved,
        smallest_flip=smallest,
        flipped_by=tuple(sorted(set(flipped_by))),
    )
