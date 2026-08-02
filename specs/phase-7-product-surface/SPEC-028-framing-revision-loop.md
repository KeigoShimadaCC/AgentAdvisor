---
id: SPEC-028
title: Framing revision loop and final send-back
phase: 7
status: implemented
depends_on: [SPEC-027]
parallel_with: [SPEC-031]
north_star_refs: ["8", "14", "15"]
last_updated: 2026-08-02
---

# SPEC-028 — Framing revision loop and final send-back

## Summary

Makes the approval gates two-way. `FramingApproval` already supports
`decision: edit | answer_clarifications` with `edits` and `clarification_answers` payloads, and
`IntakeRecord` already carries up to five clarification questions — but no code consumes any of
it: writing `decision: edit` today changes nothing, and `awaiting_framing_approval` has no path
back to `framing`. This spec adds the framing revision transition, projects the user's edits and
answers into a framing re-run, and adds the bounded final-gate send-back that routes a delivery
back through synthesis with the user's note.

## Motivation

North star Section 8 Stage 3 of the preferred interaction is "user approves **or adjusts** the
framing"; Section 15 requires revision to feel like correcting a shared understanding. The
discovery report's checkpoint design (§13.2, §13.9) depends on both paths, and its §4.6 records
that the intake role's clarification questions have never been shown to a human.

## Scope

- `orchestrator/state_machine.py`:
  - new transitions: `awaiting_framing_approval → framing` and
    `awaiting_final_approval → synthesis`.
  - `CaseState` gains `framing_revisions: int = 0` and `final_revisions: int = 0`; caps
    `MAX_FRAMING_REVISIONS = 2`, `MAX_FINAL_REVISIONS = 1` enforced in routing.
- `orchestrator/stages.py::handle_framing` — when `shared/framing_approval.yaml` exists with a
  revision decision, the director-framing invocation receives a `framing_feedback` projection:
  the previous `decision_spec`, the `edits` dict, and the `clarification_answers`, with an
  instruction block to incorporate them and to attribute answered values to the user.
- `orchestrator/projection.py` — new include key `framing_feedback`.
- `orchestrator/stages.py::handle_synthesis` — a final send-back reuses the existing re-synthesis
  feedback mechanism: the user's note is injected alongside `review_report.yaml` in the retry
  prompt; `final_revisions` is independent of `synthesis_retries` (a review-triggered retry and a
  user-triggered revision are different events with different budgets).
- `orchestrator/control.py` additions:
  - `request_framing_revision(case_id, *, edits, clarification_answers)` — validates against the
    `FramingApproval` model, writes the artifact, transitions to `framing`, restarts the worker;
    refuses over-cap with a clear error.
  - `request_final_revision(case_id, *, note)` — writes `FinalApproval(decision=revise, note=…)`,
    transitions to `synthesis`, restarts the worker; refuses a second request.
  - Both raise `WrongStage` when the case is not parked at the corresponding gate.
- Audit events: `framing_revision_requested`, `final_revision_requested` (payload includes which
  fields were edited / which questions answered, not full values).
- `cursor/roles/director-framing.md` — short addition describing the feedback contract (edits are
  user statements and override prior defaults; answered clarifications may be attributed to the
  user).

## Out of scope

- Any third gate or mid-run steering; revision exists only at the two existing gates.
- UI for these paths (SPEC-034 / SPEC-035).
- Regenerating the issue tree after a framing revision (structuring runs fresh anyway because it
  is downstream of the gate).
- "Reject" as a distinct state — a case left unsigned simply stays parked; abandoning a case is
  archival, not a state-machine concern.

## Design

Revision is modeled as a normal backward transition plus a projection, not as a special mode:
the framing handler cannot tell a first run from a revision except by the presence of feedback,
which keeps the stage idempotent under SPEC-030's rules. Caps live in routing (deterministic
control per north star 5.4), not in prompts. The user's `edits` dict is passed through verbatim
as data — the framing agent, not Python, merges meaning — but answered fields are validated
against `IntakeField` names so a typo cannot silently vanish.

## Deliverables

- [ ] state-machine transitions + revision counters + caps
- [ ] `framing_feedback` projection key and handler wiring
- [ ] `control.request_framing_revision` / `control.request_final_revision`
- [ ] director-framing role md amendment
- [ ] `tests/test_framing_revision.py`, `tests/test_final_sendback.py` (stub backend)

## Acceptance criteria

- [ ] Submitting `decision: edit` with a non-empty `edits` dict re-runs framing exactly once; the
      archived framing workspace's `inputs/` contains the edits and the previous spec; a new
      `decision_spec.yaml` is written; `framing_revisions == 1`.
- [ ] Submitting `decision: answer_clarifications` projects the answers; an answer keyed to an
      unknown `IntakeField` is rejected at validation.
- [ ] A third framing revision request is refused with the cap named in the error.
- [ ] At `awaiting_final_approval`, `request_final_revision` routes to `synthesis` exactly once;
      the synthesizer workspace `task.yaml` contains the user note; a second request is refused;
      the case then re-parks at `awaiting_final_approval`.
- [ ] Both control functions raise `WrongStage` at any other stage.
- [ ] `make check` passes.

## Verification plan

```
uv run pytest tests/test_framing_revision.py tests/test_final_sendback.py tests/test_state_machine.py -q
make check
```

## Verification results

All acceptance criteria verified via `make check` (ruff + mypy + pytest, 590 passed):

- `decision: edit` with non-empty edits re-runs framing; archived workspace `inputs/`
  contains `framing_feedback.yaml` (with edits) and previous `decision_spec.yaml`;
  new `decision_spec.yaml` written; `framing_revisions == 1`.
- `decision: answer_clarifications` projects answers to the workspace; unknown
  `IntakeField` key rejected at validation.
- Third framing revision request refused with `RevisionCapReached` naming the cap (2).
- `request_final_revision` routes to synthesis; synthesizer workspace `task.yaml`
  contains the user note; second request refused; case re-parks at
  `awaiting_final_approval`.
- Both control functions raise `WrongStage` at the wrong stage.

## Open questions

- None.
