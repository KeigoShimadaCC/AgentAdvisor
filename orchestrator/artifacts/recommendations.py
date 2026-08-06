from __future__ import annotations

from datetime import date

from pydantic import Field, model_validator

from orchestrator.artifacts.common import (
    ActionId,
    ArtifactModel,
    AssumptionId,
    EvidenceId,
    NonEmptyStr,
)
from orchestrator.artifacts.confidence import ConfidenceAssessment
from orchestrator.artifacts.probability import ProbabilityEstimate
from orchestrator.artifacts.stability import ModelStability


class AlternativeAssessment(ArtifactModel):
    alternative: NonEmptyStr
    rank: int = Field(ge=1)
    rationale: NonEmptyStr
    #: SPEC-038. How well this alternative serves each objective, on a 0..1 scale.
    #: Optional, so a case without an elicited value model is unchanged.
    objective_scores: dict[NonEmptyStr, float] | None = None

    @model_validator(mode="after")
    def validate_objective_scores(self) -> AlternativeAssessment:
        if self.objective_scores is None:
            return self
        if not self.objective_scores:
            raise ValueError(
                "objective_scores must be omitted entirely rather than set to an empty mapping."
            )
        out_of_range = sorted(
            name for name, score in self.objective_scores.items() if not 0.0 <= score <= 1.0
        )
        if out_of_range:
            raise ValueError(f"objective_scores must lie in [0, 1]; out of range: {out_of_range}")
        return self


class ScenarioAssessment(ArtifactModel):
    scenario_name: NonEmptyStr
    summary: NonEmptyStr
    probability: ProbabilityEstimate


class Counterargument(ArtifactModel):
    claim: NonEmptyStr
    resolution: NonEmptyStr
    resolved: bool


class NextAction(ArtifactModel):
    """One executable step, not a sentence about a step.

    ``first_step`` is what makes the record useful: an action the reader cannot
    start today is not an action.
    """

    action_id: ActionId
    action: NonEmptyStr
    owner: NonEmptyStr
    by_date: date
    first_step: NonEmptyStr
    why_now: NonEmptyStr
    estimated_cost: NonEmptyStr | None = None
    depends_on: list[ActionId] = Field(default_factory=list)


class PreliminaryRecommendation(ArtifactModel):
    preferred_alternative: NonEmptyStr
    rationale: list[NonEmptyStr] = Field(min_length=1)
    key_assumptions: list[AssumptionId] = Field(default_factory=list)
    outcome_probabilities: dict[NonEmptyStr, ProbabilityEstimate] = Field(min_length=1)
    evidence_confidence: ConfidenceAssessment
    recommendation_confidence: ConfidenceAssessment
    model_stability: ModelStability
    unresolved_evidence_gaps: list[NonEmptyStr] = Field(default_factory=list)
    major_risks: list[NonEmptyStr] = Field(default_factory=list)


class FinalRecommendation(ArtifactModel):
    recommended_action: NonEmptyStr
    timing: NonEmptyStr
    decision_confidence_summary: NonEmptyStr
    alternatives_considered: list[AlternativeAssessment] = Field(min_length=1)
    key_reasons: list[NonEmptyStr] = Field(min_length=1)
    scenario_analysis: list[ScenarioAssessment] = Field(min_length=1)
    quantitative_findings: list[NonEmptyStr] = Field(default_factory=list)
    strongest_counterarguments: list[Counterargument] = Field(default_factory=list)
    critical_assumptions: list[AssumptionId] = Field(default_factory=list)
    recommendation_change_triggers: list[NonEmptyStr] = Field(default_factory=list)
    #: SPEC-039. What could not be assessed: thin or single-sourced evidence, questions
    #: the investigation never reached, and what a deeper engagement would have done.
    #: Defaulted rather than required so existing cases keep validating; the process
    #: gate flags an empty list.
    limitations: list[NonEmptyStr] = Field(default_factory=list)
    next_actions: list[NextAction] = Field(min_length=1)
    citations: list[EvidenceId] = Field(default_factory=list)
    outcome_probabilities: dict[NonEmptyStr, ProbabilityEstimate] = Field(min_length=1)
    evidence_confidence: ConfidenceAssessment
    recommendation_confidence: ConfidenceAssessment
    model_stability: ModelStability

    @model_validator(mode="after")
    def validate_action_plan(self) -> FinalRecommendation:
        action_ids = [action.action_id for action in self.next_actions]
        duplicates = sorted({aid for aid in action_ids if action_ids.count(aid) > 1})
        if duplicates:
            raise ValueError(f"next_actions contains duplicate action_ids: {duplicates}")

        known = set(action_ids)
        edges: dict[str, list[str]] = {}
        for action in self.next_actions:
            unknown = sorted(set(action.depends_on) - known)
            if unknown:
                raise ValueError(f"{action.action_id} depends_on unknown action_id(s): {unknown}")
            if action.action_id in action.depends_on:
                raise ValueError(f"{action.action_id} depends on itself.")
            edges[action.action_id] = list(action.depends_on)

        # Iterative depth-first cycle detection; the plan is small and this keeps
        # the failure message pointed at a concrete action.
        state: dict[str, int] = dict.fromkeys(known, 0)
        for root in action_ids:
            if state[root] != 0:
                continue
            stack: list[tuple[str, int]] = [(root, 0)]
            while stack:
                node, index = stack.pop()
                if index == 0:
                    if state[node] == 2:
                        continue
                    state[node] = 1
                if index < len(edges[node]):
                    stack.append((node, index + 1))
                    nxt = edges[node][index]
                    if state[nxt] == 1:
                        raise ValueError(
                            f"next_actions dependency graph contains a cycle involving {nxt}."
                        )
                    if state[nxt] == 0:
                        stack.append((nxt, 0))
                else:
                    state[node] = 2
        return self
