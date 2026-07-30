---
id: SPEC-009
title: Task graph engine
phase: 2
status: draft
depends_on: [SPEC-007]
parallel_with: [SPEC-008]
north_star_refs: ["6.2", "8"]
last_updated: 2026-07-30
---

# SPEC-009 — Task graph engine

## Summary

Dependency-aware task management and parallel dispatch: hold TaskRecords, compute what is ready, run up to N workers concurrently, reconcile results into the blackboard.

## Motivation

North star Stage 4/5: the Planner proposes tasks; deterministic code decides execution order, enforces concurrency limits, and normalizes results.

## Scope

`orchestrator/task_graph.py`:

- Graph state in `shared/task_graph.yaml` (list of TaskRecords + edges), loaded/saved via case store.
- `add_tasks(records)` with cycle detection (reject cyclic additions).
- `ready() -> list[TaskRecord]`: dependencies completed, status `planned`, ordered by priority (materiality × probability-of-changing-conclusion ÷ cost fields from the TaskRecord; ties by task id).
- `dispatch(runner, max_concurrent)`: ThreadPoolExecutor over ready tasks, gated by `BudgetLedger.try_consume`; `runner` is injected (real one is SPEC-006 `invoke_role`; tests use stubs).
- Status transitions: planned → active → completed | failed; failed tasks mark dependents `blocked`; cancellation for tasks obsoleted by repair decisions.
- Reconciliation: worker outputs written to the blackboard under the graph lock, task marked completed, audit event emitted.

## Out of scope

Task proposal content (Planner role, SPEC-011), evidence normalization semantics (SPEC-012), stop decisions (SPEC-008).

## Design

Single-process, thread-based (subprocess-bound workload; no asyncio needed). One lock guards graph mutation and reconciliation; workers do all slow work outside the lock. Deterministic ordering guarantees reproducible dispatch given identical inputs.

## Deliverables

- [ ] `orchestrator/task_graph.py`
- [ ] `tests/test_task_graph.py`

## Acceptance criteria

- [ ] Dependency ordering: a task never dispatches before its dependencies complete (asserted under concurrency with randomized stub durations).
- [ ] Concurrency cap: with max_concurrent=3, observed in-flight count never exceeds 3.
- [ ] Failure propagation: failing task blocks all transitive dependents; independent branches complete.
- [ ] Cycle addition rejected with a clear error.
- [ ] Priority ordering respected for ready tasks; deterministic across runs.
- [ ] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_task_graph.py -q
```

## Verification results

—

## Open questions

- None.
