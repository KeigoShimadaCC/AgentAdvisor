from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel

from orchestrator.artifacts import (
    AnalysisResult,
    AssumptionRecord,
    AuditFinding,
    DecisionSpec,
    DisclosureRecord,
    EvidenceRecord,
    FinalRecommendation,
    FramingApproval,
    IntakeRecord,
    Level,
    ObjectionRecord,
    PreliminaryRecommendation,
    ReviewReport,
    TaskProposalBatch,
    TaskRecord,
)
from orchestrator.artifacts.yaml_io import dump_model_to_yaml_text
from orchestrator.case_store import Case


@dataclass(frozen=True, slots=True)
class ProjectedArtifact:
    filename: str
    yaml_text: str


@dataclass(frozen=True, slots=True)
class _Candidate:
    filename: str
    yaml_text: str


class ProjectionError(ValueError):
    pass


def _singleton[T: BaseModel](case: Case, model_type: type[T], *, filename: str) -> list[_Candidate]:
    try:
        record = case.read_artifact(model_type)
    except FileNotFoundError:
        return []
    return [_Candidate(filename=filename, yaml_text=dump_model_to_yaml_text(record))]


def _decision_spec(case: Case) -> list[_Candidate]:
    return _singleton(case, DecisionSpec, filename="decision_spec.yaml")


def _intake_record(case: Case) -> list[_Candidate]:
    return _singleton(case, IntakeRecord, filename="intake_record.yaml")


def _framing_approval(case: Case) -> list[_Candidate]:
    return _singleton(case, FramingApproval, filename="framing_approval.yaml")


def _preliminary_recommendation(case: Case) -> list[_Candidate]:
    return _singleton(
        case,
        PreliminaryRecommendation,
        filename="preliminary_recommendation.yaml",
    )


def _final_recommendation(case: Case) -> list[_Candidate]:
    return _singleton(case, FinalRecommendation, filename="final_recommendation.yaml")


def _disclosure_record(case: Case) -> list[_Candidate]:
    return _singleton(case, DisclosureRecord, filename="disclosure_record.yaml")


def _review_report(case: Case) -> list[_Candidate]:
    return _singleton(case, ReviewReport, filename="review_report.yaml")


def _task_proposal_batch(case: Case) -> list[_Candidate]:
    return _singleton(case, TaskProposalBatch, filename="task_proposal_batch.yaml")


def _audit_finding(case: Case) -> list[_Candidate]:
    return _singleton(case, AuditFinding, filename="audit_finding.yaml")


def _with_ids[T: BaseModel](
    records: list[T],
    *,
    filename_prefix: str,
    id_getter: Callable[[T], str],
) -> list[_Candidate]:
    newest_first = list(reversed(records))
    return [
        _Candidate(
            filename=f"{filename_prefix}--{id_getter(record)}.yaml",
            yaml_text=dump_model_to_yaml_text(record),
        )
        for record in newest_first
    ]


def _evidence(case: Case) -> list[_Candidate]:
    records = case.list_artifacts(EvidenceRecord)
    return _with_ids(
        records, filename_prefix="evidence_record", id_getter=lambda record: record.evidence_id
    )


def _assumptions(case: Case) -> list[_Candidate]:
    records = case.list_artifacts(AssumptionRecord)
    return _with_ids(
        records,
        filename_prefix="assumption_record",
        id_getter=lambda record: record.assumption_id,
    )


def _high_materiality_assumptions(case: Case) -> list[_Candidate]:
    records = [
        record
        for record in case.list_artifacts(AssumptionRecord)
        if record.materiality is Level.HIGH
    ]
    return _with_ids(
        records,
        filename_prefix="assumption_record",
        id_getter=lambda record: record.assumption_id,
    )


def _objections(case: Case) -> list[_Candidate]:
    records = case.list_artifacts(ObjectionRecord)
    return _with_ids(
        records,
        filename_prefix="objection_record",
        id_getter=lambda record: record.objection_id,
    )


def _tasks(case: Case) -> list[_Candidate]:
    records = case.list_artifacts(TaskRecord)
    return _with_ids(
        records, filename_prefix="task_record", id_getter=lambda record: record.task_id
    )


def _analysis_results(case: Case) -> list[_Candidate]:
    records = case.list_artifacts(AnalysisResult)
    return _with_ids(
        records,
        filename_prefix="analysis_result",
        id_getter=lambda record: record.task_id,
    )


def _one_line(text: str, *, limit: int = 140) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 1].rstrip()}…"


def _task_graph(case: Case) -> list[_Candidate]:
    records = case.list_artifacts(TaskRecord)
    if not records:
        return []

    graph_path = case.root / "shared" / "task_graph.yaml"
    edges: dict[str, list[str]] = {}
    if graph_path.exists():
        loaded = yaml.safe_load(graph_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            loaded_edges = loaded.get("edges")
            if isinstance(loaded_edges, dict):
                for task_id, dependencies in loaded_edges.items():
                    if isinstance(task_id, str) and isinstance(dependencies, list):
                        normalized = [dep for dep in dependencies if isinstance(dep, str)]
                        edges[task_id] = normalized

    tasks_summary = [
        {
            "task_id": record.task_id,
            "role": record.role.value,
            "status": record.status.value,
            "dependencies": edges.get(record.task_id, []),
            "priority": record.priority.value,
            "priority_score": record.priority_score,
            "question": record.question,
        }
        for record in records
    ]
    summary = {"kind": "task_graph_summary", "tasks": tasks_summary}
    return [
        _Candidate(
            filename="task_graph.yaml",
            yaml_text=yaml.safe_dump(summary, sort_keys=False),
        )
    ]


def _artifact_index(case: Case) -> list[_Candidate]:
    entries: list[dict[str, str]] = []

    for evidence_record in case.list_artifacts(EvidenceRecord):
        entries.append(
            {
                "id": evidence_record.evidence_id,
                "type": "evidence_record",
                "summary": _one_line(evidence_record.claim),
            }
        )
    for assumption_record in case.list_artifacts(AssumptionRecord):
        entries.append(
            {
                "id": assumption_record.assumption_id,
                "type": "assumption_record",
                "summary": _one_line(assumption_record.claim),
            }
        )
    for objection_record in case.list_artifacts(ObjectionRecord):
        entries.append(
            {
                "id": objection_record.objection_id,
                "type": "objection_record",
                "summary": _one_line(objection_record.claim),
            }
        )
    for task_record in case.list_artifacts(TaskRecord):
        entries.append(
            {
                "id": task_record.task_id,
                "type": "task_record",
                "summary": _one_line(task_record.question),
            }
        )
    for analysis_record in case.list_artifacts(AnalysisResult):
        entries.append(
            {
                "id": analysis_record.task_id,
                "type": "analysis_result",
                "summary": _one_line(f"Analysis result from {analysis_record.script_path}"),
            }
        )

    intake = case.list_artifacts(IntakeRecord)
    if intake:
        intake_record = intake[0]
        summary_source = intake_record.decision_question or intake_record.raw_prompt
        entries.append(
            {
                "id": "intake_record",
                "type": "intake_record",
                "summary": _one_line(summary_source),
            }
        )
    decision = case.list_artifacts(DecisionSpec)
    if decision:
        entries.append(
            {
                "id": decision[0].decision_id,
                "type": "decision_spec",
                "summary": _one_line(decision[0].question),
            }
        )
    prelim = case.list_artifacts(PreliminaryRecommendation)
    if prelim:
        entries.append(
            {
                "id": "preliminary_recommendation",
                "type": "preliminary_recommendation",
                "summary": _one_line(f"Preferred alternative: {prelim[0].preferred_alternative}"),
            }
        )
    final = case.list_artifacts(FinalRecommendation)
    if final:
        entries.append(
            {
                "id": "final_recommendation",
                "type": "final_recommendation",
                "summary": _one_line(final[0].recommended_action),
            }
        )
    disclosure = case.list_artifacts(DisclosureRecord)
    if disclosure:
        reasons = ", ".join(reason.value for reason in disclosure[0].stop_reasons)
        entries.append(
            {
                "id": "disclosure_record",
                "type": "disclosure_record",
                "summary": _one_line(f"Stop reasons: {reasons}"),
            }
        )
    review = case.list_artifacts(ReviewReport)
    if review:
        entries.append(
            {
                "id": "review_report",
                "type": "review_report",
                "summary": _one_line(f"Outcome: {review[0].outcome.value}"),
            }
        )
    proposals = case.list_artifacts(TaskProposalBatch)
    if proposals:
        entries.append(
            {
                "id": "task_proposal_batch",
                "type": "task_proposal_batch",
                "summary": _one_line(
                    f"Mode {proposals[0].mode.value}, {len(proposals[0].proposals)} proposals"
                ),
            }
        )
    findings = case.list_artifacts(AuditFinding)
    if findings:
        entries.append(
            {
                "id": "audit_finding",
                "type": "audit_finding",
                "summary": _one_line(f"{len(findings[0].findings)} finding(s)"),
            }
        )
    framing = case.list_artifacts(FramingApproval)
    if framing:
        entries.append(
            {
                "id": "framing_approval",
                "type": "framing_approval",
                "summary": _one_line(f"Decision: {framing[0].decision.value}"),
            }
        )

    if not entries:
        return []
    payload = {"kind": "artifact_index", "artifacts": entries}
    return [
        _Candidate(
            filename="artifact_index.yaml",
            yaml_text=yaml.safe_dump(payload, sort_keys=False),
        )
    ]


def _budget_snapshot(case: Case) -> list[_Candidate]:
    state_path = case.root / "state.yaml"
    if not state_path.exists():
        return []
    loaded = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return []
    counters = loaded.get("budget_counters")
    if not isinstance(counters, dict) or not counters:
        return []
    snapshot = {
        "kind": "budget_snapshot",
        "stage": loaded.get("stage"),
        "budget_counters": counters,
        "updated_at": loaded.get("updated_at"),
    }
    return [
        _Candidate(
            filename="budget_snapshot.yaml",
            yaml_text=yaml.safe_dump(snapshot, sort_keys=False),
        )
    ]


_INCLUDE_HANDLERS: dict[str, Callable[[Case], list[_Candidate]]] = {
    "intake_record": _intake_record,
    "framing_approval": _framing_approval,
    "decision_spec": _decision_spec,
    "preliminary_recommendation": _preliminary_recommendation,
    "final_recommendation": _final_recommendation,
    "disclosure_record": _disclosure_record,
    "review_report": _review_report,
    "review_reports": _review_report,
    "task_proposal_batch": _task_proposal_batch,
    "task_proposal_batches": _task_proposal_batch,
    "audit_finding": _audit_finding,
    "audit_findings": _audit_finding,
    "analysis_result": _analysis_results,
    "analysis_results": _analysis_results,
    "evidence": _evidence,
    "evidence_records": _evidence,
    "key_evidence": _evidence,
    "assumptions": _assumptions,
    "assumption_records": _assumptions,
    "high_materiality_assumptions": _high_materiality_assumptions,
    "objections": _objections,
    "objection_records": _objections,
    "tasks": _tasks,
    "task_records": _tasks,
    "task_graph": _task_graph,
    "artifact_index": _artifact_index,
    "budget_snapshot": _budget_snapshot,
}


def _resolve_candidates(case: Case, include_key: str) -> list[_Candidate]:
    handler = _INCLUDE_HANDLERS.get(include_key)
    if handler is None:
        valid_keys = ", ".join(sorted(_INCLUDE_HANDLERS))
        raise ProjectionError(
            f"Unknown projection include key '{include_key}'. Valid keys: {valid_keys}"
        )
    return handler(case)


def _truncation_notice(omitted: list[str], budget_chars: int) -> ProjectedArtifact:
    omitted_yaml = "".join([f"  - {name}\n" for name in omitted])
    message = (
        "kind: truncation_notice\n"
        f"budget_chars: {budget_chars}\n"
        f"omitted_count: {len(omitted)}\n"
        "omitted_inputs:\n"
        f"{omitted_yaml}"
        "notice: Context was truncated by a hard character budget. "
        "Proceed using only the provided inputs.\n"
    )
    return ProjectedArtifact(filename="_truncation_notice.yaml", yaml_text=message)


def project(
    case: Case, include: list[str] | tuple[str, ...], budget_chars: int
) -> list[ProjectedArtifact]:
    if budget_chars <= 0:
        return [_truncation_notice(omitted=[], budget_chars=budget_chars)]

    candidates: list[_Candidate] = []
    for include_key in include:
        candidates.extend(_resolve_candidates(case, include_key))

    projected: list[ProjectedArtifact] = []
    omitted: list[str] = []
    used_chars = 0
    for candidate in candidates:
        candidate_chars = len(candidate.yaml_text)
        if used_chars + candidate_chars > budget_chars:
            omitted.append(candidate.filename)
            continue
        projected.append(
            ProjectedArtifact(filename=candidate.filename, yaml_text=candidate.yaml_text)
        )
        used_chars += candidate_chars

    if omitted:
        projected.append(_truncation_notice(omitted=omitted, budget_chars=budget_chars))
    return projected
