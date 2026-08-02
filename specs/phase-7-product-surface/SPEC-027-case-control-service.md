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

A shared control layer over the case store and pipeline — create, status, sign both approval
gates, run, pause, resume — plus a supervisor that enforces one writer per case across processes
and can run a case in a detached worker. Every caller (the `advisor` CLI today, the web service
in SPEC-033) goes through the same audited functions instead of reimplementing gate mechanics.

## Motivation

North star Section 14 makes the user the decision owner and Section 15 requires the two consent
moments to be real interactions. The state machine parks at `awaiting_framing_approval` /
`awaiting_final_approval`, and the discovery report
(`frontend-discovery-report.md` §4.6, §17) identified the control surface as the frontend's
first prerequisite.

**Amended 2026-08-03 after SPEC-019 landed.** The `advisor` CLI (`orchestrator/cli.py`) now
implements `new/status/approve/resume/report/list`, and `cmd_approve` already writes a
`FramingApproval`, sets the flag and resumes. This spec therefore no longer builds gate mechanics
from scratch; it **extracts** them into a reusable module and adds the three things the CLI still
lacks, all of which the web service needs:

1. a callable API that is not argparse-shaped, so a second caller does not duplicate the logic;
2. cross-process single-writer enforcement — `case_store` documents one-process/many-threads, and
   two concurrent runs on one case corrupt `counters.yaml` and interleave `audit.jsonl`;
3. an auditable **final** approval record — `cmd_approve` currently flips `final_approved` with
   no artifact, so the second consent moment leaves no trace (the first one does).

## Scope

- `orchestrator/artifacts/approvals.py` — `FinalApproval` (`decision: FinalDecision`
  = `accept | revise`, `note`, `approved_by`, `approved_at`), validator requiring a note on
  `revise`. Registered in `case_store._artifact_path_for_write` at
  `outputs/final_approval.yaml`, exported from `orchestrator.artifacts`, and added to
  `schema_export.MODEL_EXPORTS`.
- `orchestrator/supervisor.py`:
  - `CaseLocked` exception carrying holder pid and lock age.
  - `case_lock(case)` context manager over `<case>/.run.lock` created `O_CREAT|O_EXCL` holding
    `{pid, started_at}`; a lock whose pid is dead is stale and is reclaimed.
  - `running_pid(case)`, `is_running(case)`, `stop(case)` (process-group termination, mirroring
    the backend's timeout kill), `interrupted_cases(cases_root)` — cases in a non-terminal,
    non-gate stage with no live worker.
  - `start_worker(case, ...)` — spawn `python -m orchestrator.worker` detached, return pid.
- `orchestrator/worker.py` — `python -m orchestrator.worker <case-id>` entry point: resolves the
  case, selects the backend, runs to the next halt, exits 0 on a clean halt and non-zero on
  pipeline failure. Backend selection is an injection seam,
  `AGENTADVISOR_BACKEND_FACTORY=module:callable`, defaulting to `CursorCLIBackend`; a plain
  `=stub` value was rejected during implementation because `StubBackend` requires scripted
  results, and hardcoding a test double in the orchestrator package would violate the backend
  boundary.
- `orchestrator/control.py` — the shared layer, all lock-guarded:
  - `new_case(prompt, *, slug, cases_root)`, `raw_prompt_for(case)`
  - `case_status(case) -> ControlStatus` (stage, awaiting, running pid, counters, failure cause)
  - `approve_framing(case, approval)` / `approve_final(case, approval)` — write the artifact,
    then set the flag, in that order, and audit `control_checkpoint_signed`
  - `run_to_halt(case, ...)` — synchronous in-process run (what the CLI uses)
  - `pause(case)`, `resume_allowed(case)`
  - `WrongStage` error for gate operations at a non-gate stage.
- `orchestrator/cli.py` refactored to call `control`; its user-visible behaviour, output and exit
  codes are unchanged, and `advisor approve` at the final gate now writes the `FinalApproval`.
- Control-plane audit events via `Case.audit`: `control_case_created`,
  `control_checkpoint_signed`, `control_run_started`, `control_run_finished`,
  `control_run_stopped`.

## Out of scope

- HTTP surface, SSE and the SPA (SPEC-033).
- Framing edits/answers actually re-shaping the spec, and the final send-back path (SPEC-028).
  This spec records the user's decision; SPEC-028 makes `revise` route.
- Orphaned-task reconciliation on resume (SPEC-030); `resume` here is the existing behaviour plus
  the lock.
- Cooperative mid-invocation cancellation — `pause` kills at the process boundary.
- Any change to stage semantics or routing.

## Design

`control.py` holds no decision logic: it composes `case_store`, `state_machine` and `pipeline`
exactly as the CLI does today, so extraction is behaviour-preserving and the CLI's existing tests
keep passing unchanged. Approval writes go artifact-first, flag-second, so a crash between them
leaves a record without a flag (recoverable and visible) rather than a flag with no record.

Running is deliberately offered in two shapes: `run_to_halt` (synchronous, what a CLI wants) and
`start_worker` (detached, what a web UI wants). Both take the same lock, so the two callers can
never race. The lock is advisory and self-healing: a lockfile whose recorded pid is no longer
alive is reclaimed and the reclamation is audited, so a killed run does not wedge a case.

## Deliverables

- [x] `orchestrator/artifacts/approvals.py` + case-store path + `orchestrator.artifacts` export
- [x] `orchestrator/supervisor.py`
- [x] `orchestrator/worker.py`
- [x] `orchestrator/control.py`
- [x] `orchestrator/cli.py` refactored onto `control`
- [x] `schemas/final_approval.schema.json` regenerated
- [x] `tests/test_control.py`, `tests/test_supervisor.py`

## Acceptance criteria

- [x] `control.new_case` + `run_to_halt` on the stub backend parks the case at
      `awaiting_framing_approval`, and `control_case_created` / `control_run_started` /
      `control_run_finished` are in the audit log.
- [x] `approve_framing` writes `shared/framing_approval.yaml`, sets the flag, and the next
      `run_to_halt` reaches `awaiting_final_approval`.
- [x] `approve_final` writes `outputs/final_approval.yaml` — the first auditable record of the
      second gate — and the case reaches `done`.
- [x] `approve_framing` / `approve_final` at any other stage raise `WrongStage`.
- [x] `FinalApproval(decision=revise)` without a note is rejected by the model validator.
- [x] Entering `case_lock` twice raises `CaseLocked` naming the holder pid; a lock whose pid is
      dead is reclaimed and the case runs.
- [x] A case in a non-terminal, non-gate stage with no live worker appears in
      `interrupted_cases`; a gate-parked case does not.
- [x] `advisor` CLI behaviour is unchanged: the full `tests/test_cli.py` suite passes untouched.
- [x] `make check` passes.

## Verification plan

```
uv run pytest tests/test_control.py tests/test_supervisor.py tests/test_cli.py -q
make schemas && git diff --exit-code schemas/
make check
```

## Verification results

**2026-08-03.** `make check` green: ruff, ruff format, mypy on 63 source files, 601 unit tests
(17 live deselected). `tests/test_control.py` (19 tests) covers the lifecycle through both gates
on `PipelineStubBackend`, the final-gate artifact, `WrongStage` at non-gate stages, the
`revise`-without-note rejection, status reporting (including a live run detected through the
lock), resume guards, and the control audit events. `tests/test_supervisor.py` (13 tests) covers
lock acquisition and release, contention, release on exception, stale-pid and malformed-lock
reclamation, killing a live holder's process group, and `interrupted_cases` classification
(active stage vs gate vs terminal vs running).

`tests/test_cli.py` passes unmodified, which is the behaviour-preservation evidence for the
refactor. `make schemas` produced `schemas/final_approval.schema.json` and left every other
schema byte-identical.

## Open questions

- None.
