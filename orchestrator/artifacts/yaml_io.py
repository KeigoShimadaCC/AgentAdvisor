from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel


class _NoAliasSafeDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: object) -> bool:  # noqa: ANN401
        return True


def load_model_from_yaml_text[ModelT: BaseModel](
    model_type: type[ModelT], yaml_text: str
) -> ModelT:
    loaded = yaml.safe_load(yaml_text)
    return model_type.model_validate(loaded)


def load_model_from_yaml_path[ModelT: BaseModel](
    model_type: type[ModelT], path: str | Path
) -> ModelT:
    yaml_text = Path(path).read_text(encoding="utf-8")
    return load_model_from_yaml_text(model_type, yaml_text)


def dump_model_to_yaml_text(model: BaseModel) -> str:
    payload = model.model_dump(mode="json")
    dumped = yaml.dump(
        payload,
        Dumper=_NoAliasSafeDumper,
        sort_keys=True,
        default_flow_style=False,
        allow_unicode=True,
    )
    if not dumped.endswith("\n"):
        dumped = f"{dumped}\n"
    return cast(str, dumped)


def dump_model_to_yaml_path(model: BaseModel, path: str | Path) -> None:
    yaml_text = dump_model_to_yaml_text(model)
    Path(path).write_text(yaml_text, encoding="utf-8")
