from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import TaskRole

ModelTier = Literal["low", "medium", "high"]


@dataclass(frozen=True, slots=True)
class PermissionProfile:
    allow_shell: bool


@dataclass(frozen=True, slots=True)
class RoleConfig:
    role: TaskRole
    role_md_path: Path
    default_model: str
    escalation_model: str
    read_only: bool
    permission_profile: PermissionProfile
    projection_include: tuple[str, ...]
    output_artifact_type: str
    model_tier: ModelTier


class RoleConfigError(RuntimeError):
    pass


_VALID_TIERS: frozenset[str] = frozenset({"low", "medium", "high"})


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _role_config_path(role: TaskRole) -> Path:
    return _repo_root() / "cursor" / "roles" / f"{role.value}.yaml"


def _as_str(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RoleConfigError(f"Role config key '{key}' must be a non-empty string.")
    return value.strip()


def _as_bool(config: dict[str, Any], key: str) -> bool:
    value = config.get(key)
    if not isinstance(value, bool):
        raise RoleConfigError(f"Role config key '{key}' must be a boolean.")
    return value


def _as_string_list(config: dict[str, Any], key: str) -> tuple[str, ...]:
    value = config.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise RoleConfigError(f"Role config key '{key}' must be a list of non-empty strings.")
    return tuple(value)


def _coerce_role(role: TaskRole | str) -> TaskRole:
    if isinstance(role, TaskRole):
        return role
    try:
        return TaskRole(role)
    except ValueError as exc:
        raise RoleConfigError(f"Unknown role '{role}'.") from exc


def family(model_id: str) -> str:
    model = model_id.strip().lower()
    if model.startswith("claude-"):
        return "anthropic"
    if model.startswith("gpt-"):
        return "openai"
    if model.startswith("composer-") or model.startswith("cursor-"):
        return "cursor"
    if model.startswith("kimi-"):
        return "moonshot"
    if "-" in model:
        return model.split("-", 1)[0]
    return model


def load_role_config(role: TaskRole | str) -> RoleConfig:
    role_enum = _coerce_role(role)
    config_path = _role_config_path(role_enum)
    if not config_path.exists():
        raise RoleConfigError(f"Role config file not found: {config_path}")

    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RoleConfigError(f"Role config must be a mapping: {config_path}")
    payload: dict[str, Any] = loaded

    role_md_path_raw = _as_str(payload, "role_md_path")
    role_md_path = (_repo_root() / role_md_path_raw).resolve()
    if not role_md_path.exists():
        raise RoleConfigError(
            f"Role instruction file is missing for '{role_enum.value}': {role_md_path}"
        )

    default_model = _as_str(payload, "default_model")
    escalation_model = _as_str(payload, "escalation_model")
    read_only = _as_bool(payload, "read_only")
    allow_shell = _as_bool(payload, "allow_shell")
    projection_include = _as_string_list(payload, "projection_include")
    output_artifact_type = _as_str(payload, "output_artifact_type")
    model_tier_raw = _as_str(payload, "model_tier")
    if model_tier_raw not in _VALID_TIERS:
        raise RoleConfigError(
            f"Role config key 'model_tier' must be one of {sorted(_VALID_TIERS)}."
        )
    model_tier = cast(ModelTier, model_tier_raw)

    return RoleConfig(
        role=role_enum,
        role_md_path=role_md_path,
        default_model=default_model,
        escalation_model=escalation_model,
        read_only=read_only,
        permission_profile=PermissionProfile(allow_shell=allow_shell),
        projection_include=projection_include,
        output_artifact_type=output_artifact_type,
        model_tier=model_tier,
    )
