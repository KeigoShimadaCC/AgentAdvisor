"""Presentation lexicon — translates raw audit events into human-readable progress events.

The lexicon data lives in ``lexicon_data.yaml`` so UI copy can be iterated without
touching Python (SPEC-033).  This module loads it once and exposes
:func:`translate_event`, which fills a template from the event payload and
returns a structured progress event.

A built-in ``technical`` flag marks Method-only events (retries, coercion
notices, bookkeeping).  Unknown event types are flagged ``technical: true``
and rendered with a generic message — the raw payload is delivered separately
so the Method room can show it without leaking raw JSON into narration.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

__all__ = ["LexiconEntry", "TranslatedEvent", "translate_event", "load_lexicon"]

_LEXICON_PATH = Path(__file__).resolve().parent / "lexicon_data.yaml"

# Built-in context variables always available to templates, in addition to
# payload keys.
_BUILTIN_VARS: tuple[str, ...] = ("actor", "event_type", "ts")


class LexiconEntry(BaseModel):
    """One lexicon row."""

    model_config = {"extra": "forbid"}

    template: str
    technical: bool = False


# Fallback entry used for unknown event types.
_UNKNOWN_ENTRY = LexiconEntry(
    template="Event recorded ({event_type})",
    technical=True,
)


class TranslatedEvent(BaseModel):
    """The structured progress event delivered to the UI."""

    event_type: str
    message: str
    technical: bool
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    line_cursor: int = 0
    ts: str | None = None
    actor: str | None = None


@lru_cache(maxsize=1)
def load_lexicon() -> dict[str, LexiconEntry]:
    """Load and cache the lexicon YAML."""
    data = yaml.safe_load(_LEXICON_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Lexicon YAML at {_LEXICON_PATH} is not a mapping.")
    return {str(key): LexiconEntry.model_validate(value) for key, value in data.items()}


# SPEC-056 follow-up: slots whose values are enum identifiers, not prose.
#
# The templates substitute payload values straight in, so "Completed stage:
# {stage}" rendered "Completed stage: pre_mortem" in the Method room's audit
# log for the whole of phase 9. The terminology guard did not catch it because
# it sampled the DOM before the log had loaded.
#
# Only the slot values are humanised, never the event type or the cursor: the
# Method room is the machinery view and an auditor still needs to line its rows
# up against `audit.jsonl`.
_IDENTIFIER_SLOTS: frozenset[str] = frozenset(
    {"stage", "role", "actor", "outcome", "to_stage", "from_stage"}
)


def _humanise(value: Any) -> Any:
    """Turn a snake_case identifier into words, leaving everything else alone."""
    if not isinstance(value, str):
        return value
    if not value or not value.replace("_", "").isalnum():
        return value
    if "_" not in value:
        return value
    return value.replace("_", " ")


def _format_template(template: str, event: dict[str, Any]) -> str:
    """Fill ``template`` from event payload + built-in vars.

    Missing slots are replaced with "—" so templates never raise on sparse
    payloads.
    """
    raw_payload = event.get("payload")
    payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    context: dict[str, Any] = {
        key: _humanise(value) if key in _IDENTIFIER_SLOTS else value
        for key, value in payload.items()
    }
    for var in _BUILTIN_VARS:
        if var not in context:
            raw = event.get(var)
            context[var] = _humanise(raw) if var in _IDENTIFIER_SLOTS else raw
    try:
        # str.format_map with a defaultdict-like to substitute "—" for misses.
        return template.format_map(_DefaultDict(context))
    except (KeyError, IndexError, ValueError):
        return template


class _DefaultDict(dict[str, Any]):
    """A dict that returns "—" for missing keys during str.format_map."""

    def __missing__(self, key: str) -> str:  # noqa: D401
        return "—"


def translate_event(event: dict[str, Any], line_cursor: int = 0) -> TranslatedEvent:
    """Translate one raw audit event (parsed JSON) into a progress event.

    Parameters
    ----------
    event:
        Parsed audit line (a dict with at least ``event_type`` and ``payload``).
    line_cursor:
        The 1-based audit line number this event came from.
    """
    event_type = str(event.get("event_type") or "unknown")
    lexicon = load_lexicon()
    entry = lexicon.get(event_type, _UNKNOWN_ENTRY)
    message = _format_template(entry.template, event)
    raw = event.get("payload")
    raw_payload: dict[str, Any] = raw if isinstance(raw, dict) else {}

    return TranslatedEvent(
        event_type=event_type,
        message=message,
        technical=entry.technical,
        raw_payload=raw_payload,
        line_cursor=line_cursor,
        ts=event.get("ts"),
        actor=event.get("actor"),
    )
