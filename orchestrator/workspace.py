from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from orchestrator.case_store import Case, runtime_root
from orchestrator.projection import ProjectedArtifact
from orchestrator.roles_config import RoleConfig
from orchestrator.skills import SkillPack, packs_for_role, render_pack_section


@dataclass(frozen=True, slots=True)
class WorkspaceTask:
    task_id: str
    assignment: str
    required_output_filename: str
    required_output_schema: str
    feedback: str | None = None
    mode: str | None = None


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


#: SPEC-043. Roles allowed to see the decision owner's own documents. Everything else —
#: the reviewers and the auditor — is excluded on purpose: a reviewer anchored on private
#: material is not independent, and personal documents should travel as narrowly as the
#: work allows. Enforced here as well as by the projection config so a stray
#: ``projection_include`` edit cannot quietly widen it.
PRIVATE_EVIDENCE_ROLES: frozenset[str] = frozenset(
    {
        "researcher",
        "analyst",
        "director",
        "structurer",
        "premortem",
        "assumption_analyst",
    }
)

PRIVATE_EVIDENCE_PREFIX = "private_evidence"


class PrivateEvidenceLeak(RuntimeError):
    """A role outside the allow-list was about to receive private evidence."""


def assert_private_evidence_allowed(role: str, projected: list[ProjectedArtifact]) -> None:
    """Fail the invocation rather than leak the user's documents into a review workspace."""
    if role in PRIVATE_EVIDENCE_ROLES:
        return
    leaked = [
        artifact.filename
        for artifact in projected
        if artifact.filename.startswith(PRIVATE_EVIDENCE_PREFIX)
    ]
    if leaked:
        raise PrivateEvidenceLeak(
            f"Role {role!r} is not permitted private evidence but {len(leaked)} record(s) "
            f"were projected into its workspace: {leaked}. Remove 'private_evidence' from "
            "its projection_include, or add the role to PRIVATE_EVIDENCE_ROLES if it "
            "genuinely needs the decision owner's own material."
        )


def build_workspace(
    *,
    case: Case,
    role_config: RoleConfig,
    role: str,
    task: WorkspaceTask,
    projected_inputs: list[ProjectedArtifact],
    skill_packs: list[SkillPack] | None = None,
) -> WorkspaceLayout:
    assert_private_evidence_allowed(role, projected_inputs)

    workspace_path = _workspace_path(case, role=role, task_id=task.task_id)
    if workspace_path.exists():
        shutil.rmtree(workspace_path)
    (workspace_path / "inputs").mkdir(parents=True, exist_ok=True)
    (workspace_path / "outputs").mkdir(parents=True, exist_ok=True)
    (workspace_path / ".cursor").mkdir(parents=True, exist_ok=True)

    role_md_text = role_config.role_md_path.read_text(encoding="utf-8")
    applicable = packs_for_role(skill_packs or [], role_config.role.value)
    (workspace_path / "AGENTS.md").write_text(
        role_md_text + render_pack_section(applicable), encoding="utf-8"
    )

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
    if task.mode:
        task_payload["mode"] = task.mode
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
