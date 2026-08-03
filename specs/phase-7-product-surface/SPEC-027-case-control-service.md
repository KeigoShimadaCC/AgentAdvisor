---
id: SPEC-027
title: Case control service and run supervisor
phase: 7
status: verified
depends_on: [SPEC-018]
parallel_with: [SPEC-031]
north_star_refs: ["5.4", "14", "15"]
last_updated: 2026-08-03
---

# SPEC-027 — Case control service and run supervisor

## Summary

A callable control layer over the case store and pipeline — create a case, report status, sign both
approval gates, pause, resume — plus a supervisor that owns at most one pipeline worker process per
case, enforces the single-writer rule across processes, and detects interrupted runs at startup.
Today approval means hand-editing `state.yaml` and re-invoking `run()` in-process; the frontend
(SPEC-033) and the user CLI (SPEC-019) both need one shared, audited entry point instead.

## Motivation

North star Section 14 makes the user the decision owner and Section 15 requires the two consent
moments to be real interactions. The state machine already parks at
`awaiting_framing_approval` / `awaiting_final_approval`, but nothing outside the test suite can
grant them. The discovery report (`frontend-discovery-report.md` §4.6, §17) identifies this as the
single most important missing piece, and notes that the second gate currently sets
`final_approved=True` without writing any auditable record at all.

## Scope

- `orchestrator/control.py` — synchronous control functions, all lock-guarded:
  - `new_case(raw_prompt, *, slug, budget_profile, depth) -> CaseId` — creates the case and starts
    a worker that runs to the first halt.
  - `case_status(case_id) -> ControlStatus` — stage, approval waits, worker liveness, failure cause.
  - `approve_framing(case_id, approval: FramingApproval)` — writes `shared/framing_approval.yaml`,
    sets `framing_approved`, restarts the worker. Only `decision: approve` is handled here;
    revision decisions are SPEC-028.
  - `approve_final(case_id, approval: FinalApproval)` — writes `outputs/final_approval.yaml`, sets
    `final_approved`, restarts the worker to completion.
  - `pause(case_id)` — stops the worker (process-group SIGKILL, same mechanism as the backend
    timeout); the case parks at its last checkpointed stage.
  - `resume(case_id)` — restarts a worker for a parked or interrupted case (safe-resume
    reconciliation is SPEC-030; until it lands, `resume` refuses cases with orphaned `active`
    tasks and says why).
- `orchestrator/artifacts/approvals.py` — `FinalApproval` model: `decision`
  (`FinalDecision: accept | revise`), `note` (str, required when `revise`), `approved_by`,
  `approved_at`. Registered in `case_store` singleton paths and `schema_export.MODEL_EXPORTS`.
- `orchestrator/supervisor.py` — worker lifecycle: spawn `python -m orchestrator.worker <case-id>`
  as a supervised child with its own process group; `.run.lock` advisory lockfile in the case
  directory containing `{pid, started_at}`; `is_running`, `stop`, `interrupted_cases()` (case in
  an active stage, no live worker, lock stale = pid dead).
- `orchestrator/worker.py` — process entry point: load case, build the configured backend
  (Cursor CLI by default, `AGENTADVISOR_BACKEND=stub` for tests), call `pipeline.run`, exit 0 on
  clean halt (gate or done), nonzero on failure.
- Control-plane audit events through the existing `Case.audit` channel:
  `control_case_created`, `control_checkpoint_signed` (payload: gate, decision, edited fields),
  `control_run_started`, `control_run_stopped`, `control_interrupted_detected`.
- Every control mutation acquires the lockfile; a held lock raises `CaseLocked` with the holder's
  pid and age.

## Out of scope

- HTTP surface, SSE, and the SPA (SPEC-033).
- Framing edits/clarification answers and the final send-back path (SPEC-028).
- Safe-resume reconciliation of orphaned tasks (SPEC-030).
- Cooperative mid-invocation cancellation (kill-and-park is v1 pause).
- The CLI command surface (SPEC-019 becomes a thin adapter over this module; its spec is amended
  when implemented, not here).

## Design

Control functions are plain synchronous Python over public `case_store` / `state_machine` /
`pipeline` APIs; they touch no orchestrator internals and add no new stage semantics. The worker
is a separate OS process so `run()`'s 40–90 min blocking behavior never blocks a caller, a crashed
run cannot take the service down, and browser/app lifetime is decoupled from run lifetime. The
lockfile is created with `O_CREAT|O_EXCL`; staleness = recorded pid not alive. Approval writes go
through `save_case_state` (atomic) after the artifact write, in that order, so a crash between the
two leaves an artifact without a flag — recoverable — never a flag without a record.

## Deliverables

- [ ] `orchestrator/control.py`
- [ ] `orchestrator/supervisor.py`
- [ ] `orchestrator/worker.py`
- [ ] `orchestrator/artifacts/approvals.py` (`FinalApproval`, `FinalDecision`) + schema export +
      case-store path registration
- [ ] `tests/test_control.py`, `tests/test_supervisor.py` (StubBackend end-to-end)
- [ ] regenerated `schemas/final_approval.schema.json`

## Acceptance criteria

- [ ] `new_case` with the stub backend returns once the case parks at
      `awaiting_framing_approval`; `state.yaml` on disk matches; `control_case_created` and
      `control_run_started` are in the audit log.
- [ ] `approve_framing` writes `shared/framing_approval.yaml`, flips the flag, and the resumed
      worker advances the case to `awaiting_final_approval` (stub run).
- [ ] `approve_final` writes `outputs/final_approval.yaml` and the case reaches `done`; the gate-2
      record exists for a non-auto-approved case for the first time.
- [ ] A second control mutation while a worker holds the lock raises `CaseLocked`; a stale lock
      (dead pid) is reclaimed and audited.
- [ ] Killing the worker mid-run puts the case in `interrupted_cases()`; `pause` then `resume` on
      a gate-parked case restarts cleanly.
- [ ] `make check` passes.

## Verification plan

```
uv run pytest tests/test_control.py tests/test_supervisor.py -q
make schemas && git diff --exit-code schemas/
make check
```

## Verification results

**2026-08-03 — verification plan executed.** `make check` green: ruff, ruff format, mypy on 65 source files, 639 unit tests (17 live deselected).

Spec's own plan run in full — 30 tests: `tests/test_control.py` + `tests/test_supervisor.py`: all pass. `make schemas` left `schemas/` byte-identical, confirming `final_approval.schema.json` is committed in sync.

## Open questions

- None.
