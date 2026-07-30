from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from orchestrator.case_store import Case, runtime_root
from orchestrator.projection import ProjectedArtifact
from orchestrator.roles_config import RoleConfig


@dataclass(frozen=True, slots=True)
class WorkspaceTask:
    task_id: str
    assignment: str
    required_output_filename: str
    required_output_schema: str
    feedback: str | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceLayout:
    path: Path
    output_path: Path
    task_yaml_path: Path


def _workspace_path(case: Case, role: str, task_id: str) -> Path:
    return runtime_root() / case.root.name / f"{role}--{task_id}"


def _permission_profile(workspace_path: Path, allow_shell: bool) -> dict[str, dict[str, list[str]]]:
    write_scope = f"Write({workspace_path}/**)"
    read_scope = f"Read({workspace_path}/**)"
    allow = [read_scope, write_scope]
    deny: list[str] = []
    if allow_shell:
        allow.append("Shell(*)")
    else:
        deny.append("Shell(*)")
    return {"permissions": {"allow": allow, "deny": deny}}


def build_workspace(
    *,
    case: Case,
    role_config: RoleConfig,
    role: str,
    task: WorkspaceTask,
    projected_inputs: list[ProjectedArtifact],
) -> WorkspaceLayout:
    workspace_path = _workspace_path(case, role=role, task_id=task.task_id)
    if workspace_path.exists():
        shutil.rmtree(workspace_path)
    (workspace_path / "inputs").mkdir(parents=True, exist_ok=True)
    (workspace_path / "outputs").mkdir(parents=True, exist_ok=True)
    (workspace_path / ".cursor").mkdir(parents=True, exist_ok=True)

    role_md_text = role_config.role_md_path.read_text(encoding="utf-8")
    (workspace_path / "AGENTS.md").write_text(role_md_text, encoding="utf-8")

    for projected in projected_inputs:
        (workspace_path / "inputs" / projected.filename).write_text(
            projected.yaml_text, encoding="utf-8"
        )

    task_payload: dict[str, Any] = {
        "task_id": task.task_id,
        "assignment": task.assignment,
        "required_output_filename": task.required_output_filename,
        "required_output_schema": task.required_output_schema,
        "inputs_dir": "inputs",
        "outputs_dir": "outputs",
    }
    if task.feedback:
        task_payload["feedback"] = task.feedback
    task_yaml = yaml.safe_dump(task_payload, sort_keys=True, allow_unicode=True)
    (workspace_path / "task.yaml").write_text(task_yaml, encoding="utf-8")

    profile_payload = _permission_profile(
        workspace_path=workspace_path, allow_shell=role_config.permission_profile.allow_shell
    )
    profile_text = json_dump(profile_payload)
    (workspace_path / ".cursor" / "cli.json").write_text(profile_text, encoding="utf-8")

    return WorkspaceLayout(
        path=workspace_path,
        output_path=workspace_path / "outputs" / task.required_output_filename,
        task_yaml_path=workspace_path / "task.yaml",
    )


def archive_attempt(
    case: Case, role: str, task_id: str, workspace_path: Path, attempt: int
) -> Path:
    archive_task_id = f"{task_id}--attempt-{attempt}"
    return case.archive_agent_workspace(
        role=role, task_id=archive_task_id, workspace_path=workspace_path
    )


def archive_final(case: Case, role: str, task_id: str, workspace_path: Path) -> Path:
    return case.archive_agent_workspace(role=role, task_id=task_id, workspace_path=workspace_path)


def delete_runtime_workspace(workspace_path: Path) -> None:
    if workspace_path.exists():
        shutil.rmtree(workspace_path)


def json_dump(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
