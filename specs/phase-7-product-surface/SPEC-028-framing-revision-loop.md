---
id: SPEC-028
title: Framing revision loop and final send-back
phase: 7
status: verified
depends_on: [SPEC-027]
parallel_with: [SPEC-031]
north_star_refs: ["8", "14", "15"]
last_updated: 2026-08-03
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
  - `CaseState` also gains `pending_framing_revision` / `pending_final_revision`: the reducer
    is a pure function of state and step result, so the request to route backwards has to be
    *in* the state. The reducer consumes the flag, counts the revision, and — critically —
    clears the gate flag it just used, so a revised framing must be signed off in its own right.
  - `_Transition` gains an `updates` mapping so a transition can write those fields.
- `orchestrator/stages.py::handle_framing` — on a revision the assignment gains an explicit
  revision block, and the invocation's task id carries the revision number.
- **Projection:** no new key. `decision_spec` and `framing_approval` already exist as include
  keys and `_singleton` tolerates a missing artifact, so the revision context is delivered by
  adding both to `cursor/roles/director-framing.yaml`'s `projection_include`. A `framing_feedback`
  key would have been a third name for artifacts the projection can already supply.
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

- [x] state-machine transitions, pending-revision flags, revision counters, caps
- [x] framing revision context via existing projection keys + `handle_framing` revision block
- [x] `control.request_framing_revision` / `control.request_final_revision` +
      `RevisionLimitReached`
- [x] user send-back note reaches the synthesizer (`_final_revision_note`)
- [x] `cursor/roles/director-framing.md` revision-handling contract
- [x] collision-safe workspace archiving (pulled forward from SPEC-030 — see below)
- [x] `tests/test_revision_loops.py`

## Acceptance criteria

- [x] A `decision: edit` request routes the case back to `framing`, re-runs it, and re-parks at
      the gate with `framing_revisions == 1` and `framing_approved == False`.
- [x] A revised case can then be approved and continues to the final gate.
- [x] `decision: answer_clarifications` is accepted as a revision; a plain `approve` is refused
      with a message pointing at `approve_framing`.
- [x] A third framing revision is refused with the cap named in the error.
- [x] `request_final_revision` routes to `synthesis` exactly once and the case re-parks at
      `awaiting_final_approval`; a second send-back is refused.
- [x] A user revision and a review-driven re-synthesis are counted separately.
- [x] Both control functions raise `WrongStage` at any other stage.
- [x] `make check` passes.

## Verification plan

```
uv run pytest tests/test_revision_loops.py tests/test_state_machine.py tests/test_control.py -q
make check
```

## Verification results

**2026-08-03.** `make check` green: ruff, ruff format, mypy, 601 unit tests (17 live deselected).
`tests/test_revision_loops.py` is 16 tests: 7 reducer-level (routing, counters, gate
re-holding, both caps, revision-vs-retry independence, error precedence) and 9 control-level
against `PipelineStubBackend` (recording, re-run, re-approval, answers, cap refusal, wrong
stage, the final send-back round trip and its refusal).

**One defect found and fixed while verifying.** The final send-back failed the case outright:

```
Review failed: Invocation failed after escalation ...
Errors: ['Archive destination already exists: .../agents/reviewer--T-review-1', ...]
```

Re-running a stage collided with the earlier run's archived agent workspace,
`archive_agent_workspace` raised `FileExistsError`, the invocation kit swallowed it as a
validation failure, and the case reached `FAILED`. This is exactly the hazard SPEC-030 catalogues
— but revisions make stage re-runs a *designed* occurrence rather than a crash-recovery edge, so
the fix could not wait for that spec. `archive_agent_workspace` now archives a repeat run
alongside its predecessor as `<role>--<task_id>--rerun-<n>` instead of refusing, and the review
and synthesis task ids carry the revision counter. SPEC-030 records that this deliverable landed
early.

## Open questions

- None.
