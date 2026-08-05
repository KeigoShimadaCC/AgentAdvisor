"""Pipeline invariants — the structural guarantee phase 9 rests on (SPEC-046).

Phase 9 is a UX phase.  Its headline claim is that it changes what the product
*communicates*, not what it *does*: no stage, no transition, no handler, no
role.  That claim is worth exactly as much as its enforcement, so it is
enforced here rather than asserted in a spec sheet.

These tests snapshot the shape of the state machine.  A phase-9 change that
quietly reaches into the pipeline — adding a stage, re-pointing a handler,
opening a new edge — fails a test instead of passing review.  If a *later*
phase legitimately changes the pipeline, that phase updates the snapshot in the
same commit, which makes the change visible in the diff.  That is the point:
the snapshot is not a freeze, it is a tripwire.
"""

from __future__ import annotations

from orchestrator.state_machine import (
    _FLOW_PLANS,
    ACTIVE_STAGES,
    ALLOWED_TRANSITIONS,
    MAX_FINAL_REVISIONS,
    MAX_FRAMING_REVISIONS,
    CaseStage,
)

# ── The snapshot ─────────────────────────────────────────────────────────────
#
# Recorded 2026-08-05, at the phase 9 base (main @ 8fbf441).  Stage names are
# written as their string values so a rename shows up as a diff here too.

EXPECTED_TRANSITIONS: dict[str, set[str]] = {
    "intake": {"framing", "failed"},
    "framing": {"awaiting_framing_approval", "failed"},
    "awaiting_framing_approval": {"structuring", "framing", "failed"},
    "structuring": {"provisional_thesis", "failed"},
    "provisional_thesis": {"planning", "failed"},
    "planning": {"investigation", "failed"},
    "investigation": {"evidence_critique", "failed"},
    "evidence_critique": {"assumption_ledger", "failed"},
    "assumption_ledger": {"preliminary_recommendation", "failed"},
    "preliminary_recommendation": {"pre_mortem", "failed"},
    "pre_mortem": {"challenge", "failed"},
    "challenge": {"stop_decision", "failed"},
    "repair": {"challenge", "failed"},
    "stop_decision": {"repair", "synthesis", "failed"},
    "synthesis": {"review", "failed"},
    "review": {"awaiting_final_approval", "synthesis", "failed"},
    "awaiting_final_approval": {"done", "synthesis", "failed"},
    "done": set(),
    "failed": set(),
}

# stage -> (handler_name, roles).  ``None`` handlers are approval gates, which
# have no handler because they wait for a human.
EXPECTED_FLOW_PLANS: dict[str, tuple[str | None, tuple[str, ...]]] = {
    "intake": ("intake", ("intake",)),
    "framing": ("framing", ("director",)),
    "awaiting_framing_approval": (None, ()),
    "structuring": ("structuring", ("structurer",)),
    "provisional_thesis": ("provisional_thesis", ("director",)),
    "planning": ("planning", ("planner",)),
    "investigation": ("investigation", ("researcher", "analyst")),
    "evidence_critique": ("evidence_critique", ()),
    "assumption_ledger": ("assumption_ledger", ("assumption_analyst",)),
    "preliminary_recommendation": ("preliminary_recommendation", ("director",)),
    "pre_mortem": ("pre_mortem", ("premortem",)),
    "challenge": ("challenge", ("challenger", "auditor")),
    "repair": ("repair", ("planner",)),
    "stop_decision": ("stop_decision", ()),
    "synthesis": ("synthesis", ("synthesizer",)),
    "review": ("review", ("reviewer",)),
    "awaiting_final_approval": (None, ()),
}


def test_allowed_transitions_are_unchanged() -> None:
    """Every edge in the state machine, and no others."""
    actual = {
        stage.value: {target.value for target in targets}
        for stage, targets in ALLOWED_TRANSITIONS.items()
    }
    assert actual == EXPECTED_TRANSITIONS


def test_flow_plans_are_unchanged() -> None:
    """Every stage's handler and role assignment."""
    # Reaching into _FLOW_PLANS is deliberate: this test exists to snapshot the
    # registry itself, so it must read the registry rather than a view of it.
    actual = {
        stage.value: (plan.handler_name, tuple(role.value for role in plan.roles))
        for stage, plan in _FLOW_PLANS.items()
    }
    assert actual == EXPECTED_FLOW_PLANS


def test_backward_edges_are_intra_phase() -> None:
    """The four review cycles stay inside their presentation phase.

    This is what makes a loop invisible to a phase strip and is the reason
    SPEC-047 replaces it with a map.  If a future change moves one of these
    across a phase boundary, the UI's loop rendering has to change with it.
    """
    from orchestrator.service.caseview import _STAGE_TO_PHASE

    backward = [
        (CaseStage.AWAITING_FRAMING_APPROVAL, CaseStage.FRAMING),
        (CaseStage.STOP_DECISION, CaseStage.REPAIR),
        (CaseStage.REPAIR, CaseStage.CHALLENGE),
        (CaseStage.REVIEW, CaseStage.SYNTHESIS),
        (CaseStage.AWAITING_FINAL_APPROVAL, CaseStage.SYNTHESIS),
    ]
    for source, target in backward:
        assert target in ALLOWED_TRANSITIONS[source], f"{source} -> {target} is not an edge"
        assert _STAGE_TO_PHASE[source] == _STAGE_TO_PHASE[target], (
            f"{source.value} -> {target.value} crosses a phase boundary; "
            "the case map's cycle rendering assumes it does not"
        )


def test_revision_caps_are_unchanged() -> None:
    """The caps the UI reports back to the user before they spend one."""
    assert MAX_FRAMING_REVISIONS == 2
    assert MAX_FINAL_REVISIONS == 1


def test_active_stages_match_the_non_terminal_set() -> None:
    """ACTIVE_STAGES stays the complement of the terminal stages."""
    terminal = {CaseStage.DONE, CaseStage.FAILED}
    assert set(ACTIVE_STAGES) == set(CaseStage) - terminal
