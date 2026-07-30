from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from orchestrator.artifacts.assumptions import AssumptionRecord
from orchestrator.artifacts.audit import AuditEvent, AuditUsage
from orchestrator.artifacts.confidence import ConfidenceAssessment
from orchestrator.artifacts.decision import DecisionSpec
from orchestrator.artifacts.evidence import EvidenceRecord
from orchestrator.artifacts.objections import ObjectionRecord
from orchestrator.artifacts.probability import ProbabilityAdjustment, ProbabilityEstimate
from orchestrator.artifacts.recommendations import (
    AlternativeAssessment,
    Counterargument,
    FinalRecommendation,
    PreliminaryRecommendation,
    ScenarioAssessment,
)
from orchestrator.artifacts.stability import ModelStability
from orchestrator.artifacts.tasks import TaskRecord

type ModelType = type[BaseModel]


MODEL_EXPORTS: dict[str, ModelType] = {
    "alternative_assessment": AlternativeAssessment,
    "assumption_record": AssumptionRecord,
    "audit_event": AuditEvent,
    "audit_usage": AuditUsage,
    "confidence_assessment": ConfidenceAssessment,
    "counterargument": Counterargument,
    "decision_spec": DecisionSpec,
    "evidence_record": EvidenceRecord,
    "final_recommendation": FinalRecommendation,
    "objection_record": ObjectionRecord,
    "preliminary_recommendation": PreliminaryRecommendation,
    "probability_adjustment": ProbabilityAdjustment,
    "probability_estimate": ProbabilityEstimate,
    "scenario_assessment": ScenarioAssessment,
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
