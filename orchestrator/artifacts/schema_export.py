from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from orchestrator.artifacts.ach import ACHMatrix
from orchestrator.artifacts.analysis import AnalysisResult
from orchestrator.artifacts.approvals import FinalApproval
from orchestrator.artifacts.assumptions import AssumptionBatch, AssumptionRecord
from orchestrator.artifacts.audit import AuditEvent, AuditUsage
from orchestrator.artifacts.audit_findings import AuditFinding
from orchestrator.artifacts.confidence import ConfidenceAssessment
from orchestrator.artifacts.decision import DecisionSpec
from orchestrator.artifacts.disclosure import DisclosureRecord
from orchestrator.artifacts.evidence import EvidenceBatch, EvidenceRecord
from orchestrator.artifacts.evidence_critique import EvidenceCritique
from orchestrator.artifacts.gates import GateReport
from orchestrator.artifacts.intake import FramingApproval, IntakeRecord
from orchestrator.artifacts.issue_tree import IssueTree
from orchestrator.artifacts.memory import (
    CalibrationSummary,
    CaseMemoryDigest,
    PriorEvidenceDigest,
)
from orchestrator.artifacts.monitoring import MonitoringPlan
from orchestrator.artifacts.objections import ObjectionBatch, ObjectionRecord
from orchestrator.artifacts.premortem import PreMortemReport
from orchestrator.artifacts.probability import ProbabilityAdjustment, ProbabilityEstimate
from orchestrator.artifacts.recommendations import (
    AlternativeAssessment,
    Counterargument,
    FinalRecommendation,
    PreliminaryRecommendation,
    ScenarioAssessment,
)
from orchestrator.artifacts.review import IndependentReview, ReviewReport
from orchestrator.artifacts.stability import ModelStability
from orchestrator.artifacts.task_proposals import TaskProposalBatch
from orchestrator.artifacts.tasks import TaskRecord
from orchestrator.artifacts.thesis import ThesisRevision
from orchestrator.artifacts.tracks import TrackDivergence
from orchestrator.artifacts.verification import VerificationWorksheet
from orchestrator.service.caseview import (
    ApprovalRecordView,
    AssessedConfidence,
    AssessedStability,
    AssumptionView,
    BriefBlock,
    BriefSection,
    CaseView,
    ChallengesRoom,
    EffortView,
    GateSummaryView,
    HistoryView,
    IntegrityView,
    IssueNodeView,
    NotAssessed,
    ObjectionView,
    OptionView,
    PlanView,
    PreMortemView,
    ProbabilityView,
    RoomsView,
    SourcesRoom,
    SourceView,
    TrackDivergenceView,
    UncertaintyView,
)

type ModelType = type[BaseModel]


MODEL_EXPORTS: dict[str, ModelType] = {
    "ach_matrix": ACHMatrix,
    "analysis_result": AnalysisResult,
    "alternative_assessment": AlternativeAssessment,
    "assumption_batch": AssumptionBatch,
    "assumption_record": AssumptionRecord,
    "audit_event": AuditEvent,
    "audit_finding": AuditFinding,
    "audit_usage": AuditUsage,
    "calibration_summary": CalibrationSummary,
    "case_memory_digest": CaseMemoryDigest,
    "confidence_assessment": ConfidenceAssessment,
    "counterargument": Counterargument,
    "decision_spec": DecisionSpec,
    "disclosure_record": DisclosureRecord,
    "evidence_batch": EvidenceBatch,
    "evidence_critique": EvidenceCritique,
    "evidence_record": EvidenceRecord,
    "final_approval": FinalApproval,
    "final_recommendation": FinalRecommendation,
    "framing_approval": FramingApproval,
    "gate_report": GateReport,
    "intake_record": IntakeRecord,
    "issue_tree": IssueTree,
    "monitoring_plan": MonitoringPlan,
    "objection_record": ObjectionRecord,
    "objection_batch": ObjectionBatch,
    "premortem_report": PreMortemReport,
    "preliminary_recommendation": PreliminaryRecommendation,
    "prior_evidence_digest": PriorEvidenceDigest,
    "probability_adjustment": ProbabilityAdjustment,
    "probability_estimate": ProbabilityEstimate,
    "review_report": ReviewReport,
    "independent_review": IndependentReview,
    "scenario_assessment": ScenarioAssessment,
    "task_proposal_batch": TaskProposalBatch,
    "task_record": TaskRecord,
    "thesis_revision": ThesisRevision,
    "track_divergence": TrackDivergence,
    "verification_worksheet": VerificationWorksheet,
    "model_stability": ModelStability,
    # CaseView projection (SPEC-032) and nested models.
    "approval_record_view": ApprovalRecordView,
    "assessed_confidence": AssessedConfidence,
    "assessed_stability": AssessedStability,
    "assumption_view": AssumptionView,
    "brief_block": BriefBlock,
    "brief_section": BriefSection,
    "case_view": CaseView,
    "challenges_room": ChallengesRoom,
    "effort_view": EffortView,
    "gate_summary_view": GateSummaryView,
    "history_view": HistoryView,
    "integrity_view": IntegrityView,
    "issue_node_view": IssueNodeView,
    "not_assessed": NotAssessed,
    "objection_view": ObjectionView,
    "option_view": OptionView,
    "plan_view": PlanView,
    "premortem_view": PreMortemView,
    "probability_view": ProbabilityView,
    "rooms_view": RoomsView,
    "sources_room": SourcesRoom,
    "source_view": SourceView,
    "track_divergence_view": TrackDivergenceView,
    "uncertainty_view": UncertaintyView,
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
