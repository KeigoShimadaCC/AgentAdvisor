from __future__ import annotations

import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel

from orchestrator.artifacts import AuditEvent, AuditUsage, DecisionSpec, IntakeRecord, TaskRecord
from orchestrator.artifacts.schema_export import MODEL_EXPORTS
from orchestrator.artifacts.yaml_io import (
    CoercionReport,
    coerce_payload_for_model,
    fill_missing_required_defaults,
    load_model_from_yaml_text,
)
from orchestrator.backend import (
    AgentBackend,
    CursorCLIBackend,
    ResultStatus,
    RoleInvocation,
    RoleResult,
)
from orchestrator.budget import BudgetKind
from orchestrator.case_store import Case
from orchestrator.isolation import WorkspaceNotIsolated, assert_isolated
from orchestrator.projection import project
from orchestrator.roles_config import RoleConfig, load_role_config
from orchestrator.skills import SkillPack, select_packs
from orchestrator.task_graph import BudgetLedgerLike
from orchestrator.workspace import (
    WorkspaceTask,
    archive_attempt,
    archive_final,
    build_workspace,
    delete_runtime_workspace,
)

# Source titles and publishers routinely contain a colon, and an unquoted one makes the
# whole artifact unparseable, so the quoting rule is worth the two lines it costs here.
_YAML_QUOTING_RULE = (
    'Quote any string value containing a colon, for example publisher: "Applied '
    'Economics: Case Studies". '
)
FIXED_PROMPT = (
    "Read AGENTS.md for role instructions. Read task.yaml and inputs/. "
    + _YAML_QUOTING_RULE
    + "Write exactly the required output file under outputs/ and stop."
)
FIXED_READ_ONLY_PROMPT = (
    "Read AGENTS.md for role instructions. Read task.yaml and inputs/. "
    + _YAML_QUOTING_RULE
    + "Return exactly one fenced ```yaml``` block containing the required artifact and stop."
)
DEFAULT_TIMEOUT_S = 120.0
DEFAULT_PROJECTION_BUDGET_CHARS = 20_000

CrossFieldHook = Callable[[BaseModel, Case], None]
_CROSS_FIELD_HOOKS: dict[str, list[CrossFieldHook]] = {}


@dataclass(frozen=True, slots=True)
class InvokeTask:
    task_id: str
    assignment: str
    output_artifact_type: str
    timeout_s: float = DEFAULT_TIMEOUT_S
    projection_budget_chars: int = DEFAULT_PROJECTION_BUDGET_CHARS
    mode: str | None = None


class RoleInvocationFailed(RuntimeError):
    pass


def register_cross_field_validation_hook(artifact_type: str, hook: CrossFieldHook) -> None:
    hooks = _CROSS_FIELD_HOOKS.setdefault(artifact_type, [])
    hooks.append(hook)


def clear_cross_field_validation_hooks(artifact_type: str | None = None) -> None:
    if artifact_type is None:
        _CROSS_FIELD_HOOKS.clear()
        return
    _CROSS_FIELD_HOOKS.pop(artifact_type, None)


def _coerce_task(task: TaskRecord | InvokeTask) -> InvokeTask:
    if isinstance(task, InvokeTask):
        return task
    assignment = (
        f"Question: {task.question}\n"
        f"Why it matters: {task.why_it_matters}\n"
        f"Completion criteria: {task.completion_criteria}\n"
        f"Expected information gain: {task.expected_information_gain}\n"
        f"Materiality: {task.materiality}\n"
    )
    return InvokeTask(
        task_id=task.task_id,
        assignment=assignment,
        output_artifact_type=task.required_output,
    )


def _build_attempt_plan(config: RoleConfig) -> list[str]:
    return [config.default_model, config.default_model, config.escalation_model]


def _case_decision_text(case: Case) -> str:
    specs = case.list_artifacts(DecisionSpec)
    if specs:
        spec = specs[0]
        return " ".join([spec.question, *spec.alternatives, *spec.objectives])
    intakes = case.list_artifacts(IntakeRecord)
    if intakes:
        return intakes[0].decision_question or intakes[0].raw_prompt
    return ""


def _case_skill_packs(case: Case) -> list[SkillPack]:
    """Packs are chosen from the decision question by the orchestrator, never by an agent."""
    text = _case_decision_text(case)
    if not text:
        return []
    return select_packs(text)


def _required_output_filename(artifact_type: str) -> str:
    return f"{artifact_type}.yaml"


def _artifact_model_type(artifact_type: str) -> type[BaseModel]:
    model_type = MODEL_EXPORTS.get(artifact_type)
    if model_type is None:
        raise RoleInvocationFailed(f"Unknown output artifact type: {artifact_type}")
    return model_type


def _extract_yaml_block(result_text: str) -> str:
    match = re.search(r"```(?:yaml|yml)\s*\n(.*?)```", result_text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip() + "\n"
    return result_text.strip() + "\n"


def _apply_cross_field_validation(artifact_type: str, artifact: BaseModel, case: Case) -> None:
    for hook in _CROSS_FIELD_HOOKS.get(artifact_type, []):
        hook(artifact, case)


def _validate_output(
    *,
    artifact_type: str,
    yaml_text: str,
    case: Case,
) -> tuple[BaseModel, CoercionReport]:
    """Validate the YAML output, coercing common mistakes if needed.

    Returns the validated artifact and a CoercionReport (empty if no
    coercion was needed).
    """
    model_type = _artifact_model_type(artifact_type)
    report = CoercionReport()
    try:
        artifact = load_model_from_yaml_text(model_type, yaml_text)
    except Exception:
        # Try coercing common model formatting mistakes (nested objects -> strings, etc.)
        # Then try filling missing required fields with conservative defaults.
        payload = yaml.safe_load(yaml_text)
        coerced = coerce_payload_for_model(model_type, payload, report=report)
        filled = fill_missing_required_defaults(model_type, coerced, report=report)
        if filled is not payload:
            artifact = model_type.model_validate(filled)
        else:
            raise
    # Cross-field validation runs after successful model validation, whether
    # or not coercion was needed.  Its failure must not trigger coercion.
    _apply_cross_field_validation(artifact_type=artifact_type, artifact=artifact, case=case)
    return artifact, report


def _audit_attempt(
    *,
    case: Case,
    role: str,
    task_id: str,
    attempt: int,
    model: str,
    backend_result: RoleResult | None,
    status: str,
    detail: str | None,
    coercion_report: CoercionReport | None = None,
) -> None:
    usage = None
    if backend_result is not None and backend_result.usage is not None:
        usage = AuditUsage(
            input_tokens=backend_result.usage.input_tokens,
            output_tokens=backend_result.usage.output_tokens,
            total_tokens=backend_result.usage.total_tokens,
        )
    payload: dict[str, Any] = {
        "task_id": task_id,
        "attempt": attempt,
        "status": status,
        "detail": detail,
        "backend_status": backend_result.status.value if backend_result is not None else None,
    }
    if coercion_report is not None and coercion_report.has_coercions:
        payload["coercions"] = [
            {
                "field": rec.field_path,
                "type": rec.coercion_type,
                "from": rec.original_type,
                "to": rec.coerced_to,
            }
            for rec in coercion_report.records
        ]
    case.audit(
        AuditEvent(
            ts=datetime.now(UTC),
            actor=role,
            event_type="role_invocation_attempt",
            payload=payload,
            model=model,
            cli_version=backend_result.cli_version if backend_result is not None else None,
            usage=usage,
            duration_ms=backend_result.duration_ms if backend_result is not None else 0,
        )
    )


def _invoke_internal(
    *,
    case: Case,
    role: str,
    task: TaskRecord | InvokeTask,
    backend: AgentBackend | None,
    read_only_stdout: bool,
    variant: str | None,
    budget_ledger: BudgetLedgerLike | None = None,
    consume_agent_invocations: bool = True,
) -> BaseModel:
    config = load_role_config(role, variant)
    normalized_task = _coerce_task(task)
    if normalized_task.output_artifact_type != config.output_artifact_type:
        raise RoleInvocationFailed(
            "Task output artifact type does not match role config: "
            f"task={normalized_task.output_artifact_type}, role={config.output_artifact_type}"
        )

    # Consume one agent_invocation per invoke() call (not per attempt).
    # The retry ladder stays an internal reliability mechanism.
    if budget_ledger is not None and consume_agent_invocations:
        budget_ledger.try_consume(BudgetKind.AGENT_INVOCATIONS.value)

    projected_inputs = project(
        case=case,
        include=config.projection_include,
        budget_chars=normalized_task.projection_budget_chars,
    )
    backend_impl = backend or CursorCLIBackend()
    skill_packs = _case_skill_packs(case)
    attempts = _build_attempt_plan(config)
    errors: list[str] = []
    workspace_path: Path | None = None

    for attempt_index, model in enumerate(attempts, start=1):
        # An attempt on the escalation model with a high model_tier consumes
        # high_tier_calls.  This is per-attempt, not per-invocation.
        if (
            budget_ledger is not None
            and model == config.escalation_model
            and budget_ledger.is_high_tier_model(model)
        ):
            budget_ledger.try_consume(BudgetKind.HIGH_TIER_CALLS.value)

        feedback = errors[-1] if errors else None
        workspace_task = WorkspaceTask(
            task_id=normalized_task.task_id,
            assignment=normalized_task.assignment,
            required_output_filename=_required_output_filename(
                normalized_task.output_artifact_type
            ),
            required_output_schema=normalized_task.output_artifact_type,
            feedback=feedback,
            mode=normalized_task.mode,
        )
        layout = build_workspace(
            case=case,
            role_config=config,
            role=role,
            task=workspace_task,
            projected_inputs=projected_inputs,
            skill_packs=skill_packs,
        )
        workspace_path = layout.path

        backend_result: RoleResult | None = None
        failure_detail: str | None = None
        try:
            assert_isolated(layout.path)
            backend_result = backend_impl.run(
                RoleInvocation(
                    role=role,
                    model=model,
                    prompt=FIXED_READ_ONLY_PROMPT if read_only_stdout else FIXED_PROMPT,
                    workspace=layout.path,
                    timeout_s=normalized_task.timeout_s,
                    read_only=read_only_stdout or config.read_only,
                )
            )
            if backend_result.status is not ResultStatus.OK:
                failure_detail = (
                    f"backend status={backend_result.status.value} "
                    f"stderr={backend_result.raw_stderr}"
                )
                errors.append(failure_detail)
                _audit_attempt(
                    case=case,
                    role=role,
                    task_id=normalized_task.task_id,
                    attempt=attempt_index,
                    model=model,
                    backend_result=backend_result,
                    status="backend_failure",
                    detail=failure_detail,
                )
                archive_attempt(case, role, normalized_task.task_id, layout.path, attempt_index)
                continue

            if read_only_stdout:
                if backend_result.result_text is None:
                    raise ValueError("Agent result envelope did not contain a `result` string.")
                output_yaml = _extract_yaml_block(backend_result.result_text)
            else:
                if not layout.output_path.exists():
                    raise FileNotFoundError(f"Required output file not found: {layout.output_path}")
                output_yaml = layout.output_path.read_text(encoding="utf-8")

            artifact, coercion_report = _validate_output(
                artifact_type=normalized_task.output_artifact_type,
                yaml_text=output_yaml,
                case=case,
            )

            # Copy analysis/ directory from workspace to case root (for analyst role).
            _analysis_src = layout.path / "analysis"
            if _analysis_src.exists():
                _analysis_dst = case.root / "analysis"
                _analysis_dst.mkdir(parents=True, exist_ok=True)
                shutil.copytree(_analysis_src, _analysis_dst, dirs_exist_ok=True)

            _audit_attempt(
                case=case,
                role=role,
                task_id=normalized_task.task_id,
                attempt=attempt_index,
                model=model,
                backend_result=backend_result,
                status="ok",
                detail=None,
                coercion_report=coercion_report if coercion_report.has_coercions else None,
            )
            archive_final(case, role, normalized_task.task_id, layout.path)
            delete_runtime_workspace(layout.path)
            return artifact
        except WorkspaceNotIsolated as exc:
            failure_detail = str(exc)
            _audit_attempt(
                case=case,
                role=role,
                task_id=normalized_task.task_id,
                attempt=attempt_index,
                model=model,
                backend_result=backend_result,
                status="isolation_failure",
                detail=failure_detail,
            )
            errors.append(failure_detail)
            archive_attempt(case, role, normalized_task.task_id, layout.path, attempt_index)
        except Exception as exc:  # noqa: BLE001
            failure_detail = str(exc)
            _audit_attempt(
                case=case,
                role=role,
                task_id=normalized_task.task_id,
                attempt=attempt_index,
                model=model,
                backend_result=backend_result,
                status="validation_failure",
                detail=failure_detail,
            )
            errors.append(failure_detail)
            archive_attempt(case, role, normalized_task.task_id, layout.path, attempt_index)

    if workspace_path is not None:
        delete_runtime_workspace(workspace_path)
    ladder = (
        "attempt 1: default model -> attempt 2: retry default model -> attempt 3: escalation model"
    )
    raise RoleInvocationFailed(f"Invocation failed after escalation ({ladder}). Errors: {errors}")


def invoke(
    case: Case,
    role: str,
    task: TaskRecord | InvokeTask,
    *,
    backend: AgentBackend | None = None,
    variant: str | None = None,
    budget_ledger: BudgetLedgerLike | None = None,
    consume_agent_invocations: bool = True,
) -> BaseModel:
    return _invoke_internal(
        case=case,
        role=role,
        task=task,
        backend=backend,
        read_only_stdout=False,
        variant=variant,
        budget_ledger=budget_ledger,
        consume_agent_invocations=consume_agent_invocations,
    )


def invoke_read_only(
    case: Case,
    role: str,
    task: TaskRecord | InvokeTask,
    *,
    backend: AgentBackend | None = None,
    variant: str | None = None,
    budget_ledger: BudgetLedgerLike | None = None,
    consume_agent_invocations: bool = True,
) -> BaseModel:
    return _invoke_internal(
        case=case,
        role=role,
        task=task,
        backend=backend,
        read_only_stdout=True,
        variant=variant,
        budget_ledger=budget_ledger,
        consume_agent_invocations=consume_agent_invocations,
    )
