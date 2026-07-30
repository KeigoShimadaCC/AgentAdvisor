---
id: SPEC-009
title: Task graph engine
phase: 2
status: verified
depends_on: [SPEC-007]
parallel_with: [SPEC-008]
north_star_refs: ["6.2", "8"]
last_updated: 2026-07-31
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

- [x] `orchestrator/task_graph.py`
- [x] `tests/test_task_graph.py`

## Acceptance criteria

- [x] Dependency ordering: a task never dispatches before its dependencies complete (asserted under concurrency with randomized stub durations).
- [x] Concurrency cap: with max_concurrent=3, observed in-flight count never exceeds 3.
- [x] Failure propagation: failing task blocks all transitive dependents; independent branches complete.
- [x] Cycle addition rejected with a clear error.
- [x] Priority ordering respected for ready tasks; deterministic across runs.
- [x] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_task_graph.py -q
```

## Verification results

**2026-07-31 — PASS.** `orchestrator/task_graph.py` and `tests/test_task_graph.py` (12 tests) now verify dependency-safe parallel dispatch with real concurrency and deterministic ordering rules. Ordering and concurrency were stress-tested across 20 randomized duration seeds, and the observed in-flight counter proved the `max_concurrent=3` cap while maintaining dependency correctness.

Failure and mutation semantics are now explicit and auditable: a failed task is marked `failed`, its transitive dependents are marked `blocked`, and independent branches continue; cycle addition is rejected all-or-nothing by validating candidate updates in memory before any write; and budget refusal returns cleanly with tasks left `planned` and no busy loop. Graph mutation and reconciliation are guarded by one lock while runner execution remains outside the lock, so correctness is protected without serializing worker execution.

Three post-review correctness fixes were applied and validated: `TaskStatus.failed` was added to avoid conflating direct failures with dependency blocks; `TaskRecord` gained `estimated_cost` and `probability_of_changing_conclusion` so priority is truly `materiality_weight * probability_of_changing_conclusion / estimated_cost` with deterministic tie-break by task id; and the north star marginal-value rule is now a pre-dispatch gate that audits computed values under `task_marginal_value_refused` and can be disabled via constructor flag for tests and the toy end-to-end case.

## Open questions

- None.
