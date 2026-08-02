"""Validate the YAML examples inside role definitions against the real schemas.

Role markdown is a product artifact the models copy from literally. Three separate
live failures came from examples that described fields the schema does not have:
director-b invented `alternatives_considered`, the analyst taught `method: base_rate`
and an adjustment shape of `{delta, reason, evidence_id}`. None of it was visible to
lint, mypy or any unit test, because the defect lived in prose.

An example block opts into this check by carrying a top-level `schema_version`, which
is what a complete artifact has and a partial snippet does not.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import BaseModel, ValidationError

from orchestrator.artifacts.schema_export import MODEL_EXPORTS

REPO_ROOT = Path(__file__).resolve().parents[1]
ROLES_DIR = REPO_ROOT / "cursor" / "roles"
FENCED_YAML = re.compile(r"```ya?ml\n(.*?)```", re.DOTALL)


def _role_names() -> list[str]:
    return sorted(path.stem for path in ROLES_DIR.glob("*.yaml"))


def _role_config(role_name: str) -> dict[str, Any]:
    """Read the pair off disk rather than through the loader, which cannot address
    variants such as `director-b` by filename."""
    loaded = yaml.safe_load((ROLES_DIR / f"{role_name}.yaml").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{role_name}.yaml is not a mapping"
    return loaded


def _role_markdown(role_name: str) -> str:
    config = _role_config(role_name)
    md_path = REPO_ROOT / str(config["role_md_path"])
    assert md_path.exists(), f"{role_name}.yaml points at a missing {md_path}"
    return md_path.read_text(encoding="utf-8")


def _complete_examples(markdown: str) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for block in FENCED_YAML.findall(markdown):
        try:
            parsed = yaml.safe_load(block)
        except yaml.YAMLError as exc:
            raise AssertionError(f"Role markdown contains unparseable YAML: {exc}") from exc
        if isinstance(parsed, dict) and "schema_version" in parsed:
            examples.append(parsed)
    return examples


@pytest.mark.parametrize("role_name", _role_names())
def test_role_examples_validate_against_the_declared_schema(role_name: str) -> None:
    artifact_type = _role_config(role_name)["output_artifact_type"]
    model_type: type[BaseModel] | None = MODEL_EXPORTS.get(artifact_type)
    assert model_type is not None, (
        f"{role_name}.yaml declares output_artifact_type "
        f"{artifact_type!r}, which is not an exported artifact model"
    )

    for index, example in enumerate(_complete_examples(_role_markdown(role_name))):
        try:
            model_type.model_validate(example)
        except ValidationError as exc:
            raise AssertionError(
                f"{role_name}.md example {index} does not validate as "
                f"{model_type.__name__}. The role would be teaching the model an "
                f"output shape the orchestrator rejects.\n{exc}"
            ) from exc


def test_the_roles_that_hand_models_a_worked_example_are_actually_covered() -> None:
    """Guards the check itself: a convention nothing satisfies would pass silently."""
    covered = {
        role_name for role_name in _role_names() if _complete_examples(_role_markdown(role_name))
    }

    assert {
        "analyst",
        "challenger",
        "intake",
        "researcher",
        "reviewer",
        "synthesizer",
    } <= covered


def test_every_role_declares_an_artifact_the_orchestrator_knows() -> None:
    for role_name in _role_names():
        artifact_type = _role_config(role_name)["output_artifact_type"]
        assert artifact_type in MODEL_EXPORTS, f"{role_name} declares {artifact_type!r}"
