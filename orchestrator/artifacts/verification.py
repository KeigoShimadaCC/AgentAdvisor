from __future__ import annotations

from pydantic import Field

from orchestrator.artifacts.common import ArtifactModel, NonEmptyStr
from orchestrator.artifacts.gates import GateFinding


class CitationCheckItem(ArtifactModel):
    """One claim paired with the excerpts of the evidence it cites.

    The reviewer must return a verdict per item, so "the citations look fine" is not
    an available answer.
    """

    item_id: NonEmptyStr
    claim: NonEmptyStr
    cited_ids: list[NonEmptyStr] = Field(default_factory=list)
    dangling_ids: list[NonEmptyStr] = Field(default_factory=list)
    evidence_excerpts: list[NonEmptyStr] = Field(default_factory=list)


class VerificationWorksheet(ArtifactModel):
    items: list[CitationCheckItem] = Field(default_factory=list)
    deterministic_findings: list[GateFinding] = Field(default_factory=list)
    instructions: NonEmptyStr


class CitationVerdict(ArtifactModel):
    item_id: NonEmptyStr
    supported: bool
    justification: NonEmptyStr
