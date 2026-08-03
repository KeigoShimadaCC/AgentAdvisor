"""Per-backend model assignment.

Role configs under `cursor/roles/` name Cursor CLI models, which do not exist in
another harness's catalogue. Rather than duplicate every role file per backend,
a backend that is not Cursor declares its own assignment in
`backends/<backend>/models.yaml`: a model pair per tier, plus per-role overrides
for the roles where the specific model matters (notably the Director/Challenger
family split the diversity guard enforces).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


@dataclass(frozen=True, slots=True)
class ModelPair:
    default_model: str
    escalation_model: str


class BackendModelsError(RuntimeError):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _models_path(backend: str) -> Path:
    return _repo_root() / "backends" / backend / "models.yaml"


def _as_model_pair(payload: Any, where: str) -> ModelPair:
    if not isinstance(payload, dict):
        raise BackendModelsError(f"{where} must be a mapping.")
    default_model = payload.get("default_model")
    escalation_model = payload.get("escalation_model")
    for key, value in (("default_model", default_model), ("escalation_model", escalation_model)):
        if not isinstance(value, str) or not value.strip():
            raise BackendModelsError(f"{where}.{key} must be a non-empty string.")
    assert isinstance(default_model, str) and isinstance(escalation_model, str)
    return ModelPair(default_model=default_model.strip(), escalation_model=escalation_model.strip())


@dataclass(frozen=True, slots=True)
class BackendModels:
    tiers: dict[str, ModelPair]
    roles: dict[str, ModelPair]


@lru_cache(maxsize=8)
def load_backend_models(backend: str) -> BackendModels | None:
    """Model table for a backend, or None when the backend uses the role configs."""

    path = _models_path(backend)
    if not path.exists():
        return None

    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise BackendModelsError(f"Backend model table must be a mapping: {path}")

    raw_tiers = loaded.get("tiers")
    if not isinstance(raw_tiers, dict) or not raw_tiers:
        raise BackendModelsError(f"Backend model table needs a non-empty 'tiers' mapping: {path}")
    tiers = {
        str(tier): _as_model_pair(pair, f"{path}: tiers.{tier}") for tier, pair in raw_tiers.items()
    }

    raw_roles = loaded.get("roles") or {}
    if not isinstance(raw_roles, dict):
        raise BackendModelsError(f"Backend model table 'roles' must be a mapping: {path}")
    roles = {
        str(role): _as_model_pair(pair, f"{path}: roles.{role}") for role, pair in raw_roles.items()
    }

    return BackendModels(tiers=tiers, roles=roles)


def resolve_models(
    *,
    backend: str,
    role_stem: str,
    tier: str,
    fallback: ModelPair,
) -> ModelPair:
    """Models for one role on one backend, falling back to the role config's own pair."""

    table = load_backend_models(backend)
    if table is None:
        return fallback

    override = table.roles.get(role_stem)
    if override is not None:
        return override

    by_tier = table.tiers.get(tier)
    if by_tier is None:
        raise BackendModelsError(
            f"Backend '{backend}' has no models for tier '{tier}' "
            f"and no override for role '{role_stem}'."
        )
    return by_tier
