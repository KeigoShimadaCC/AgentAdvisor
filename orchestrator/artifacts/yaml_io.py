from __future__ import annotations

from pathlib import Path
from typing import Any, cast, get_args, get_origin

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


def _flatten_to_string(value: Any) -> str | None:
    """Try to coerce a value into a non-empty string."""
    if isinstance(value, str):
        return value if value.strip() else None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, dict):
        for key in ("headline", "title", "summary", "action", "text", "description", "detail"):
            if key in value and isinstance(value[key], str):
                return value[key].strip() or None
        parts = [str(v) for v in value.values() if isinstance(v, (str, int, float))]
        joined = " ".join(parts).strip()
        return joined or None
    if isinstance(value, list):
        parts = [str(item) for item in value if isinstance(item, (str, int, float))]
        joined = " ".join(parts).strip()
        return joined or None
    return None


def _base_type(annotation: Any) -> Any:
    """Extract the underlying type from Annotated[T, ...]."""
    origin = get_origin(annotation)
    if origin is not None:
        args = get_args(annotation)
        if args:
            return args[0]
    return annotation


def _is_str_type(annotation: Any) -> bool:
    """Check if annotation expects a string type (including Annotated[str, ...])."""
    base = _base_type(annotation)
    return base is str or (isinstance(base, type) and issubclass(base, str))


def _is_list_of_str_type(annotation: Any) -> bool:
    """Check if annotation expects a list of strings (including list[NonEmptyStr])."""
    origin = get_origin(annotation)
    if origin is list:
        args = get_args(annotation)
        if args:
            return _is_str_type(args[0])
    return False


def coerce_payload_for_model(model_type: type[BaseModel], payload: Any) -> Any:
    """Coerce common model formatting mistakes before validation.

    Handles:
    - Nested objects/lists where strings expected (flattens to string)
    - List items that are dicts where strings expected (flattens each item)
    - Numbers where strings expected (converts to string)

    Returns the coerced payload (may be unchanged if no coercion needed).
    """
    if not isinstance(payload, dict):
        return payload

    coerced = dict(payload)
    changed = False

    for field_name, field_info in model_type.model_fields.items():
        if field_name not in coerced:
            continue

        value = coerced[field_name]
        annotation = field_info.annotation

        if _is_str_type(annotation) and not isinstance(value, str):
            flattened = _flatten_to_string(value)
            if flattened is not None:
                coerced[field_name] = flattened
                changed = True

        elif _is_list_of_str_type(annotation) and isinstance(value, list):
            new_items: list[Any] = []
            any_coerced = False
            for item in value:
                if isinstance(item, str):
                    new_items.append(item)
                else:
                    flattened = _flatten_to_string(item)
                    if flattened is not None:
                        new_items.append(flattened)
                        any_coerced = True
                    else:
                        new_items.append(item)
            if any_coerced:
                coerced[field_name] = new_items
                changed = True

    return coerced if changed else payload


# Defaults for commonly-missing required fields whose types allow a
# conservative fallback.  String/list fields cannot be defaulted because
# they carry decision-specific content.
_DEFAULT_FILLERS: dict[str, dict[str, Any]] = {
    "model_stability": {
        "share_of_sensitivity_runs_supporting_recommendation": 0.0,
        "runs_total": 1,
        "runs_supporting": 0,
    },
    "evidence_confidence": {
        "value": 0.5,
        "basis": "Not independently assessed",
    },
    "recommendation_confidence": {
        "value": 0.5,
        "basis": "Not independently assessed",
    },
}


def fill_missing_required_defaults(model_type: type[BaseModel], payload: Any) -> Any:
    """Fill in missing required fields with conservative defaults.

    Only fills fields that have a known safe default (model_stability,
    evidence_confidence, recommendation_confidence).  String and list
    fields are left untouched because they carry decision-specific content.

    Returns the filled payload (may be unchanged if nothing was missing).
    """
    if not isinstance(payload, dict):
        return payload

    filled = dict(payload)
    changed = False

    for field_name in model_type.model_fields:
        if field_name in filled:
            continue
        if field_name in _DEFAULT_FILLERS:
            filled[field_name] = dict(_DEFAULT_FILLERS[field_name])
            changed = True

    return filled if changed else payload
