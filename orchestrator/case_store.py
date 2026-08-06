"""Case blackboard storage primitives.

This module is the single owner of `cases/` path construction.

Live agent workspaces are intentionally outside the repository tree because the
`report-and-findings/2026-07-31-agents-md-leakage.md` finding showed
`cursor-agent` loads `AGENTS.md` files from workspace ancestors. Keeping runtime
workspaces out of the repo avoids inheriting development instructions.

Concurrency scope for v1 is one process with multiple threads. Cross-process
locking is explicitly out of scope.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel

from orchestrator.artifacts import (
    ACHMatrix,
    AnalysisResult,
    AssumptionBatch,
    AssumptionRecord,
    AuditEvent,
    AuditFinding,
    CaseMemoryDigest,
    DecisionSpec,
    DisclosureRecord,
    EvidenceBatch,
    EvidenceCritique,
    EvidenceRecord,
    FinalApproval,
    FinalRecommendation,
    FramingApproval,
    GateReport,
    IndependentReview,
    IntakeRecord,
    IssueTree,
    MonitoringPlan,
    ObjectionBatch,
    ObjectionRecord,
    PreliminaryRecommendation,
    PreMortemReport,
    PriorEvidenceDigest,
    ReviewReport,
    TaskProposalBatch,
    TaskRecord,
    ThesisRevision,
    TrackDivergence,
    VerificationWorksheet,
)
from orchestrator.artifacts.yaml_io import dump_model_to_yaml_text, load_model_from_yaml_path

ModelT = TypeVar("ModelT", bound=BaseModel)

_CASE_DIR_RE = re.compile(r"^case-(\d+)-([a-z0-9]+(?:-[a-z0-9]+)*)$")
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_COUNTER_PREFIXES = {"E-", "A-", "T-", "O-"}
_UNSAFE_FILENAME_RE = re.compile(r"[^a-z0-9._-]+")


def _safe_stem(value: str) -> str:
    """Reduce an arbitrary label to a filename-safe stem."""
    stem = _UNSAFE_FILENAME_RE.sub("-", value.strip().lower()).strip("-")
    if not stem:
        raise ValueError(f"Cannot derive a filename from '{value}'.")
    return stem


# Phase 6 artifacts that live at one fixed path per case.
_SINGLETON_ARTIFACT_TYPES: tuple[type[BaseModel], ...] = (
    IssueTree,
    EvidenceCritique,
    TrackDivergence,
    PreMortemReport,
    VerificationWorksheet,
    CaseMemoryDigest,
    PriorEvidenceDigest,
)


def default_cases_root() -> Path:
    configured = os.getenv("AGENTADVISOR_CASES_ROOT")
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parents[1] / "cases"


def _required_layout_paths(case_root: Path) -> tuple[Path, ...]:
    return (
        case_root / "shared",
        case_root / "shared" / "evidence",
        case_root / "shared" / "assumptions",
        case_root / "shared" / "objections",
        case_root / "shared" / "tasks",
        case_root / "shared" / "task_graph.yaml",
        case_root / "agents",
        case_root / "analysis",
        case_root / "outputs",
        case_root / "state.yaml",
        case_root / "audit.jsonl",
    )


def atomic_write_text(path: Path, content: str) -> None:
    """Write `content` to `path` atomically, leaving no partial or stray temp file.

    Public because non-artifact case files (notably `state.yaml`) need the same
    durability guarantee without going through the artifact path mapping.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.tmp-",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()
        raise


def _artifact_path_for_write(case_root: Path, model: BaseModel) -> Path:
    if isinstance(model, EvidenceBatch):
        raise TypeError(
            "EvidenceBatch cannot be written directly to case storage. "
            "Batches are transport envelopes archived with the agent workspace "
            "(agents/<role>--<task_id>/outputs). Unpack into EvidenceRecord artifacts via "
            "orchestrator.unpack.unpack_evidence_batch(case, batch)."
        )
    if isinstance(model, ObjectionBatch):
        raise TypeError(
            "ObjectionBatch cannot be written directly to case storage. "
            "Batches are transport envelopes archived with the agent workspace "
            "(agents/<role>--<task_id>/outputs). Unpack into ObjectionRecord artifacts via "
            "orchestrator.unpack.unpack_objection_batch(case, batch)."
        )
    if isinstance(model, AssumptionBatch):
        raise TypeError(
            "AssumptionBatch cannot be written directly to case storage. "
            "Batches are transport envelopes archived with the agent workspace "
            "(agents/<role>--<task_id>/outputs). Unpack into AssumptionRecord artifacts via "
            "orchestrator.unpack.unpack_assumption_batch(case, batch)."
        )
    if isinstance(model, IntakeRecord):
        return case_root / "shared" / "intake_record.yaml"
    if isinstance(model, FramingApproval):
        return case_root / "shared" / "framing_approval.yaml"
    if isinstance(model, IssueTree):
        return case_root / "shared" / "issue_tree.yaml"
    if isinstance(model, EvidenceCritique):
        return case_root / "shared" / "evidence_critique.yaml"
    if isinstance(model, TrackDivergence):
        return case_root / "shared" / "track_divergence.yaml"
    if isinstance(model, PreMortemReport):
        return case_root / "shared" / "premortem_report.yaml"
    if isinstance(model, VerificationWorksheet):
        return case_root / "shared" / "verification_worksheet.yaml"
    if isinstance(model, CaseMemoryDigest):
        return case_root / "shared" / "case_memory_digest.yaml"
    if isinstance(model, PriorEvidenceDigest):
        return case_root / "shared" / "prior_evidence_digest.yaml"
    if isinstance(model, GateReport):
        return case_root / "shared" / "gates" / f"{_safe_stem(model.stage)}.yaml"
    if isinstance(model, ThesisRevision):
        return case_root / "shared" / "thesis" / f"thesis-{model.revision:03d}.yaml"
    if isinstance(model, DecisionSpec):
        return case_root / "shared" / "decision_spec.yaml"
    if isinstance(model, PreliminaryRecommendation):
        return case_root / "shared" / "preliminary_recommendation.yaml"
    if isinstance(model, FinalRecommendation):
        return case_root / "outputs" / "final_recommendation.yaml"
    if isinstance(model, FinalApproval):
        return case_root / "outputs" / "final_approval.yaml"
    if isinstance(model, TaskProposalBatch):
        return case_root / "shared" / "task_proposal_batch.yaml"
    if isinstance(model, AnalysisResult):
        return case_root / "analysis" / f"{model.task_id}.analysis_result.yaml"
    if isinstance(model, AuditFinding):
        return case_root / "shared" / "audit_finding.yaml"
    if isinstance(model, ACHMatrix):
        return case_root / "shared" / "ach_matrix.yaml"
    if isinstance(model, MonitoringPlan):
        return case_root / "outputs" / "monitoring_plan.yaml"
    if isinstance(model, ReviewReport):
        return case_root / "outputs" / "review_report.yaml"
    if isinstance(model, IndependentReview):
        return case_root / "outputs" / "independent_review.yaml"
    if isinstance(model, DisclosureRecord):
        return case_root / "shared" / "disclosure_record.yaml"
    if isinstance(model, EvidenceRecord):
        return case_root / "shared" / "evidence" / f"{model.evidence_id}.yaml"
    if isinstance(model, AssumptionRecord):
        return case_root / "shared" / "assumptions" / f"{model.assumption_id}.yaml"
    if isinstance(model, ObjectionRecord):
        return case_root / "shared" / "objections" / f"{model.objection_id}.yaml"
    if isinstance(model, TaskRecord):
        return case_root / "shared" / "tasks" / f"{model.task_id}.yaml"
    raise TypeError(f"Unsupported artifact model type: {type(model).__name__}")


def _artifact_path_for_read(
    case_root: Path, model_type: type[BaseModel], artifact_id: str | None
) -> Path:
    if issubclass(model_type, IntakeRecord):
        return case_root / "shared" / "intake_record.yaml"
    if issubclass(model_type, FramingApproval):
        return case_root / "shared" / "framing_approval.yaml"
    if issubclass(model_type, DecisionSpec):
        return case_root / "shared" / "decision_spec.yaml"
    if issubclass(model_type, IssueTree):
        return case_root / "shared" / "issue_tree.yaml"
    if issubclass(model_type, EvidenceCritique):
        return case_root / "shared" / "evidence_critique.yaml"
    if issubclass(model_type, TrackDivergence):
        return case_root / "shared" / "track_divergence.yaml"
    if issubclass(model_type, PreMortemReport):
        return case_root / "shared" / "premortem_report.yaml"
    if issubclass(model_type, VerificationWorksheet):
        return case_root / "shared" / "verification_worksheet.yaml"
    if issubclass(model_type, CaseMemoryDigest):
        return case_root / "shared" / "case_memory_digest.yaml"
    if issubclass(model_type, PriorEvidenceDigest):
        return case_root / "shared" / "prior_evidence_digest.yaml"
    if issubclass(model_type, GateReport):
        if artifact_id is None:
            raise ValueError(f"artifact_id is required for {model_type.__name__}")
        return case_root / "shared" / "gates" / f"{_safe_stem(artifact_id)}.yaml"
    if issubclass(model_type, ThesisRevision):
        if artifact_id is None:
            raise ValueError(f"artifact_id is required for {model_type.__name__}")
        return case_root / "shared" / "thesis" / f"{artifact_id}.yaml"
    if issubclass(model_type, PreliminaryRecommendation):
        return case_root / "shared" / "preliminary_recommendation.yaml"
    if issubclass(model_type, FinalRecommendation):
        return case_root / "outputs" / "final_recommendation.yaml"
    if issubclass(model_type, FinalApproval):
        return case_root / "outputs" / "final_approval.yaml"
    if issubclass(model_type, TaskProposalBatch):
        return case_root / "shared" / "task_proposal_batch.yaml"
    if issubclass(model_type, AnalysisResult):
        if artifact_id is None:
            raise ValueError(f"artifact_id is required for {model_type.__name__}")
        return case_root / "analysis" / f"{artifact_id}.analysis_result.yaml"
    if issubclass(model_type, AuditFinding):
        return case_root / "shared" / "audit_finding.yaml"
    if issubclass(model_type, ACHMatrix):
        return case_root / "shared" / "ach_matrix.yaml"
    if issubclass(model_type, MonitoringPlan):
        return case_root / "outputs" / "monitoring_plan.yaml"
    if issubclass(model_type, ReviewReport):
        return case_root / "outputs" / "review_report.yaml"
    if issubclass(model_type, IndependentReview):
        return case_root / "outputs" / "independent_review.yaml"
    if issubclass(model_type, DisclosureRecord):
        return case_root / "shared" / "disclosure_record.yaml"
    if artifact_id is None:
        raise ValueError(f"artifact_id is required for {model_type.__name__}")
    if issubclass(model_type, EvidenceRecord):
        return case_root / "shared" / "evidence" / f"{artifact_id}.yaml"
    if issubclass(model_type, AssumptionRecord):
        return case_root / "shared" / "assumptions" / f"{artifact_id}.yaml"
    if issubclass(model_type, ObjectionRecord):
        return case_root / "shared" / "objections" / f"{artifact_id}.yaml"
    if issubclass(model_type, TaskRecord):
        return case_root / "shared" / "tasks" / f"{artifact_id}.yaml"
    raise TypeError(f"Unsupported artifact model type: {model_type.__name__}")


def _artifact_dir_for_list(case_root: Path, model_type: type[BaseModel]) -> Path:
    if issubclass(model_type, GateReport):
        return case_root / "shared" / "gates"
    if issubclass(model_type, ThesisRevision):
        return case_root / "shared" / "thesis"
    if issubclass(model_type, IntakeRecord):
        return case_root / "shared"
    if issubclass(model_type, FramingApproval):
        return case_root / "shared"
    if issubclass(model_type, DecisionSpec):
        return case_root / "shared"
    if issubclass(model_type, PreliminaryRecommendation):
        return case_root / "shared"
    if issubclass(model_type, FinalRecommendation):
        return case_root / "outputs"
    if issubclass(model_type, FinalApproval):
        return case_root / "outputs"
    if issubclass(model_type, TaskProposalBatch):
        return case_root / "shared"
    if issubclass(model_type, AnalysisResult):
        return case_root / "analysis"
    if issubclass(model_type, AuditFinding):
        return case_root / "shared"
    if issubclass(model_type, ACHMatrix):
        return case_root / "shared"
    if issubclass(model_type, MonitoringPlan):
        return case_root / "outputs"
    if issubclass(model_type, ReviewReport):
        return case_root / "outputs"
    if issubclass(model_type, IndependentReview):
        return case_root / "outputs"
    if issubclass(model_type, DisclosureRecord):
        return case_root / "shared"
    if issubclass(model_type, EvidenceRecord):
        return case_root / "shared" / "evidence"
    if issubclass(model_type, AssumptionRecord):
        return case_root / "shared" / "assumptions"
    if issubclass(model_type, ObjectionRecord):
        return case_root / "shared" / "objections"
    if issubclass(model_type, TaskRecord):
        return case_root / "shared" / "tasks"
    raise TypeError(f"Unsupported artifact model type: {model_type.__name__}")


@dataclass(slots=True)
class Case:
    root: Path
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def write_artifact(self, model: BaseModel) -> Path:
        path = _artifact_path_for_write(self.root, model)
        payload = dump_model_to_yaml_text(model)
        atomic_write_text(path, payload)
        return path

    def read_artifact(self, model_type: type[ModelT], artifact_id: str | None = None) -> ModelT:
        path = _artifact_path_for_read(self.root, model_type, artifact_id)
        if not path.exists():
            raise FileNotFoundError(f"Artifact not found: {path}")
        return load_model_from_yaml_path(model_type, path)

    def next_id(self, prefix: str) -> str:
        if prefix not in _COUNTER_PREFIXES:
            raise ValueError(f"Unsupported ID prefix: {prefix}")
        counters_path = self.root / "shared" / "counters.yaml"
        with self._lock:
            counters: dict[str, int] = {}
            if counters_path.exists():
                loaded = yaml.safe_load(counters_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    counters = {
                        str(key): int(value)
                        for key, value in loaded.items()
                        if str(key) in _COUNTER_PREFIXES
                    }

            next_value = counters.get(prefix, 0) + 1
            counters[prefix] = next_value
            dumped = yaml.safe_dump(counters, sort_keys=True)
            atomic_write_text(counters_path, dumped)
            return f"{prefix}{next_value:03d}"

    def audit(self, event: AuditEvent) -> None:
        audit_path = self.root / "audit.jsonl"
        line = json.dumps(event.model_dump(mode="json"), separators=(",", ":"), sort_keys=True)
        with self._lock:
            with audit_path.open("a", encoding="utf-8") as fh:
                fh.write(f"{line}\n")
                fh.flush()

    def list_artifacts(self, model_type: type[ModelT]) -> list[ModelT]:
        if issubclass(model_type, _SINGLETON_ARTIFACT_TYPES):
            singleton_path = _artifact_path_for_read(self.root, model_type, None)
            if not singleton_path.exists():
                return []
            return [load_model_from_yaml_path(model_type, singleton_path)]
        if issubclass(model_type, IntakeRecord):
            intake_path = self.root / "shared" / "intake_record.yaml"
            if not intake_path.exists():
                return []
            return [load_model_from_yaml_path(model_type, intake_path)]
        if issubclass(model_type, FramingApproval):
            framing_path = self.root / "shared" / "framing_approval.yaml"
            if not framing_path.exists():
                return []
            return [load_model_from_yaml_path(model_type, framing_path)]
        if issubclass(model_type, DecisionSpec):
            decision_path = self.root / "shared" / "decision_spec.yaml"
            if not decision_path.exists():
                return []
            return [load_model_from_yaml_path(model_type, decision_path)]
        if issubclass(model_type, PreliminaryRecommendation):
            preliminary_path = self.root / "shared" / "preliminary_recommendation.yaml"
            if not preliminary_path.exists():
                return []
            return [load_model_from_yaml_path(model_type, preliminary_path)]
        if issubclass(model_type, FinalRecommendation):
            final_path = self.root / "outputs" / "final_recommendation.yaml"
            if not final_path.exists():
                return []
            return [load_model_from_yaml_path(model_type, final_path)]
        if issubclass(model_type, FinalApproval):
            final_approval_path = self.root / "outputs" / "final_approval.yaml"
            if not final_approval_path.exists():
                return []
            return [load_model_from_yaml_path(model_type, final_approval_path)]
        if issubclass(model_type, TaskProposalBatch):
            proposal_path = self.root / "shared" / "task_proposal_batch.yaml"
            if not proposal_path.exists():
                return []
            return [load_model_from_yaml_path(model_type, proposal_path)]
        if issubclass(model_type, AuditFinding):
            finding_path = self.root / "shared" / "audit_finding.yaml"
            if not finding_path.exists():
                return []
            return [load_model_from_yaml_path(model_type, finding_path)]
        if issubclass(model_type, MonitoringPlan):
            plan_path = self.root / "outputs" / "monitoring_plan.yaml"
            if not plan_path.exists():
                return []
            return [load_model_from_yaml_path(model_type, plan_path)]
        if issubclass(model_type, ACHMatrix):
            ach_path = self.root / "shared" / "ach_matrix.yaml"
            if not ach_path.exists():
                return []
            return [load_model_from_yaml_path(model_type, ach_path)]
        if issubclass(model_type, IndependentReview):
            independent_path = self.root / "outputs" / "independent_review.yaml"
            if not independent_path.exists():
                return []
            return [load_model_from_yaml_path(model_type, independent_path)]
        if issubclass(model_type, ReviewReport):
            review_path = self.root / "outputs" / "review_report.yaml"
            if not review_path.exists():
                return []
            return [load_model_from_yaml_path(model_type, review_path)]
        if issubclass(model_type, DisclosureRecord):
            disclosure_path = self.root / "shared" / "disclosure_record.yaml"
            if not disclosure_path.exists():
                return []
            return [load_model_from_yaml_path(model_type, disclosure_path)]
        if issubclass(model_type, AnalysisResult):
            analysis_dir = self.root / "analysis"
            if not analysis_dir.exists():
                return []
            return [
                load_model_from_yaml_path(model_type, path)
                for path in sorted(analysis_dir.glob("*.analysis_result.yaml"))
            ]

        artifact_dir = _artifact_dir_for_list(self.root, model_type)
        if not artifact_dir.exists():
            return []
        return [
            load_model_from_yaml_path(model_type, path)
            for path in sorted(artifact_dir.glob("*.yaml"))
        ]

    def archive_agent_workspace(self, role: str, task_id: str, workspace_path: Path) -> Path:
        if not workspace_path.is_dir():
            raise FileNotFoundError(f"Workspace path is not a directory: {workspace_path}")
        destination = self.root / "agents" / f"{role}--{task_id}"
        if destination.exists():
            # Collision-safe: archive to the next available --rerun-<n> suffix.
            n = 0
            while destination.exists():
                n += 1
                destination = self.root / "agents" / f"{role}--{task_id}--rerun-{n}"
        shutil.copytree(workspace_path, destination)
        return destination


def create_case(slug: str, cases_root: Path | None = None) -> Case:
    if not _SLUG_RE.fullmatch(slug):
        raise ValueError(f"Invalid slug '{slug}'. Use lowercase letters, digits, and hyphens.")

    root = cases_root or default_cases_root()
    root.mkdir(parents=True, exist_ok=True)

    max_number = 0
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        match = _CASE_DIR_RE.fullmatch(entry.name)
        if match is None:
            continue
        max_number = max(max_number, int(match.group(1)))

    case_id = f"case-{max_number + 1:03d}-{slug}"
    case_root = root / case_id
    case_root.mkdir(parents=False, exist_ok=False)

    for path in (
        case_root / "shared" / "evidence",
        case_root / "shared" / "assumptions",
        case_root / "shared" / "objections",
        case_root / "shared" / "tasks",
        case_root / "shared" / "gates",
        case_root / "shared" / "thesis",
        case_root / "agents",
        case_root / "analysis",
        case_root / "outputs",
    ):
        path.mkdir(parents=True, exist_ok=True)

    (case_root / "shared" / "task_graph.yaml").write_text("{}\n", encoding="utf-8")
    (case_root / "state.yaml").write_text("{}\n", encoding="utf-8")
    (case_root / "audit.jsonl").write_text("", encoding="utf-8")

    return Case(root=case_root)


def load_case(case_id: str, cases_root: Path | None = None) -> Case:
    if _CASE_DIR_RE.fullmatch(case_id) is None:
        raise ValueError(f"Invalid case_id '{case_id}'")

    root = cases_root or default_cases_root()
    case_root = root / case_id
    if not case_root.exists():
        raise FileNotFoundError(f"Case directory does not exist: {case_root}")
    if not case_root.is_dir():
        raise NotADirectoryError(f"Case path is not a directory: {case_root}")

    missing: list[str] = []
    for path in _required_layout_paths(case_root):
        if not path.exists():
            missing.append(str(path.relative_to(case_root)))
    if missing:
        missing_str = ", ".join(missing)
        raise FileNotFoundError(f"Case layout is incomplete for {case_id}. Missing: {missing_str}")

    return Case(root=case_root)


def runtime_root() -> Path:
    configured = os.getenv("AGENTADVISOR_RUNTIME_ROOT")
    if configured:
        root = Path(configured).expanduser()
    else:
        root = Path("~/.local/share/agentadvisor/workspaces").expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root
