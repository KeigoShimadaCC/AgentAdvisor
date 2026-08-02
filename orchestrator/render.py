from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from orchestrator.artifacts import (
    ConfidenceAssessment,
    DisclosureRecord,
    EvidenceRecord,
    FinalRecommendation,
    PreMortemReport,
    ProbabilityEstimate,
)
from orchestrator.artifacts.sentinels import (
    is_unassessed_confidence,
    is_unassessed_stability,
)
from orchestrator.case_store import Case, atomic_write_text
from orchestrator.citations import (
    collect_final_recommendation_citation_ids,
    validate_final_recommendation_citations,
)
from orchestrator.normalize import humanize_independence_group

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


def _confidence_line(label: str, confidence: ConfidenceAssessment) -> str:
    """A coerced placeholder is reported as unassessed, never as a percentage.

    North star Section 9 forbids presenting one uncertainty quantity as another;
    a filler basis carrying a default value is not a measurement of anything, so
    the number is withheld and the basis speaks for itself.
    """
    if is_unassessed_confidence(confidence):
        return f"- [{PROVENANCE_CALCULATION}] {label}: not assessed (basis: {confidence.basis})."
    return (
        f"- [{PROVENANCE_CALCULATION}] {label}: {_format_percent(confidence.value)} "
        f"(basis: {confidence.basis})."
    )


def _premortem_lines(report: PreMortemReport) -> list[str]:
    lines = ["## Pre-mortem"]
    lines.append(
        f"- [{PROVENANCE_INTERPRETATION}] Assumed outcome over {report.horizon}: "
        f"{_ensure_terminal_punctuation(report.assumed_outcome)}"
    )
    for mode in report.failure_modes:
        marker = " (most likely)" if mode.failure_mode == report.most_likely_failure_mode else ""
        lines.append(
            f"- [{PROVENANCE_INTERPRETATION}] Failure mode{marker}: `{mode.failure_mode}` — "
            f"{_ensure_terminal_punctuation(mode.narrative)} "
            f"(probability: {_format_probability(mode.probability)}; "
            f"severity: {mode.severity.value})."
        )
        indicators = "; ".join(mode.leading_indicators)
        lines.append(f"  - [{PROVENANCE_INTERPRETATION}] Leading indicators: {indicators}.")
        lines.append(
            f"  - [{PROVENANCE_RECOMMENDATION}] Preventive action: "
            f"{_ensure_terminal_punctuation(mode.preventive_action)}"
        )
    return lines


def render_final_recommendation_markdown(
    recommendation: FinalRecommendation,
    evidence_records: Sequence[EvidenceRecord],
    *,
    disclosure_record: DisclosureRecord | None = None,
    user_supplied_inputs: Sequence[str] = (),
    premortem_report: PreMortemReport | None = None,
) -> str:
    """Render the canonical Markdown export.

    Citations stay next to the claims that carry them (north star Section 10):
    each bullet shows only the references its own content supplies, and the whole
    corpus appears once in "Evidence and citations". Appending the shared list to
    every bullet made roughly two fifths of the document duplicated noise and told
    the reader nothing about which source supported which claim.
    """
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
        _confidence_line("Recommendation confidence", recommendation.recommendation_confidence)
    )
    lines.append(_confidence_line("Evidence confidence", recommendation.evidence_confidence))
    if is_unassessed_stability(recommendation.model_stability):
        lines.append(f"- [{PROVENANCE_CALCULATION}] Model stability: not assessed (single run).")
    else:
        stability_share = (
            recommendation.model_stability.share_of_sensitivity_runs_supporting_recommendation
        )
        lines.append(
            f"- [{PROVENANCE_CALCULATION}] Model stability: "
            f"{_format_percent(stability_share)} "
            f"({recommendation.model_stability.runs_supporting}/"
            f"{recommendation.model_stability.runs_total} sensitivity runs support "
            "the recommendation)."
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
        lines.extend(_premortem_lines(premortem_report))
        lines.append("")
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
    lines.append("## Next actions")
    for action in recommendation.next_actions:
        lines.append(f"- [{PROVENANCE_RECOMMENDATION}] {action}")
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
            f"{_escape_md_cell(humanize_independence_group(record.independence_group))} |"
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
) -> Path:
    """Render and persist the export, reading the pre-mortem from the case itself.

    The pre-mortem is written by its own stage and is not carried by the caller,
    so the report went unread until the renderer looked it up.
    """
    premortem_reports = Case(root=case_root).list_artifacts(PreMortemReport)
    markdown = render_final_recommendation_markdown(
        recommendation,
        evidence_records,
        disclosure_record=disclosure_record,
        user_supplied_inputs=user_supplied_inputs,
        premortem_report=premortem_reports[0] if premortem_reports else None,
    )
    output_path = case_root / "outputs" / "final_recommendation.md"
    atomic_write_text(output_path, markdown)
    return output_path
