from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from orchestrator.artifacts import (
    AssumptionRecord,
    DecisionSpec,
    EvidenceRecord,
    Level,
    ObjectionRecord,
    TaskRecord,
)
from orchestrator.artifacts.schema_export import MODEL_EXPORTS
from orchestrator.artifacts.yaml_io import dump_model_to_yaml_text, load_model_from_yaml_text
from orchestrator.case_store import Case


@dataclass(frozen=True, slots=True)
class ProjectedArtifact:
    filename: str
    yaml_text: str


@dataclass(frozen=True, slots=True)
class _Candidate:
    filename: str
    yaml_text: str


def _decision_spec(case: Case) -> list[_Candidate]:
    try:
        record = case.read_artifact(DecisionSpec)
    except FileNotFoundError:
        return []
    return [_Candidate(filename="decision_spec.yaml", yaml_text=dump_model_to_yaml_text(record))]


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


def _output_artifact(case: Case, artifact_type: str) -> list[_Candidate]:
    model_type = MODEL_EXPORTS.get(artifact_type)
    if model_type is None:
        return []
    output_path = case.root / "outputs" / f"{artifact_type}.yaml"
    if not output_path.exists():
        return []
    loaded = load_model_from_yaml_text(model_type, output_path.read_text(encoding="utf-8"))
    yaml_text = dump_model_to_yaml_text(loaded)
    return [_Candidate(filename=f"{artifact_type}.yaml", yaml_text=yaml_text)]


_INCLUDE_HANDLERS: dict[str, Callable[[Case], list[_Candidate]]] = {
    "decision_spec": _decision_spec,
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
}


def _resolve_candidates(case: Case, include_key: str) -> list[_Candidate]:
    handler = _INCLUDE_HANDLERS.get(include_key)
    if handler is not None:
        return handler(case)
    return _output_artifact(case, include_key)


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
