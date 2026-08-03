---
id: SPEC-030
title: Safe resume and delivery-integrity persistence
phase: 7
status: verified
depends_on: [SPEC-029]
parallel_with: []
north_star_refs: ["5.4", "18"]
last_updated: 2026-08-03
---

# SPEC-030 — Safe resume and delivery-integrity persistence

## Summary

Makes an interrupted case resumable without corruption, and makes "the review actually passed" a
persisted engine fact. Today a killed run leaves zombie `active` tasks that are never
re-dispatched; re-running a stage collides with archived agent workspaces (`FileExistsError`
swallowed as a validation failure → case `FAILED`); batch unpacking re-mints duplicate
`E-/A-/O-` IDs; and a case that exhausts its synthesis retry advances to `done` with a failing
`review_report` that nothing surfaces — the completed reference case shipped exactly this way.

## Motivation

PROJECT_PLAN DoD A requires "a case can be checkpointed, resumed, and inspected mid-run" (its
resume criterion is recorded as not yet tested in SPEC-018). North star 5.4 puts workflow state
under deterministic control, and Section 18's traceability criteria are hollow if `done` can
silently mean "review failed." The discovery report's interrupted-run and integrity-slip designs
(§11, §13.9) depend on both guarantees.

## Scope

- **Orphan reconciliation** — `orchestrator/task_graph.py`: `reconcile_orphans()` resets `active`
  tasks to `planned` (audit: `task_reset_on_resume`, payload lists task ids); called by
  `pipeline.run` when it loads a case in an active stage and by `control.resume` (SPEC-027's
  refusal is replaced by this path).
- **Archive collisions** — `case_store.archive_agent_workspace`: on existing destination, archive
  to `agents/<role>--<task_id>--rerun-<n>/` instead of raising; the invocation kit no longer
  swallows `FileExistsError` as a validation failure.
- **Idempotent unpack** — `orchestrator/unpack.py`: each unpack records a marker
  `shared/unpack_markers/<task_id>.yaml` (`{task_id, artifact_type, record_ids}`); re-unpacking
  the same task id is a no-op returning the recorded ids (audit: `unpack_skipped_duplicate`).
  Thesis ledger gains the same guard: `record_thesis_revision` skips when the head revision has
  identical `trigger`, `preferred_alternative`, and digest.
- **Delivery integrity** — `CaseState.review_accepted: bool | None` (None until review runs), set
  in `handle_review` from `review_is_acceptable(...)`; survives the advance-past-failed-review
  path; also mirrored into the `review_evaluated` audit payload (already present as `accepted`).
- **Resume entry** — `pipeline.prepare_resume(case)`: reconcile orphans, verify no live lock,
  return a report of what was reset; `run()` calls it implicitly on active-stage load.
- `tests/test_safe_resume.py` covering each hazard from the discovery report §4.7 / mechanics
  findings §6.

## Out of scope

- Mid-*invocation* checkpointing (stage re-run remains the granularity).
- Recovering partial batch output from a killed agent workspace.
- Changing the review→approval routing itself (a failed review still advances after its retry;
  it now does so *legibly*).
- UI surfacing (SPEC-032/035 read `review_accepted`).

## Design

Resume is made idempotent by construction rather than by cleanup scripts: every non-idempotent
write path (task status, archive naming, ID minting, thesis append) gets a deterministic guard
keyed on stable identifiers already in the system (`task_id`, revision content). Markers live
inside `shared/` so a case directory remains self-describing and the audit log remains the
chronology. `review_accepted` is deliberately tri-state — `None` distinguishes "review never ran"
(crash before review) from a recorded verdict.

## Deliverables

- [ ] `reconcile_orphans` + wiring in `pipeline.run` / `control.resume`
- [ ] collision-safe workspace archiving (`--rerun-<n>`)
- [ ] unpack markers + duplicate guard; thesis duplicate guard
- [ ] `CaseState.review_accepted` persisted from `handle_review`
- [ ] `pipeline.prepare_resume`
- [ ] `tests/test_safe_resume.py`

## Acceptance criteria

- [ ] Simulated crash mid-investigation (two tasks `active`, no worker): `prepare_resume` resets
      exactly those tasks; the resumed stub run completes; the audit log shows
      `task_reset_on_resume`.
- [ ] Re-running a stage whose agent workspace is already archived succeeds and produces a
      `--rerun-1` archive; the case does not fail.
- [ ] Re-executing a stage that already unpacked task `T-004`'s evidence batch mints zero new
      `E-` ids (counter file unchanged; `unpack_skipped_duplicate` audited).
- [ ] A fixture case whose review fails after its retry reaches `done` with
      `review_accepted: false` in `state.yaml`; a passing case records `true`; a case crashed
      before review reloads with `None`.
- [ ] Interrupted → `resume` end-to-end on the stub backend reaches `done` with no duplicate
      thesis revision and no duplicate blackboard ids.
- [ ] `make check` passes.

## Verification plan

```
uv run pytest tests/test_safe_resume.py tests/test_task_graph.py tests/test_case_store.py -q
make check
```

## Verification results

**2026-08-03 — verification plan executed.** `make check` green: ruff, ruff format, mypy on 65 source files, 639 unit tests (17 live deselected).

Spec's own plan run in full — 27 tests: `tests/test_safe_resume.py`, `tests/test_task_graph.py`, `tests/test_case_store.py`: all pass.

## Open questions

- None.
