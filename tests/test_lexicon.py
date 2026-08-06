"""Lexicon coverage: every audit event the engine emits must be narratable."""

from __future__ import annotations


def test_every_emitted_audit_event_has_a_lexicon_entry() -> None:
    """An unnarrated event renders through the unknown-event fallback, which reads as
    noise to the user. Found five pre-existing gaps during the Phase 8 audit; this
    keeps the next one from shipping."""
    import re
    from pathlib import Path

    import yaml

    repo_root = Path(__file__).resolve().parents[1]
    lexicon = yaml.safe_load(
        (repo_root / "orchestrator" / "service" / "lexicon_data.yaml").read_text(encoding="utf-8")
    )

    emitted: set[str] = set()
    for path in (repo_root / "orchestrator").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        emitted |= set(re.findall(r'_audit\(\s*case,\s*"([a-z_]+)"', source))
        emitted |= set(re.findall(r'event_type="([a-z_]+)"', source))

    missing = sorted(event for event in emitted if event not in lexicon)
    assert not missing, f"audit events with no lexicon narration: {missing}"
