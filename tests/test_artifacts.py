from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from orchestrator.artifacts.assumptions import AssumptionRecord
from orchestrator.artifacts.audit import AuditEvent
from orchestrator.artifacts.decision import DecisionSpec
from orchestrator.artifacts.disclosure import DisclosureRecord
from orchestrator.artifacts.evidence import EvidenceRecord
from orchestrator.artifacts.objections import ObjectionRecord
from orchestrator.artifacts.probability import ProbabilityEstimate
from orchestrator.artifacts.recommendations import FinalRecommendation, PreliminaryRecommendation
from orchestrator.artifacts.schema_export import export_schemas
from orchestrator.artifacts.tasks import TaskRecord
from orchestrator.artifacts.yaml_io import dump_model_to_yaml_text, load_model_from_yaml_text

type ModelType = type[BaseModel]

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "artifacts"
REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = REPO_ROOT / "schemas"

MODEL_BY_FIXTURE: dict[str, ModelType] = {
    "assumption_record": AssumptionRecord,
    "audit_event": AuditEvent,
    "decision_spec": DecisionSpec,
    "disclosure_record": DisclosureRecord,
    "evidence_record": EvidenceRecord,
    "final_recommendation": FinalRecommendation,
    "objection_record": ObjectionRecord,
    "preliminary_recommendation": PreliminaryRecommendation,
    "probability_estimate": ProbabilityEstimate,
    "task_record": TaskRecord,
}

EXPECTED_ERROR_FIELD_BY_FIXTURE: dict[str, str] = {
    "assumption_record.invalid.yaml": "estimate",
    "audit_event.invalid.yaml": "duration_ms",
    "decision_spec.invalid.yaml": "decision_id",
    "final_recommendation.confidence_value.invalid.yaml": "value",
    "final_recommendation.model_stability.invalid.yaml": (
        "share_of_sensitivity_runs_supporting_recommendation"
    ),
    "evidence_record.invalid.yaml": "reliability",
    "final_recommendation.invalid.yaml": "citations",
    "objection_record.invalid.yaml": "commissioned_tasks",
    "preliminary_recommendation.invalid.yaml": "basis",
    "probability_estimate.invalid.yaml": "base_rate",
    "probability_estimate.reference_class_missing_base_rate.invalid.yaml": "base_rate",
    "task_record.invalid.yaml": "question",
}


def _model_for_fixture(path: Path) -> ModelType:
    prefix = path.name.split(".", maxsplit=1)[0]
    return MODEL_BY_FIXTURE[prefix]


@pytest.mark.parametrize("fixture_path", sorted(FIXTURES_DIR.glob("*.valid.yaml")))
def test_valid_fixtures_round_trip_byte_identical(fixture_path: Path) -> None:
    model_type = _model_for_fixture(fixture_path)
    original_text = fixture_path.read_text(encoding="utf-8")
    model = load_model_from_yaml_text(model_type, original_text)
    dumped_text = dump_model_to_yaml_text(model)
    assert dumped_text == original_text


@pytest.mark.parametrize("fixture_path", sorted(FIXTURES_DIR.glob("*.invalid.yaml")))
def test_invalid_fixtures_raise_validation_error_with_field_name(fixture_path: Path) -> None:
    model_type = _model_for_fixture(fixture_path)
    fixture_text = fixture_path.read_text(encoding="utf-8")
    expected_field = EXPECTED_ERROR_FIELD_BY_FIXTURE[fixture_path.name]

    with pytest.raises(ValidationError) as exc_info:
        load_model_from_yaml_text(model_type, fixture_text)

    assert expected_field in str(exc_info.value)


def test_schema_sync(tmp_path: Path) -> None:
    generated = tmp_path / "schemas"
    export_schemas(generated)

    committed_files = sorted(path for path in SCHEMAS_DIR.glob("*.schema.json"))
    generated_files = sorted(path for path in generated.glob("*.schema.json"))

    assert [path.name for path in generated_files] == [path.name for path in committed_files]

    for generated_file in generated_files:
        committed_file = SCHEMAS_DIR / generated_file.name
        generated_text = generated_file.read_text(encoding="utf-8")
        committed_text = committed_file.read_text(encoding="utf-8")
        assert generated_text == committed_text
