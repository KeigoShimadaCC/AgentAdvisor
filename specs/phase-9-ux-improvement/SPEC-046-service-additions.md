---
id: SPEC-046
title: Service additions — progress events, non-blocking creation, projection reads
phase: 9
status: draft
depends_on: []
parallel_with: [SPEC-045]
north_star_refs: ["13", "15"]
last_updated: 2026-08-05
---

# SPEC-046 — Service additions: progress events, non-blocking creation, projection reads

## Summary

Every backend change phase 9 needs, gathered into one spec so the backend is opened once, reviewed
once, and closed. Four additions: two audit events so the stream is not silent during the longest
wait in the product, a non-blocking `new_case` so commissioning is not a disabled button for
minutes, `needs_you` on the case list so the client stops re-deriving it, and a read endpoint over
the calibration machinery that has never been exposed. All four are emits or reads. Carries the
phase's structural guarantee as a test: zero diff in the state machine's transitions and handlers.

## Motivation

North star Section 15 requires the interface to expose meaningful progress. It cannot: the audit log
records an invocation *after* it returns (`invoke_role.py:224`), so during a multi-minute agent call
nothing is emitted at all. `LiveActivity` consequently infers "running" from the last attempt whose
status is *not* `ok`, so a healthy long-running agent renders as the previous agent, greyed, marked
completed — the UI is most reassuring when something is going wrong. Section 13 (cost and resource
principles) motivates the calibration read: `orchestrator/calibration.py` computes a Brier score
against realised outcomes, `MemoryStore.calibration()` returns it, and nothing in the product can
reach it.

## Scope

- `orchestrator/invoke_role.py` — two new audit events alongside the existing
  `role_invocation_attempt`:
  - `role_invocation_started`, emitted immediately before the backend call, carrying `task_id`,
    `role`, `model`, `attempt`;
  - `role_invocation_progress`, emitted on a ~20 s timer for the duration of the call, carrying the
    same identifiers plus `elapsed_s`. The timer is owned by the invocation, is a daemon, and is
    cancelled in a `finally` so it cannot outlive the call it describes.
- `orchestrator/service/lexicon_data.yaml` — narration templates for both, `technical: false`.
- `orchestrator/control.py` — `new_case` gains a `worker_runner` parameter defaulting to the
  existing blocking runner, exactly as `approve_framing` already has. The service passes
  `spawn_worker_background`.
- `orchestrator/service/app.py`:
  - `POST /api/cases` creates the case directory, writes `control_meta.yaml`, audits
    `control_case_created`, starts the background worker and returns `202` with
    `{case_id, stage}` — without waiting for intake or framing;
  - `CaseSummary` gains `needs_you`, computed by the same helper the projection uses, so
    `CaseLibrary.tsx`'s duplicated stage-string derivation can be deleted in SPEC-052;
  - `GET /api/calibration` → `CalibrationSummary` over `MemoryStore(root=memory_root())`.
- `schemas/` + `frontend/src/generated/` — `CalibrationSummary` exported and its TypeScript type
  regenerated through the existing drift gate. `CaseSummary` is a service model, not an artifact
  schema, and changes in place.
- `tests/test_invoke_role.py`, `tests/test_service_api.py`, `tests/test_events.py` — extended.
- `tests/test_pipeline_invariants.py` — new: the no-flow-change guarantee.

## Out of scope

- Any consumption of these events or endpoints in the UI (SPEC-047, SPEC-051).
- Token-level or sub-invocation streaming. The 20 s cadence is deliberate: the backends expose no
  token stream, and a heartbeat is what the audit log can honestly carry.
- Extending `CaseView` for phase 8's artifacts (SPEC-053).
- Any change to stages, transitions, handlers, roles, or artifact schemas.

## Design

The two events are additive rows in an append-only log, which is why this spec can add live progress
without touching the pipeline: `invoke_role` already owns the call boundary and already audits at
it, so the change is one emit before and one timer around code that exists. Both events reuse the
`role_invocation_attempt` payload shape so the lexicon, the SSE translation and the Method room need
no special cases.

`new_case` is the only control function that still blocks to a halt; `approve_framing`,
`approve_final` and `resume` were all moved to `spawn_worker_background` when the event-loop freeze
was fixed. This spec finishes that migration rather than inventing a mechanism. The 202 is honest:
the case exists and is durable when it returns, and the client follows the same SSE stream it would
have followed anyway.

`tests/test_pipeline_invariants.py` is the mechanism that makes the phase's headline constraint
checkable rather than asserted. It snapshots `ALLOWED_TRANSITIONS`, `_FLOW_PLANS` and the registered
stage handlers, and fails on any diff. It is written here and inherited by every later phase-9 spec,
so a UI spec that quietly reaches into the pipeline breaks a test rather than a promise.

## Deliverables

- [ ] `orchestrator/invoke_role.py` — `role_invocation_started`, `role_invocation_progress`, timer
- [ ] `orchestrator/service/lexicon_data.yaml` — two narration templates
- [ ] `orchestrator/control.py` + `app.py` — non-blocking `new_case` returning 202
- [ ] `app.py` — `needs_you` on `CaseSummary`; `GET /api/calibration`; `CalibrationSummary` schema
      and regenerated TS type
- [ ] `tests/test_pipeline_invariants.py` — transitions/handlers snapshot guard
- [ ] Extensions to `tests/test_invoke_role.py`, `tests/test_service_api.py`, `tests/test_events.py`

## Acceptance criteria

- [ ] A stubbed invocation emits `role_invocation_started` before the backend call and at least one
      `role_invocation_progress` for a call exceeding the interval; both carry `task_id`, `role`,
      `model` and `attempt`, and the progress timer is stopped when the call returns — asserted on
      the success, validation-failure and backend-failure paths.
- [ ] No `role_invocation_progress` is emitted after its invocation ends, verified by asserting the
      last progress event's cursor precedes the matching `role_invocation_attempt`.
- [ ] Both event types have lexicon entries that fill without error and arrive over SSE as
      non-technical translated events with monotonic cursors.
- [ ] `POST /api/cases` returns `202` with a resolvable `case_id` before the worker reaches the
      framing gate; `GET /api/cases/{id}/view` succeeds immediately afterwards, and the case still
      parks at `awaiting_framing_approval`.
- [ ] `GET /api/cases` carries `needs_you` matching `GET /api/cases/{id}/view`'s value for the same
      case across all four states.
- [ ] `GET /api/calibration` returns the sample size and, with fewer than five recorded outcomes,
      the "noise, not a calibration estimate" interpretation verbatim from `calibration.py`.
- [ ] `tests/test_pipeline_invariants.py` passes, and fails if a transition, flow plan or stage
      handler is added, removed or re-pointed. `make check` and `make frontend-check` are green.

## Verification plan

```
uv run pytest tests/test_invoke_role.py tests/test_service_api.py tests/test_events.py -q
uv run pytest tests/test_pipeline_invariants.py -q
cd frontend && npm run check:clean          # CalibrationSummary type drift
make check
make frontend-check
E2E_MODE=stub npx playwright test --config=frontend/e2e/playwright.config.ts   # lifecycle still parks at both gates
```

## Verification results

Not yet executed.

## Open questions

- Progress cadence: 20 s is chosen so a 3-minute call produces ~9 events and a 191-minute case adds
  a few hundred audit lines. If that proves noisy in the Method room, the cadence is a constant and
  the events are already flagged for filtering — but the default should be settled before approval.
