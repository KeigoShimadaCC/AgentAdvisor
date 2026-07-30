from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from orchestrator.artifacts.analysis import AnalysisResult
from orchestrator.artifacts.assumptions import AssumptionRecord
from orchestrator.artifacts.audit import AuditEvent, AuditUsage
from orchestrator.artifacts.audit_findings import AuditFinding
from orchestrator.artifacts.confidence import ConfidenceAssessment
from orchestrator.artifacts.decision import DecisionSpec
from orchestrator.artifacts.disclosure import DisclosureRecord
from orchestrator.artifacts.evidence import EvidenceBatch, EvidenceRecord
from orchestrator.artifacts.intake import FramingApproval, IntakeRecord
from orchestrator.artifacts.objections import ObjectionBatch, ObjectionRecord
from orchestrator.artifacts.probability import ProbabilityAdjustment, ProbabilityEstimate
from orchestrator.artifacts.recommendations import (
    AlternativeAssessment,
    Counterargument,
    FinalRecommendation,
    PreliminaryRecommendation,
    ScenarioAssessment,
)
from orchestrator.artifacts.review import ReviewReport
from orchestrator.artifacts.stability import ModelStability
from orchestrator.artifacts.task_proposals import TaskProposalBatch
from orchestrator.artifacts.tasks import TaskRecord

type ModelType = type[BaseModel]


MODEL_EXPORTS: dict[str, ModelType] = {
    "analysis_result": AnalysisResult,
    "alternative_assessment": AlternativeAssessment,
    "assumption_record": AssumptionRecord,
    "audit_event": AuditEvent,
    "audit_finding": AuditFinding,
    "audit_usage": AuditUsage,
    "confidence_assessment": ConfidenceAssessment,
    "counterargument": Counterargument,
    "decision_spec": DecisionSpec,
    "disclosure_record": DisclosureRecord,
    "evidence_batch": EvidenceBatch,
    "evidence_record": EvidenceRecord,
    "final_recommendation": FinalRecommendation,
    "framing_approval": FramingApproval,
    "intake_record": IntakeRecord,
    "objection_record": ObjectionRecord,
    "objection_batch": ObjectionBatch,
    "preliminary_recommendation": PreliminaryRecommendation,
    "probability_adjustment": ProbabilityAdjustment,
    "probability_estimate": ProbabilityEstimate,
    "review_report": ReviewReport,
    "scenario_assessment": ScenarioAssessment,
    "task_proposal_batch": TaskProposalBatch,
    "task_record": TaskRecord,
    "model_stability": ModelStability,
}


def export_schemas(output_dir: str | Path) -> list[Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []

    for name, model_type in sorted(MODEL_EXPORTS.items()):
        schema_payload = model_type.model_json_schema()
        schema_path = destination / f"{name}.schema.json"
        schema_path.write_text(
            json.dumps(schema_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written_paths.append(schema_path)

    return written_paths


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    export_schemas(repo_root / "schemas")


if __name__ == "__main__":
    main()
