"""Every audit event the orchestrator emits must have a lexicon entry.

`translate_event` falls back to `_UNKNOWN_ENTRY`, which renders "Event recorded
(<type>)" and flags the event `technical: true` — so the UI hides it behind the
Method-room filter. That fallback is correct for genuinely unknown input, but it
also means a *newly added* event type degrades silently: no error, no test
failure, just an event the user never sees. Four refusal/failure events had
drifted this way, which is the same defect class as the role-md/schema drift
guarded by `test_role_contracts.py`.

This walks the orchestrator source for emitted `event_type=` literals and holds
the lexicon to them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from orchestrator.service.lexicon import load_lexicon

ORCHESTRATOR_ROOT = Path(__file__).resolve().parent.parent / "orchestrator"

# Events that are emitted with a computed (non-literal) type, or that belong to
# a different vocabulary than the audit log. Empty today; kept as the documented
# escape hatch so a future exception is stated rather than silently grepped out.
NOT_USER_FACING: frozenset[str] = frozenset()

# Events whose whole purpose is to disclose that the run did less than it could
# have. These must reach the default progress feed, not just the Method room.
DISCLOSURE_EVENTS = frozenset(
    {
        "task_failed",
        "task_budget_refused",
        "task_marginal_value_refused",
        "tasks_cancelled",
    }
)


def _emitted_event_types() -> set[str]:
    """Collect every literal passed as `event_type=` anywhere in the orchestrator.

    Parsed rather than grepped so a string that merely *mentions* an event type
    (a docstring, a comparison) is not mistaken for an emission.
    """
    found: set[str] = set()
    for path in sorted(ORCHESTRATOR_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg != "event_type":
                    continue
                if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                    found.add(keyword.value.value)
    return found


def test_source_scan_finds_events() -> None:
    """Guard the guard: an AST change that silently finds nothing must fail here."""
    emitted = _emitted_event_types()
    assert len(emitted) > 10, f"only found {len(emitted)} event types — the scan is broken"


def test_every_emitted_event_type_has_a_lexicon_entry() -> None:
    lexicon = load_lexicon()
    missing = sorted(_emitted_event_types() - set(lexicon) - NOT_USER_FACING)
    assert not missing, (
        "audit event types with no lexicon entry, so they render as "
        f"'Event recorded (<type>)' and are hidden as technical: {missing}"
    )


@pytest.mark.parametrize("event_type", sorted(DISCLOSURE_EVENTS))
def test_disclosure_events_are_not_marked_technical(event_type: str) -> None:
    """A refused, failed or cancelled task has to be visible while the run happens."""
    lexicon = load_lexicon()
    assert event_type in lexicon, f"{event_type} has no lexicon entry"
    assert not lexicon[event_type].technical, (
        f"{event_type} is marked technical, so the progress feed hides it — "
        "the user would not learn the run investigated less than it planned to"
    )


def test_disclosure_events_are_actually_emitted() -> None:
    """If one of these is renamed, this list must be updated rather than rot."""
    emitted = _emitted_event_types()
    stale = sorted(DISCLOSURE_EVENTS - emitted)
    assert not stale, f"listed as disclosure events but no longer emitted: {stale}"
