"""Analysis of Competing Hypotheses (SPEC-040).

Heuer's technique, catalogued in Heuer & Pherson, *Structured Analytic Techniques for
Intelligence Analysis*, and required as "analysis of alternatives" by ICD 203's analytic
tradecraft standards.

The core insight the rest of this pipeline does not implement: evidence consistent with
every hypothesis carries no information, and the best hypothesis is the one with the least
evidence *against* it rather than the most evidence for it.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from orchestrator.artifacts.common import ArtifactModel, EvidenceId, NonEmptyStr

#: Ceiling on matrix size. Filling an N×M consistency matrix is a harder structured-output
#: task than anything else asked of any role, and this repo's history shows structured-output
#: failures are where invocations die. Excluded records are listed with a reason rather than
#: silently dropped.
MAX_ACH_EVIDENCE = 20


class ACHConsistency(StrEnum):
    """How an evidence record bears on a hypothesis."""

    STRONGLY_INCONSISTENT = "strongly_inconsistent"
    INCONSISTENT = "inconsistent"
    NEUTRAL = "neutral"
    CONSISTENT = "consistent"
    STRONGLY_CONSISTENT = "strongly_consistent"


#: Numeric value used for diagnosticity dispersion, on a symmetric scale around neutral.
CONSISTENCY_VALUE: dict[ACHConsistency, float] = {
    ACHConsistency.STRONGLY_INCONSISTENT: -1.0,
    ACHConsistency.INCONSISTENT: -0.5,
    ACHConsistency.NEUTRAL: 0.0,
    ACHConsistency.CONSISTENT: 0.5,
    ACHConsistency.STRONGLY_CONSISTENT: 1.0,
}

#: How much each cell counts *against* a hypothesis. Only inconsistency scores; consistency
#: contributes nothing, which is the whole point of the technique.
INCONSISTENCY_WEIGHT: dict[ACHConsistency, float] = {
    ACHConsistency.STRONGLY_INCONSISTENT: 1.0,
    ACHConsistency.INCONSISTENT: 0.5,
    ACHConsistency.NEUTRAL: 0.0,
    ACHConsistency.CONSISTENT: 0.0,
    ACHConsistency.STRONGLY_CONSISTENT: 0.0,
}


class ACHCell(ArtifactModel):
    """One evidence record scored against one alternative."""

    evidence_id: EvidenceId
    alternative: NonEmptyStr
    consistency: ACHConsistency
    note: NonEmptyStr


class ACHExclusion(ArtifactModel):
    """An evidence record left out of the matrix, and why."""

    evidence_id: EvidenceId
    reason: NonEmptyStr


class ACHMatrix(ArtifactModel):
    """A complete hypothesis × evidence consistency matrix.

    Completeness is enforced: a partially filled matrix would let the ranking be driven
    by which cells the model bothered to fill.
    """

    decision_question: NonEmptyStr
    alternatives: list[NonEmptyStr] = Field(min_length=2)
    evidence_ids: list[EvidenceId] = Field(min_length=1)
    cells: list[ACHCell] = Field(min_length=1)
    excluded_evidence_ids: list[ACHExclusion] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_matrix_is_complete(self) -> ACHMatrix:
        if len(set(self.alternatives)) != len(self.alternatives):
            raise ValueError("alternatives contains duplicates.")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence_ids contains duplicates.")
        if len(self.evidence_ids) > MAX_ACH_EVIDENCE:
            raise ValueError(
                f"evidence_ids exceeds the {MAX_ACH_EVIDENCE}-record cap; "
                "list the rest under excluded_evidence_ids with a reason."
            )

        expected = {(eid, alt) for eid in self.evidence_ids for alt in self.alternatives}
        seen: set[tuple[str, str]] = set()
        for cell in self.cells:
            key = (cell.evidence_id, cell.alternative)
            if key in seen:
                raise ValueError(
                    f"duplicate cell for evidence {cell.evidence_id} / "
                    f"alternative {cell.alternative!r}."
                )
            if key not in expected:
                raise ValueError(
                    f"cell references evidence {cell.evidence_id} / "
                    f"alternative {cell.alternative!r} not declared in the matrix."
                )
            seen.add(key)

        missing = expected - seen
        if missing:
            sample = sorted(f"{eid}/{alt}" for eid, alt in missing)[:5]
            raise ValueError(
                f"matrix is incomplete: {len(missing)} cell(s) missing, e.g. {sample}. "
                "Every evidence record must be scored against every alternative."
            )

        overlap = {exclusion.evidence_id for exclusion in self.excluded_evidence_ids} & set(
            self.evidence_ids
        )
        if overlap:
            raise ValueError(
                f"evidence appears both in the matrix and in exclusions: {sorted(overlap)}"
            )
        return self
