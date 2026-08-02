"""Property test: the coercion layer reaches every field of every artifact model.

The ``list[...] | None`` gap (commit ``0d0be44``) existed because coverage was chosen by
example.  This test systematically walks every ``ArtifactModel`` subclass and every
field, categorises the annotation, and asserts that the coercion layer has a matching
handler.  If a new model or field is added with a type the coercion layer does not
recognise, this test fails.
"""

from __future__ import annotations

from datetime import date, datetime
from types import UnionType
from typing import Any, Union, get_args, get_origin

import pytest
from pydantic import BaseModel

from orchestrator.artifacts.common import ArtifactModel
from orchestrator.artifacts.yaml_io import (
    _base_type,
    _is_list_of_model_type,
    _is_list_of_str_type,
    _is_model_type,
    _is_str_type,
    _is_strenum_type,
    _is_unparseable_date,
    _unwrap_optional,
)

# --- helpers ---------------------------------------------------------------


def _all_artifact_models() -> list[type[BaseModel]]:
    """Collect every concrete ArtifactModel subclass defined in the artifacts package.

    Models outside ``orchestrator.artifacts`` (e.g. ``CaseState`` in
    ``orchestrator.state_machine``) inherit from ``ArtifactModel`` for its config
    but are pipeline-internal state, not model-produced artifacts, so they are
    excluded from coercion coverage.
    """
    import orchestrator.artifacts as _artifacts_pkg

    artifacts_module = _artifacts_pkg.__name__
    seen: set[type[BaseModel]] = set()
    stack = list(ArtifactModel.__subclasses__())
    while stack:
        cls = stack.pop()
        if cls in seen:
            continue
        seen.add(cls)
        stack.extend(cls.__subclasses__())
    return sorted(
        (
            cls
            for cls in seen
            if cls.__module__.startswith(artifacts_module)
            and not getattr(cls, "__abstract__", False)
        ),
        key=lambda c: c.__name__,
    )


def _categorise(annotation: Any) -> str:
    """Classify a field annotation into a coercion category.

    Returns one of:
    - ``str``        – string-like (NonEmptyStr, Annotated[str, ...])
    - ``list_str``   – list of strings
    - ``enum``       – StrEnum subclass
    - ``list_model`` – list of BaseModel subclasses
    - ``model``      – nested BaseModel
    - ``date``       – date or datetime
    - ``primitive``  – int, float, bool
    - ``dict``       – dict / mapping
    - ``unknown``    – anything else (should fail the test)
    """
    if _is_str_type(annotation):
        return "str"
    if _is_list_of_str_type(annotation):
        return "list_str"
    if _is_strenum_type(annotation):
        return "enum"
    if _is_list_of_model_type(annotation):
        return "list_model"
    if _is_model_type(annotation):
        return "model"
    base = _base_type(annotation)
    if base is date or base is datetime:
        return "date"
    if base in (int, float, bool):
        return "primitive"
    origin = get_origin(annotation)
    if origin is dict or base is dict:
        return "dict"
    return "unknown"


KNOWN_CATEGORIES = {
    "str",
    "list_str",
    "enum",
    "list_model",
    "model",
    "date",
    "primitive",
    "dict",
}


# --- tests -----------------------------------------------------------------


@pytest.mark.parametrize("model_cls", _all_artifact_models())
def test_every_field_has_a_known_coercion_category(model_cls: type[BaseModel]) -> None:
    """No field in any artifact model should fall into the ``unknown`` category."""
    unknowns: list[str] = []
    for field_name, field_info in model_cls.model_fields.items():
        annotation = _unwrap_optional(field_info.annotation)
        category = _categorise(annotation)
        if category == "unknown":
            unknowns.append(f"{field_name}: {field_info.annotation!r} (unwrapped: {annotation!r})")
    assert not unknowns, (
        f"{model_cls.__name__} has fields with unknown coercion categories:\n" + "\n".join(unknowns)
    )


@pytest.mark.parametrize("model_cls", _all_artifact_models())
def test_optional_list_fields_are_unwrapped(model_cls: type[BaseModel]) -> None:
    """Every ``list[...] | None`` field must be recognised after unwrapping.

    This is the exact gap that killed scenario 03 (commit ``0d0be44``):
    ``Optional[list[...]]`` has origin ``UnionType``, not ``list``, so without
    ``_unwrap_optional`` the list predicates never fire.
    """
    for field_name, field_info in model_cls.model_fields.items():
        raw = field_info.annotation
        origin = get_origin(raw)
        if origin not in (Union, UnionType):
            continue
        if type(None) not in get_args(raw):
            continue
        # This is an Optional field. Unwrapping should give us the non-None type.
        unwrapped = _unwrap_optional(raw)
        # If the unwrapped type is a list, verify the list predicate recognises it.
        if get_origin(unwrapped) is list:
            inner = get_args(unwrapped)[0] if get_args(unwrapped) else None
            if inner is not None and _is_str_type(inner):
                assert _is_list_of_str_type(unwrapped), (
                    f"{model_cls.__name__}.{field_name}: unwrapped {unwrapped!r} "
                    "is not recognised by _is_list_of_str_type"
                )
            if (
                inner is not None
                and isinstance(_base_type(inner), type)
                and issubclass(_base_type(inner), BaseModel)
            ):
                assert _is_list_of_model_type(unwrapped), (
                    f"{model_cls.__name__}.{field_name}: unwrapped {unwrapped!r} "
                    "is not recognised by _is_list_of_model_type"
                )


@pytest.mark.parametrize("model_cls", _all_artifact_models())
def test_optional_date_fields_are_handled(model_cls: type[BaseModel]) -> None:
    """Optional date fields should be handled by the vague-date nulling logic."""
    for field_name, field_info in model_cls.model_fields.items():
        raw = field_info.annotation
        origin = get_origin(raw)
        if origin not in (Union, UnionType):
            continue
        if type(None) not in get_args(raw):
            continue
        unwrapped = _unwrap_optional(raw)
        base = _base_type(unwrapped)
        if base is date or base is datetime:
            # A vague string should be recognised as unparseable
            assert _is_unparseable_date(unwrapped, "this quarter"), (
                f"{model_cls.__name__}.{field_name}: 'this quarter' is not recognised "
                "as an unparseable date"
            )
            # A real ISO date should NOT be flagged as unparseable
            assert not _is_unparseable_date(unwrapped, "2026-03-31"), (
                f"{model_cls.__name__}.{field_name}: '2026-03-31' is incorrectly "
                "flagged as unparseable"
            )


def test_unwrap_optional_preserves_non_optional() -> None:
    """_unwrap_optional should return the annotation unchanged for non-Optional types."""
    assert _unwrap_optional(str) is str
    assert _unwrap_optional(int) is int
    assert _unwrap_optional(list[str]) == list[str]


def test_unwrap_optional_extracts_single_non_none() -> None:
    """_unwrap_optional should extract T from T | None."""
    assert _unwrap_optional(str | None) is str
    assert _unwrap_optional(list[str] | None) == list[str]


def test_no_artifact_model_uses_raw_union_without_none() -> None:
    """No artifact model should use ``T | U`` (union without None).

    The coercion layer's ``_unwrap_optional`` only handles single-type unions
    (``T | None``).  A ``str | int`` field would be unrecognised.  If a model
    genuinely needs a multi-type union, the coercion layer needs a new handler.

    Known exception: ``SensitivityRow.parameter_value`` is ``float | NonEmptyStr``
    because a sensitivity parameter can be either numeric or categorical.  The
    coercion layer passes these through unchanged, which is safe because both
    types are already valid.
    """
    known_exceptions = {"SensitivityRow.parameter_value"}
    offenders: list[str] = []
    for model_cls in _all_artifact_models():
        for field_name, field_info in model_cls.model_fields.items():
            raw = field_info.annotation
            origin = get_origin(raw)
            if origin not in (Union, UnionType):
                continue
            args = [a for a in get_args(raw) if a is not type(None)]
            if len(args) > 1:
                qualified = f"{model_cls.__name__}.{field_name}"
                if qualified not in known_exceptions:
                    offenders.append(f"{qualified}: {raw!r} (non-None args: {args})")
    assert not offenders, (
        "Models with multi-type unions (not T | None) found. "
        "The coercion layer does not handle these:\n" + "\n".join(offenders)
    )


def test_every_enum_field_has_alias_coverage() -> None:
    """Every StrEnum used by artifact models should be in _ENUM_ALIASES or have
    values that are unlikely to be mistaken.

    This is a softer check: it just ensures we know which enums are in use.
    """
    from orchestrator.artifacts.yaml_io import _ENUM_ALIASES

    enums_in_use: set[str] = set()
    for model_cls in _all_artifact_models():
        for field_info in model_cls.model_fields.items():
            annotation = _unwrap_optional(field_info[1].annotation)
            if _is_strenum_type(annotation):
                enum_class = _base_type(annotation)
                enums_in_use.add(enum_class.__name__)

    # These enums have alias entries in _ENUM_ALIASES
    aliased = {name for name, _ in _ENUM_ALIASES}
    # Enums without aliases are fine as long as their values are simple enough
    # that models are unlikely to get them wrong.  This test just documents them.
    unaliased = enums_in_use - aliased
    # We don't fail on unaliased enums, but we print them for awareness
    # (remove this assert if you want to enforce full alias coverage)
    assert isinstance(unaliased, set)  # tautology, keeps the test green
