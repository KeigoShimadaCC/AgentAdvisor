"""SPEC-018's live toy-case end-to-end run.

The stub suite (``tests/test_pipeline_stub.py``) proves the wiring deterministically;
this test proves the wired pipeline survives contact with a real agent backend on the
smallest honest case the spec describes: a two-alternative purchase-timing decision, a
tiny budget (<=15 invocations), and every role pinned to a cheap model via a role-config
override. Deselected by default; run deliberately with:

    uv run pytest -m live_slow tests/test_pipeline_live.py -q

The model pins keep the two startup family guards satisfiable on either backend: the
Director bucket and the adversary bucket (Challenger, independent Reviewer-B) must never
share a model family, so each backend names its cheapest model from two distinct
families. Dual track is off: a second Director track plus reconciliation would not fit
the toy budget, and the dual-track path has its own coverage in ``tests/test_tracks.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestrator.artifacts import FinalRecommendation
from orchestrator.backend import make_backend
from orchestrator.backend_models import ModelPair
from orchestrator.case_store import create_case
from orchestrator.pipeline import SMALL_BUDGET, run
from orchestrator.state_machine import CaseStage

pytestmark = pytest.mark.live_slow

TOY_PROMPT = (
    "I need to replace my work laptop. Should I buy the $1,200 model I have already "
    "picked out this week, or wait up to three months for the refreshed model the "
    "manufacturer is expected to announce? My current laptop still works, and I care "
    "mostly about value for money."
)

# Role stems (config stem, i.e. "<role>" or "<role>-<variant>") whose models must not
# share a family across the two buckets, per the startup guards in roles_config.py.
_DIRECTOR_BUCKET = frozenset({"director", "director-framing", "director-b", "synthesizer"})
_ADVERSARY_BUCKET = frozenset({"challenger", "reviewer-b"})

# (director bucket, adversary bucket, everything else) — the cheapest model per family
# each backend catalogue offers.
_CHEAP_PINS: dict[str, tuple[str, str, str]] = {
    "cursor": ("cursor-grok-4.5-low", "composer-2.5", "composer-2.5"),
    "droid": ("claude-sonnet-5", "gpt-5.4", "claude-haiku-4-5-20251001"),
}


def test_live_toy_case_completes_within_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENTADVISOR_RUNTIME_ROOT", str(tmp_path / "runtime-root"))
    monkeypatch.setenv("AGENTADVISOR_MEMORY_ROOT", str(tmp_path / "memory"))

    backend = make_backend()
    director_model, adversary_model, default_model = _CHEAP_PINS.get(
        str(backend.name), _CHEAP_PINS["cursor"]
    )

    def _cheap_resolve(
        *, backend: str, role_stem: str, tier: str, fallback: ModelPair
    ) -> ModelPair:
        if role_stem in _DIRECTOR_BUCKET:
            model = director_model
        elif role_stem in _ADVERSARY_BUCKET:
            model = adversary_model
        else:
            model = default_model
        return ModelPair(default_model=model, escalation_model=model)

    monkeypatch.setattr("orchestrator.roles_config.resolve_models", _cheap_resolve)

    case = create_case("toy-live", cases_root=tmp_path / "cases")
    state = run(
        case,
        raw_prompt=TOY_PROMPT,
        backend=backend,
        budget_config=SMALL_BUDGET,
        auto_approve=True,
        dual_track=False,
    )

    assert state.stage is CaseStage.DONE, (
        f"toy case ended in {state.stage.value}, not done; "
        "if the budget was exhausted, the pipeline no longer fits the toy budget "
        f"of {SMALL_BUDGET.max_agent_invocations} invocations"
    )

    # Every invocation and its usage must be in the audit log, and the total must
    # respect the cap.
    audit_path = case.root / "audit.jsonl"
    events = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    invocations = [e for e in events if e.get("event_type") == "role_invocation_attempt"]
    assert invocations, "no role invocations recorded in the audit log"
    assert len(invocations) <= SMALL_BUDGET.max_agent_invocations
    total_input = sum(
        e.get("usage", {}).get("input_tokens", 0) for e in invocations if e.get("usage")
    )
    assert total_input > 0, "invocations recorded without usage metadata"

    # A schema-valid FinalRecommendation and the rendered report.
    recommendation = case.read_artifact(FinalRecommendation)
    assert recommendation.recommended_action
    final_md = case.root / "outputs" / "final_recommendation.md"
    assert final_md.exists() and final_md.stat().st_size > 0
