---
id: SPEC-007
title: Case state machine
phase: 2
status: verified
depends_on: [SPEC-003, SPEC-004]
parallel_with: [SPEC-005, SPEC-006]
north_star_refs: ["5.4", "8"]
last_updated: 2026-07-31
---

# SPEC-007 — Case state machine

## Summary

The deterministic spine: explicit case stages, a transition table, checkpointing after every transition, and resume from checkpoint. Fully testable with stub steps, zero model calls.

## Motivation

North star 5.4: deterministic control around probabilistic workers. The state machine is where "the orchestrator decides what is actually executed" becomes code.

## Scope

`orchestrator/state_machine.py`:

- `CaseStage` enum: `INTAKE`, `FRAMING`, `AWAITING_FRAMING_APPROVAL`, `PROVISIONAL_THESIS`, `PLANNING`, `INVESTIGATION`, `PRELIMINARY_RECOMMENDATION`, `CHALLENGE`, `REPAIR`, `STOP_DECISION`, `SYNTHESIS`, `REVIEW`, `AWAITING_FINAL_APPROVAL`, `DONE`, `FAILED`.
- `CaseState` model (extends SPEC-003): stage, repair_cycle count, budget counters reference, timestamps; persisted as `state.yaml` via case store.
- Transition table as data: allowed (stage → stage) pairs; anything else raises `IllegalTransition`.
- `route(state) -> StepPlan`: pure function returning the next step descriptor (which handler, which roles) for the current stage. Repair loop (north star 5.3): `STOP_DECISION` routes to `REPAIR` at most twice; each repair returns through `CHALLENGE` in final-falsification mode before the next `STOP_DECISION`; after the cap, `SYNTHESIS` is forced.
- `run_case(case, handlers, until=None)`: loop `route → execute handler → reduce → checkpoint`; handlers injected (real stage handlers arrive in SPEC-018; tests use stubs).
- Approval stages halt the loop and return control to the caller.

## Out of scope

Real stage handlers (SPEC-018), budget math (SPEC-008; the state machine only calls into it), task dispatch (SPEC-009).

## Design

`route` and `reduce` are pure; all I/O lives in the loop (checkpoint via case store). Handlers return typed `StepResult`s; `reduce` maps (stage, result) → next stage strictly through the transition table. Resume = load `state.yaml`, continue loop. `FAILED` is terminal and always reachable via an error result carrying the cause.

## Deliverables

- [x] `orchestrator/state_machine.py`
- [x] `tests/test_state_machine.py`

## Acceptance criteria

- [x] Happy-path simulation with stub handlers walks INTAKE → … → DONE including `PROVISIONAL_THESIS` between framing approval and planning, checkpointing at every transition (assert one state.yaml write per transition).
- [x] Repair loop executes at most 2 REPAIR passes, each routing REPAIR → CHALLENGE → STOP_DECISION, then forces SYNTHESIS.
- [x] Illegal transitions raise; FAILED reachable from any active stage on error results.
- [x] Kill-and-resume: interrupting after any transition and calling `run_case` again completes identically (same final stage sequence).
- [x] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_state_machine.py -q
```

## Verification results

**2026-07-31 — PASS.** `orchestrator/state_machine.py` and `tests/test_state_machine.py` (29 tests) now implement and verify the full stage model, including `PROVISIONAL_THESIS` between `AWAITING_FRAMING_APPROVAL` and `PLANNING`, with transitions encoded as data and enforced so illegal moves raise `IllegalTransition` naming both stages. Approval stages halt and return control to the caller rather than blocking or auto-advancing, and kill-and-resume was parametrized across every transition point to prove resumed runs reproduce the uninterrupted stage sequence exactly.

Repair routing is enforced as `STOP_DECISION -> REPAIR` (cap 2) -> `CHALLENGE` (final falsification) -> `STOP_DECISION`, with `SYNTHESIS` forced once the cap is reached, which closes the loop discipline required by the north star. Two review corrections were applied and covered: routing now uses distinct `TaskRole` members for `intake` and `reviewer` instead of conflating those stages with Director/Auditor, and `STOP_DECISION` no longer carries any agent role because it is handled by the deterministic StopEvaluator.

A post-implementation duplication was also removed: `atomic_write_text` was promoted as a public helper in `orchestrator/case_store.py` and reused by the state machine path, replacing a private copy in this module so one atomic-write implementation governs checkpoint durability.

## Open questions

- None.
