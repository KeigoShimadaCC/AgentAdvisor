from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from orchestrator.ach import (
    diagnosticity,
    rank_by_disconfirmation,
    zero_diagnosticity_records,
)
from orchestrator.artifacts import (
    ACHMatrix,
    DisclosureRecord,
    EvidenceRecord,
    FinalRecommendation,
    IndependentReview,
    PreMortemReport,
    ProbabilityEstimate,
)
from orchestrator.artifacts.sentinels import (
    confidence_render_label,
    model_stability_render_label,
)
from orchestrator.case_store import atomic_write_text
from orchestrator.citations import (
    collect_final_recommendation_citation_ids,
    validate_final_recommendation_citations,
)
from orchestrator.value_model import (
    WEIGHT_PERTURBATION,
    compute_ranking,
    normalize_weights,
    weight_sensitivity,
)

PROVENANCE_SOURCED_FACT = "sourced_fact"
PROVENANCE_ASSUMPTION = "assumption"
PROVENANCE_CALCULATION = "calculation"
PROVENANCE_USER_INPUT = "user_input"
PROVENANCE_INTERPRETATION = "interpretation"
PROVENANCE_RECOMMENDATION = "recommendation"


def _format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _format_probability(estimate: ProbabilityEstimate) -> str:
    if estimate.point is not None:
        return _format_percent(estimate.point)
    if estimate.interval_low is None or estimate.interval_high is None:
        raise ValueError("ProbabilityEstimate must have either point or interval values.")
    return f"{_format_percent(estimate.interval_low)} to {_format_percent(estimate.interval_high)}"


def _sorted_unique_evidence_ids(evidence_ids: Iterable[str]) -> list[str]:
    return sorted(set(evidence_ids))


def _citation_suffix(evidence_ids: Sequence[str]) -> str:
    if not evidence_ids:
        return ""
    return " " + " ".join(
        f"[{evidence_id}]" for evidence_id in _sorted_unique_evidence_ids(evidence_ids)
    )


def _escape_md_cell(value: str) -> str:
    return value.replace("|", r"\|").replace("\n", " ")


def _ensure_terminal_punctuation(text: str) -> str:
    stripped = text.rstrip()
    if stripped.endswith((".", "!", "?")):
        return stripped
    return f"{stripped}."


def _independence_group_label(group: str) -> str:
    """Convert a raw independence group slug into a human-readable label.

    Group slugs look like ``publisher-bloomberg``, ``origin-nyt.com``, or
    ``wire-associated-press`` (new format, origin-keyed) or
    ``question-slug-publisher-bloomberg`` (old format, question-keyed).
    The label strips the question prefix and category tag, keeping only
    the identifying part.
    """
    # Try new format first: tag at start
    for tag in ("publisher-", "origin-", "wire-"):
        if group.startswith(tag):
            return group[len(tag) :].replace("-", " ").title()
    # Old format: tag after question slug
    for tag in ("-publisher-", "-origin-", "-wire-"):
        idx = group.find(tag)
        if idx >= 0:
            return group[idx + len(tag) :].replace("-", " ").title()
    if "uncertain-source-cluster" in group:
        return "Uncertain source"
    return group


def _format_failure_mode_severity(level: str) -> str:
    return level.replace("_", " ").lower()


def _render_premortem_section(report: PreMortemReport) -> list[str]:
    """Render the pre-mortem section from a PreMortemReport artifact."""
    lines: list[str] = []
    lines.append("## Pre-mortem")
    lines.append("")
    lines.append(f"- [{PROVENANCE_INTERPRETATION}] Horizon: {report.horizon}")
    lines.append(
        f"- [{PROVENANCE_INTERPRETATION}] Assumed outcome: "
        f"{_ensure_terminal_punctuation(report.assumed_outcome)}"
    )
    lines.append("")
    lines.append("### Failure modes")
    for mode in report.failure_modes:
        lines.append(
            f"- [{PROVENANCE_INTERPRETATION}] "
            f"{_ensure_terminal_punctuation(mode.failure_mode)} "
            f"(probability: {_format_probability(mode.probability)}, "
            f"severity: {_format_failure_mode_severity(mode.severity.value)})."
        )
        lines.append(f"  - Narrative: {mode.narrative}")
        lines.append(f"  - Leading indicators: {', '.join(mode.leading_indicators)}")
        if mode.referenced_evidence_ids:
            lines.append(f"  - Evidence: {', '.join(mode.referenced_evidence_ids)}")
        if mode.referenced_assumption_ids:
            lines.append(f"  - Assumptions: {', '.join(mode.referenced_assumption_ids)}")
    lines.append("")
    lines.append(
        f"- [{PROVENANCE_INTERPRETATION}] Most likely failure mode: "
        f"{_ensure_terminal_punctuation(report.most_likely_failure_mode)}"
    )
    lines.append("")
    return lines


def _render_independent_review_section(review: IndependentReview | None) -> list[str]:
    """Render the independent reviewer's verdict (SPEC-039).

    A dissent that survived to delivery is reported verbatim rather than dropped:
    disclosing disagreement the system could not resolve beats suppressing it.
    """
    if review is None:
        return []
    lines = ["## Independent review"]
    lines.append("")
    lines.append(
        f"- [{PROVENANCE_INTERPRETATION}] Verdict: {review.verdict.value.replace('_', ' ')}."
    )
    lines.append(
        f"- [{PROVENANCE_INTERPRETATION}] {_ensure_terminal_punctuation(review.reasoning)}"
    )
    if review.divergent_conclusion:
        lines.append(
            f"- [{PROVENANCE_INTERPRETATION}] The independent reviewer would instead "
            f"recommend: {_ensure_terminal_punctuation(review.divergent_conclusion)}"
        )
    for claim in review.unsupported_claims:
        lines.append(
            f"- [{PROVENANCE_INTERPRETATION}] Flagged as unsupported by the evidence: "
            f"{_ensure_terminal_punctuation(claim)}"
        )
    lines.append("")
    return lines


def _render_ach_section(matrix: ACHMatrix | None) -> list[str]:
    """Render the competing-hypotheses exhibit (SPEC-040).

    The zero-diagnosticity list is included deliberately: naming the evidence that could
    never have changed the answer is one of the more useful things the technique produces.
    """
    if matrix is None:
        return []
    standings = rank_by_disconfirmation(matrix)
    if not standings:
        return []

    weights = diagnosticity(matrix)
    lines = ["## Competing hypotheses"]
    lines.append("")
    lines.append(
        f"- [{PROVENANCE_CALCULATION}] Alternatives ranked by weight of disconfirming "
        "evidence, least disconfirmed first. Evidence consistent with every alternative "
        "carries no weight."
    )
    lines.append("")
    lines.append("| Rank | Alternative | Disconfirming weight | Records against |")
    lines.append("|---|---|---|---|")
    for standing in standings:
        against = (
            ", ".join(standing.disconfirming_evidence_ids)
            if standing.disconfirming_evidence_ids
            else "—"
        )
        lines.append(
            f"| {standing.rank} | {_escape_md_cell(standing.alternative)} "
            f"| {standing.weighted_inconsistency:.2f} | {against} |"
        )
    lines.append("")

    informative = sorted(
        (eid for eid, value in weights.items() if value > 0),
        key=lambda eid: (-weights[eid], eid),
    )
    if informative:
        top = ", ".join(f"{eid} ({weights[eid]:.2f})" for eid in informative[:5])
        lines.append(f"- [{PROVENANCE_CALCULATION}] Most discriminating evidence: {top}.")
    uninformative = zero_diagnosticity_records(matrix)
    if uninformative:
        lines.append(
            f"- [{PROVENANCE_CALCULATION}] {len(uninformative)} record(s) scored the same "
            f"against every alternative and could not have changed the ranking: "
            f"{', '.join(uninformative)}."
        )
    if matrix.excluded_evidence_ids:
        lines.append(
            f"- [{PROVENANCE_CALCULATION}] "
            f"{len(matrix.excluded_evidence_ids)} record(s) fell below the authority cut "
            "for the capped matrix and were not scored."
        )
    lines.append("")
    return lines


def _render_value_model_section(
    recommendation: FinalRecommendation,
    objective_weights: Mapping[str, float] | None,
) -> list[str]:
    """Render the weighted ranking and its weight sensitivity (SPEC-038).

    Emits nothing when no value model was elicited, so cases predating the weights
    render exactly as before.
    """
    if not objective_weights:
        return []
    ranked = compute_ranking(objective_weights, recommendation.alternatives_considered)
    if not ranked:
        return []

    normalized = normalize_weights(objective_weights)
    lines = ["## Weighted ranking"]
    lines.append("")
    weight_summary = ", ".join(
        f"{name} {share:.0%}" for name, share in sorted(normalized.items(), key=lambda kv: -kv[1])
    )
    lines.append(f"- [{PROVENANCE_USER_INPUT}] Objective weights: {weight_summary}.")
    lines.append("")
    lines.append("| Weighted rank | Alternative | Score | Rank stated by synthesis |")
    lines.append("|---|---|---|---|")
    for row in ranked:
        lines.append(
            f"| {row.computed_rank} | {_escape_md_cell(row.alternative)} "
            f"| {row.score:.2f} | {row.stated_rank} |"
        )
    lines.append("")

    sensitivity = weight_sensitivity(objective_weights, recommendation.alternatives_considered)
    if sensitivity is not None:
        lines.append(
            f"- [{PROVENANCE_CALCULATION}] `{sensitivity.top_alternative}` stays top under "
            f"{sensitivity.share_preserving_top:.0%} of "
            f"{sensitivity.runs_total} single-weight perturbations of "
            f"±{int(WEIGHT_PERTURBATION * 100)}%."
        )
        if sensitivity.smallest_flip is not None:
            name, direction = sensitivity.smallest_flip
            lines.append(
                f"- [{PROVENANCE_CALCULATION}] Changing the weight on `{name}` by "
                f"{direction:+.0%} flips the top choice."
            )
        else:
            lines.append(
                f"- [{PROVENANCE_CALCULATION}] No single weight perturbation of "
                f"±{int(WEIGHT_PERTURBATION * 100)}% changes the top choice."
            )
        lines.append("")
    return lines


def render_final_recommendation_markdown(
    recommendation: FinalRecommendation,
    evidence_records: Sequence[EvidenceRecord],
    *,
    disclosure_record: DisclosureRecord | None = None,
    user_supplied_inputs: Sequence[str] = (),
    premortem_report: PreMortemReport | None = None,
    objective_weights: Mapping[str, float] | None = None,
    independent_review: IndependentReview | None = None,
    unanswered_questions: Sequence[str] = (),
    ach_matrix: ACHMatrix | None = None,
) -> str:
    validate_final_recommendation_citations(recommendation, evidence_records)
    evidence_by_id = {record.evidence_id: record for record in evidence_records}
    lines: list[str] = []

    lines.append("# Final recommendation")
    lines.append("")
    lines.append("## Executive recommendation")
    lines.append(
        f"- [{PROVENANCE_RECOMMENDATION}] Recommended action: "
        f"{_ensure_terminal_punctuation(recommendation.recommended_action)}"
    )
    lines.append(
        f"- [{PROVENANCE_RECOMMENDATION}] Timing: "
        f"{_ensure_terminal_punctuation(recommendation.timing)}"
    )
    lines.append("")
    lines.append("## Decision confidence")
    lines.append(f"- [{PROVENANCE_INTERPRETATION}] {recommendation.decision_confidence_summary}")
    lines.append(
        f"- [{PROVENANCE_CALCULATION}] Recommendation confidence: "
        f"{confidence_render_label(recommendation.recommendation_confidence)}"
    )
    lines.append(
        f"- [{PROVENANCE_CALCULATION}] Evidence confidence: "
        f"{confidence_render_label(recommendation.evidence_confidence)}"
    )
    lines.append(
        f"- [{PROVENANCE_CALCULATION}] Model stability: "
        f"{model_stability_render_label(recommendation.model_stability)}."
    )
    for outcome_name in sorted(recommendation.outcome_probabilities):
        probability = recommendation.outcome_probabilities[outcome_name]
        outcome_citations: list[str] = []
        for adjustment in probability.adjustments:
            outcome_citations.extend(adjustment.evidence_ids)
        lines.append(
            f"- [{PROVENANCE_CALCULATION}] Outcome probability — {outcome_name}: "
            f"{_format_probability(probability)} via `{probability.method.value}`."
            f"{_citation_suffix(outcome_citations)}"
        )
    lines.append("")
    lines.append("## Alternatives considered")
    for assessment in sorted(recommendation.alternatives_considered, key=lambda item: item.rank):
        lines.append(
            f"- [{PROVENANCE_INTERPRETATION}] Rank {assessment.rank}: "
            f"`{assessment.alternative}` — {assessment.rationale}"
        )
    lines.append("")
    lines.extend(_render_value_model_section(recommendation, objective_weights))
    lines.extend(_render_ach_section(ach_matrix))
    lines.append("## Key reasons")
    for reason in recommendation.key_reasons:
        lines.append(f"- [{PROVENANCE_INTERPRETATION}] {reason}")
    lines.append("")
    lines.append("## Scenario analysis")
    for scenario in recommendation.scenario_analysis:
        scenario_citations: list[str] = []
        for adjustment in scenario.probability.adjustments:
            scenario_citations.extend(adjustment.evidence_ids)
        lines.append(
            f"- [{PROVENANCE_CALCULATION}] `{scenario.scenario_name}`: "
            f"{scenario.summary} (probability: {_format_probability(scenario.probability)})."
            f"{_citation_suffix(scenario_citations)}"
        )
    lines.append("")
    lines.append("## Quantitative findings")
    if recommendation.quantitative_findings:
        for finding in recommendation.quantitative_findings:
            lines.append(f"- [{PROVENANCE_CALCULATION}] {finding}")
    else:
        lines.append("- [calculation] No additional quantitative findings were provided.")
    lines.append("")
    lines.append("## Strongest counterarguments")
    if recommendation.strongest_counterarguments:
        for counterargument in recommendation.strongest_counterarguments:
            status = "resolved" if counterargument.resolved else "unresolved"
            lines.append(
                f"- [{PROVENANCE_INTERPRETATION}] Counterargument ({status}): "
                f"{_ensure_terminal_punctuation(counterargument.claim)}"
            )
            lines.append(
                f"  - [{PROVENANCE_INTERPRETATION}] Resolution/status detail: "
                f"{counterargument.resolution}"
            )
    else:
        lines.append("- [interpretation] No material counterarguments were provided.")
    lines.append("")
    if premortem_report is not None:
        lines.extend(_render_premortem_section(premortem_report))
    lines.append("## Critical assumptions")
    if recommendation.critical_assumptions:
        for assumption_id in recommendation.critical_assumptions:
            lines.append(f"- [{PROVENANCE_ASSUMPTION}] {assumption_id}")
    else:
        lines.append("- [assumption] No critical assumptions were listed.")
    lines.append("")
    lines.append("## What would change the recommendation")
    if recommendation.recommendation_change_triggers:
        for trigger in recommendation.recommendation_change_triggers:
            lines.append(f"- [{PROVENANCE_INTERPRETATION}] {trigger}")
    else:
        lines.append("- [interpretation] No explicit recommendation-change triggers were provided.")
    lines.append("")
    lines.append("## Limitations")
    if recommendation.limitations:
        for limitation in recommendation.limitations:
            lines.append(
                f"- [{PROVENANCE_INTERPRETATION}] {_ensure_terminal_punctuation(limitation)}"
            )
    else:
        lines.append(
            f"- [{PROVENANCE_INTERPRETATION}] No limitations were stated. Treat that as an "
            "omission rather than as a claim of completeness."
        )
    if unanswered_questions:
        lines.append(
            f"- [{PROVENANCE_INTERPRETATION}] Questions the investigation did not answer: "
            f"{'; '.join(unanswered_questions)}."
        )
    lines.append("")
    lines.extend(_render_independent_review_section(independent_review))
    lines.append("## Next actions")
    lines.append("")
    lines.append("| # | Action | Owner | By | First step |")
    lines.append("|---|---|---|---|---|")
    for action in recommendation.next_actions:
        lines.append(
            f"| {_escape_md_cell(action.action_id)} "
            f"| {_escape_md_cell(action.action)} "
            f"| {_escape_md_cell(action.owner)} "
            f"| {action.by_date.isoformat()} "
            f"| {_escape_md_cell(action.first_step)} |"
        )
    lines.append("")
    for action in recommendation.next_actions:
        detail = f"{action.action_id}: {_ensure_terminal_punctuation(action.why_now)}"
        if action.estimated_cost is not None:
            detail = f"{detail} Estimated cost: {action.estimated_cost}."
        if action.depends_on:
            detail = f"{detail} Depends on {', '.join(sorted(action.depends_on))}."
        lines.append(f"- [{PROVENANCE_RECOMMENDATION}] {detail}")
    lines.append("")
    if user_supplied_inputs:
        lines.append("## User-supplied inputs")
        for user_input in user_supplied_inputs:
            lines.append(f"- [{PROVENANCE_USER_INPUT}] {user_input}")
        lines.append("")
    if disclosure_record is not None:
        lines.append("## Budget/depth stop disclosure")
        stop_reasons = ", ".join(reason.value for reason in disclosure_record.stop_reasons)
        exhausted = ", ".join(disclosure_record.exhausted_dimensions)
        lines.append(f"- [{PROVENANCE_INTERPRETATION}] Stop reasons: {stop_reasons}.")
        lines.append(f"- [{PROVENANCE_INTERPRETATION}] Exhausted dimensions: {exhausted}.")
        lines.append("")
    lines.append("## Evidence and citations")
    citation_ids = collect_final_recommendation_citation_ids(recommendation)
    citation_refs = " ".join(f"[{evidence_id}]" for evidence_id in citation_ids)
    lines.append(f"- [{PROVENANCE_SOURCED_FACT}] Inline evidence references: {citation_refs}")
    lines.append("")
    lines.append(
        "| Evidence ID | Claim | Publisher | Source URL | Publication date | Independence group |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for evidence_id in citation_ids:
        record = evidence_by_id[evidence_id]
        lines.append(
            "| "
            f"{record.evidence_id} | "
            f"{_escape_md_cell(record.claim)} | "
            f"{_escape_md_cell(record.publisher)} | "
            f"{_escape_md_cell(record.source_url)} | "
            f"{record.publication_date.isoformat()} | "
            f"{_escape_md_cell(_independence_group_label(record.independence_group))} |"
        )
    lines.append("")
    lines.append("## Provenance labels")
    lines.append(f"- `[{PROVENANCE_SOURCED_FACT}]`: sourced fact grounded in evidence records.")
    lines.append(f"- `[{PROVENANCE_ASSUMPTION}]`: explicit assumption references.")
    lines.append(f"- `[{PROVENANCE_CALCULATION}]`: quantitative or modeled statement.")
    lines.append(f"- `[{PROVENANCE_USER_INPUT}]`: user-provided input.")
    lines.append(f"- `[{PROVENANCE_INTERPRETATION}]`: synthesis interpretation.")
    lines.append(f"- `[{PROVENANCE_RECOMMENDATION}]`: normative recommendation statement.")
    lines.append("")

    return "\n".join(lines)


def write_final_recommendation_markdown(
    case_root: Path,
    recommendation: FinalRecommendation,
    evidence_records: Sequence[EvidenceRecord],
    *,
    disclosure_record: DisclosureRecord | None = None,
    user_supplied_inputs: Sequence[str] = (),
    premortem_report: PreMortemReport | None = None,
    objective_weights: Mapping[str, float] | None = None,
    independent_review: IndependentReview | None = None,
    unanswered_questions: Sequence[str] = (),
    ach_matrix: ACHMatrix | None = None,
) -> Path:
    markdown = render_final_recommendation_markdown(
        recommendation,
        evidence_records,
        disclosure_record=disclosure_record,
        user_supplied_inputs=user_supplied_inputs,
        premortem_report=premortem_report,
        objective_weights=objective_weights,
        independent_review=independent_review,
        unanswered_questions=unanswered_questions,
        ach_matrix=ach_matrix,
    )
    output_path = case_root / "outputs" / "final_recommendation.md"
    atomic_write_text(output_path, markdown)
    return output_path
