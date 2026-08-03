from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import TaskRole
from orchestrator.backend_models import ModelPair, resolve_models

ModelTier = Literal["low", "medium", "high"]
CURSOR_BACKEND = "cursor"


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
    variant: str | None = None

    @property
    def stem(self) -> str:
        return self.role.value if self.variant is None else f"{self.role.value}-{self.variant}"


class RoleConfigError(RuntimeError):
    pass


def models_for(config: RoleConfig, backend: str = CURSOR_BACKEND) -> ModelPair:
    """The default/escalation pair this role uses on the given backend."""

    return resolve_models(
        backend=backend,
        role_stem=config.stem,
        tier=config.model_tier,
        fallback=ModelPair(
            default_model=config.default_model,
            escalation_model=config.escalation_model,
        ),
    )


_VALID_TIERS: frozenset[str] = frozenset({"low", "medium", "high"})
_KNOWN_FAMILY_PREFIXES: tuple[tuple[str, str], ...] = (
    ("claude-", "anthropic"),
    ("gpt-", "openai"),
    ("cursor-grok-", "xai"),
    ("grok-", "xai"),
    ("composer-", "cursor-composer"),
    ("kimi-", "moonshot"),
    ("gemini-", "google"),
    ("glm-", "zhipu"),
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _role_config_path(role: TaskRole, variant: str | None = None) -> Path:
    """Config path for a role, or for a named variant of it.

    A variant is a distinct instruction set for the same underlying role, such as
    the Director's framing pass, which needs its own model tier and projection
    while still being the Director.
    """
    stem = role.value if variant is None else f"{role.value}-{variant}"
    return _repo_root() / "cursor" / "roles" / f"{stem}.yaml"


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


def family(model_id: str, *, canonical: bool = False) -> str:
    """Return model family for a model identifier.

    Unknown models raise RoleConfigError instead of falling back to a guessed
    prefix. Silent fallback would let a same-family Director/Challenger pair
    slip through startup validation when model names churn.
    """

    model = model_id.strip().lower()
    if not model:
        raise RoleConfigError("Model id must be a non-empty string.")

    for prefix, mapped_family in _KNOWN_FAMILY_PREFIXES:
        if model.startswith(prefix):
            if canonical:
                return mapped_family
            # Backward-compatible alias used in existing tests and callers.
            if mapped_family in {"cursor-composer", "xai"}:
                return "cursor"
            return mapped_family

    raise RoleConfigError(
        "Unknown model family for model "
        f"'{model_id}'. Add it to _KNOWN_FAMILY_PREFIXES in orchestrator/roles_config.py."
    )


def validate_director_challenger_family_diversity(
    *,
    director_variant: str | None = None,
    challenger_variant: str | None = None,
    backend: str = CURSOR_BACKEND,
) -> None:
    """Startup guard: Director and Challenger must use different model families."""

    director_model = models_for(
        load_role_config(TaskRole.DIRECTOR, director_variant), backend
    ).default_model
    challenger_model = models_for(
        load_role_config(TaskRole.CHALLENGER, challenger_variant), backend
    ).default_model
    director_family = family(director_model, canonical=True)
    challenger_family = family(challenger_model, canonical=True)

    if director_family == challenger_family:
        raise RoleConfigError(
            "Director/Challenger family diversity guard failed: "
            f"director={director_model} ({director_family}), "
            f"challenger={challenger_model} ({challenger_family}). "
            "Configure different model families."
        )


def load_role_config(role: TaskRole | str, variant: str | None = None) -> RoleConfig:
    role_enum = _coerce_role(role)
    config_path = _role_config_path(role_enum, variant)
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
        variant=variant,
        role_md_path=role_md_path,
        default_model=default_model,
        escalation_model=escalation_model,
        read_only=read_only,
        permission_profile=PermissionProfile(allow_shell=allow_shell),
        projection_include=projection_include,
        output_artifact_type=output_artifact_type,
        model_tier=model_tier,
    )
