from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field

from orchestrator.artifacts import (
    AuditEvent,
    EvidenceBatch,
    Level,
    ObjectionBatch,
    TaskRecord,
    TaskStatus,
)
from orchestrator.artifacts.yaml_io import dump_model_to_yaml_text
from orchestrator.case_store import Case, atomic_write_text
from orchestrator.unpack import unpack_evidence_batch, unpack_objection_batch

type EdgeInput = Mapping[str, Sequence[str]] | Sequence[tuple[str, str]]

_LEVEL_WEIGHT: dict[Level, int] = {
    Level.HIGH: 3,
    Level.MEDIUM: 2,
    Level.LOW: 1,
}


class BudgetLedgerLike(Protocol):
    def try_consume(self, kind: str, model: str | None = None) -> bool: ...
    def is_high_tier_model(self, model: str) -> bool: ...
    def counts_against_high_tier(self, model: str, *, role_tier: str | None = None) -> bool: ...


@dataclass(frozen=True, slots=True)
class _PermissiveLedger:
    def try_consume(self, kind: str, model: str | None = None) -> bool:
        del kind, model
        return True

    def is_high_tier_model(self, model: str) -> bool:
        del model
        return False

    def counts_against_high_tier(self, model: str, *, role_tier: str | None = None) -> bool:
        del model, role_tier
        return False


class TaskRunner(Protocol):
    def __call__(self, task: TaskRecord) -> TaskExecutionResult: ...


@dataclass(frozen=True, slots=True)
class TaskExecutionResult:
    artifacts: tuple[BaseModel, ...] = ()
    output_payload: Mapping[str, Any] | None = None
    audit_payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DispatchSummary:
    started: tuple[str, ...]
    completed: tuple[str, ...]
    failed: tuple[str, ...]
    blocked: tuple[str, ...]
    budget_refused: bool


class TaskGraphCycleError(ValueError):
    pass


class _TaskGraphState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_ids: list[str] = Field(default_factory=list)
    edges: dict[str, list[str]] = Field(default_factory=dict)
    failed_reasons: dict[str, str] = Field(default_factory=dict)


class TaskGraph:
    def __init__(
        self,
        case: Case,
        *,
        budget_ledger: BudgetLedgerLike | None = None,
        budget_kind: str = "task_dispatch",
        budget_model: str | None = None,
        enforce_marginal_value_gate: bool = False,
        materiality_weights: Mapping[Level, float] | None = None,
    ) -> None:
        self._case = case
        self._budget_ledger: BudgetLedgerLike = budget_ledger or _PermissiveLedger()
        self._budget_kind = budget_kind
        self._budget_model = budget_model
        self._enforce_marginal_value_gate = enforce_marginal_value_gate
        self._materiality_weights: dict[Level, float] = (
            dict(materiality_weights)
            if materiality_weights is not None
            else {level: float(weight) for level, weight in _LEVEL_WEIGHT.items()}
        )
        self._lock = Lock()
        self._graph = self._load_graph()

    def add_tasks(self, records: Sequence[TaskRecord], edges: EdgeInput | None = None) -> None:
        normalized_edges = self._normalize_edges(edges or {})
        with self._lock:
            current_edges = {task_id: deps[:] for task_id, deps in self._graph.edges.items()}
            current_ids = set(self._graph.task_ids)

            new_records_by_id: dict[str, TaskRecord] = {
                record.task_id: record for record in records
            }
            candidate_ids = current_ids | set(new_records_by_id.keys())
            candidate_edges = self._merge_edges(
                base_edges=current_edges, new_edges=normalized_edges, known_ids=candidate_ids
            )

            cycle = self._find_cycle(candidate_edges, candidate_ids)
            if cycle:
                cycle_str = " -> ".join(cycle)
                raise TaskGraphCycleError(f"Cycle detected: {cycle_str}")

            for record in new_records_by_id.values():
                self._case.write_artifact(record)

            ordered_ids = sorted(candidate_ids)
            self._graph = _TaskGraphState(
                task_ids=ordered_ids,
                edges=candidate_edges,
                failed_reasons=self._graph.failed_reasons,
            )
            self._save_graph_unlocked()

    def ready(self) -> list[TaskRecord]:
        with self._lock:
            return self._ready_unlocked()

    def dispatch(self, runner: TaskRunner, max_concurrent: int) -> DispatchSummary:
        if max_concurrent <= 0:
            raise ValueError("max_concurrent must be > 0")

        started: list[str] = []
        completed: list[str] = []
        failed: list[str] = []
        blocked: set[str] = set()
        marginal_value_refused: set[str] = set()
        budget_refused = False

        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            in_flight: dict[Future[TaskExecutionResult], str] = {}

            while True:
                while len(in_flight) < max_concurrent and not budget_refused:
                    with self._lock:
                        ready = self._ready_unlocked()
                        if not ready:
                            break
                        task = next(
                            (
                                candidate
                                for candidate in ready
                                if candidate.task_id not in marginal_value_refused
                            ),
                            None,
                        )
                        if task is None:
                            break
                        if self._enforce_marginal_value_gate:
                            (
                                gate_passed,
                                gate_payload,
                            ) = self._marginal_value_gate_decision_unlocked(task)
                            if not gate_passed:
                                marginal_value_refused.add(task.task_id)
                                self._audit_unlocked(
                                    event_type="task_marginal_value_refused",
                                    payload=gate_payload,
                                )
                                continue
                        if not self._budget_ledger.try_consume(
                            kind=self._budget_kind, model=self._budget_model
                        ):
                            budget_refused = True
                            self._audit_unlocked(
                                event_type="task_budget_refused", payload={"task_id": task.task_id}
                            )
                            break
                        self._set_task_status_unlocked(task.task_id, TaskStatus.ACTIVE)
                        started.append(task.task_id)
                        self._audit_unlocked(
                            event_type="task_started",
                            payload={"task_id": task.task_id},
                        )

                    future = executor.submit(runner, task)
                    in_flight[future] = task.task_id

                if not in_flight:
                    break

                done, _ = wait(tuple(in_flight), return_when=FIRST_COMPLETED)
                for future in done:
                    task_id = in_flight.pop(future)
                    try:
                        result = future.result()
                    except Exception as exc:
                        with self._lock:
                            blocked_ids = self._mark_failed_and_block_dependents_unlocked(
                                task_id=task_id, error=str(exc)
                            )
                            failed.append(task_id)
                            blocked.update(blocked_ids)
                        continue

                    with self._lock:
                        self._reconcile_success_unlocked(task_id=task_id, result=result)
                        completed.append(task_id)

        return DispatchSummary(
            started=tuple(started),
            completed=tuple(completed),
            failed=tuple(failed),
            blocked=tuple(sorted(blocked)),
            budget_refused=budget_refused,
        )

    def reconcile_orphans(self) -> list[str]:
        """Reset all ``active`` tasks to ``planned`` (safe-resume reconciliation).

        Called after an interrupted run is loaded.  Returns the sorted list of
        task ids that were reset and audits a ``task_reset_on_resume`` event.
        Scans all task records on the blackboard, not just those tracked in the
        graph's ``task_ids`` list, so tasks written outside the graph (e.g. by a
        crashed worker) are still reconciled.
        """
        with self._lock:
            all_records = self._case.list_artifacts(TaskRecord)
            active_ids = [
                record.task_id for record in all_records if record.status is TaskStatus.ACTIVE
            ]
            for task_id in active_ids:
                self._set_task_status_unlocked(task_id, TaskStatus.PLANNED)
            if active_ids:
                self._audit_unlocked(
                    event_type="task_reset_on_resume",
                    payload={"task_ids": sorted(active_ids)},
                )
            return sorted(active_ids)

    def cancel_tasks(
        self,
        task_ids: Iterable[str],
        *,
        include_dependents: bool = False,
        reason: str | None = None,
    ) -> set[str]:
        with self._lock:
            requested = {task_id for task_id in task_ids}
            if include_dependents:
                for task_id in list(requested):
                    requested.update(self._transitive_dependents_unlocked(task_id))

            cancelled: set[str] = set()
            for task_id in sorted(requested):
                record = self._case.read_artifact(TaskRecord, task_id)
                if record.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}:
                    continue
                updated = record.model_copy(update={"status": TaskStatus.CANCELLED})
                self._case.write_artifact(updated)
                cancelled.add(task_id)

            if cancelled:
                self._audit_unlocked(
                    event_type="tasks_cancelled",
                    payload={"task_ids": sorted(cancelled), "reason": reason},
                )
            return cancelled

    def _graph_path(self) -> Path:
        return self._case.root / "shared" / "task_graph.yaml"

    def _task_output_path(self, task_id: str) -> Path:
        return self._case.root / "shared" / "task_outputs" / f"{task_id}.yaml"

    def _load_graph(self) -> _TaskGraphState:
        path = self._graph_path()
        if not path.exists():
            return _TaskGraphState()
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict) or len(loaded) == 0:
            return _TaskGraphState()
        return _TaskGraphState.model_validate(loaded)

    def _save_graph_unlocked(self) -> None:
        normalized_edges = {
            task_id: sorted(set(deps))
            for task_id, deps in self._graph.edges.items()
            if deps or task_id in self._graph.task_ids
        }
        state = _TaskGraphState(
            task_ids=sorted(set(self._graph.task_ids)),
            edges=normalized_edges,
            failed_reasons=dict(sorted(self._graph.failed_reasons.items())),
        )
        self._graph = state
        atomic_write_text(self._graph_path(), dump_model_to_yaml_text(state))

    def _ready_unlocked(self) -> list[TaskRecord]:
        if not self._graph.task_ids:
            return []

        records = [
            self._case.read_artifact(TaskRecord, task_id) for task_id in self._graph.task_ids
        ]
        status_by_id = {record.task_id: record.status for record in records}
        ready: list[TaskRecord] = []
        for record in records:
            if record.status is not TaskStatus.PLANNED:
                continue
            dependencies = self._graph.edges.get(record.task_id, [])
            if all(status_by_id.get(dep_id) is TaskStatus.COMPLETED for dep_id in dependencies):
                ready.append(record)

        ready.sort(key=self._priority_sort_key)
        return ready

    def _priority_sort_key(self, task: TaskRecord) -> tuple[float, str]:
        materiality_weight = self._materiality_weights[task.materiality]
        ordering_score = (
            materiality_weight * task.probability_of_changing_conclusion / task.estimated_cost
        )
        return (-ordering_score, task.task_id)

    def _marginal_value_gate_decision_unlocked(
        self, task: TaskRecord
    ) -> tuple[bool, dict[str, float | str]]:
        materiality_weight = self._materiality_weights[task.materiality]
        probability_of_change = task.probability_of_changing_conclusion
        estimated_cost = task.estimated_cost
        expected_marginal_value = materiality_weight * probability_of_change
        gate_passed = expected_marginal_value > estimated_cost
        payload: dict[str, float | str] = {
            "task_id": task.task_id,
            "materiality_weight": materiality_weight,
            "probability_of_changing_conclusion": probability_of_change,
            "estimated_cost": estimated_cost,
            "expected_marginal_value": expected_marginal_value,
        }
        return gate_passed, payload

    def _set_task_status_unlocked(self, task_id: str, status: TaskStatus) -> None:
        record = self._case.read_artifact(TaskRecord, task_id)
        updated = record.model_copy(update={"status": status})
        self._case.write_artifact(updated)

    def _reconcile_success_unlocked(self, task_id: str, result: TaskExecutionResult) -> None:
        for artifact in result.artifacts:
            if isinstance(artifact, EvidenceBatch):
                unpack_evidence_batch(self._case, artifact)
            elif isinstance(artifact, ObjectionBatch):
                unpack_objection_batch(self._case, artifact, task_id=task_id)
            else:
                self._case.write_artifact(artifact)

        if result.output_payload is not None:
            dumped = yaml.safe_dump(dict(result.output_payload), sort_keys=True)
            atomic_write_text(self._task_output_path(task_id), dumped)

        self._set_task_status_unlocked(task_id, TaskStatus.COMPLETED)
        self._graph.failed_reasons.pop(task_id, None)
        self._save_graph_unlocked()
        payload: dict[str, Any] = {"task_id": task_id}
        payload.update(dict(result.audit_payload))
        self._audit_unlocked(event_type="task_completed", payload=payload)

    def _mark_failed_and_block_dependents_unlocked(self, task_id: str, error: str) -> set[str]:
        self._graph.failed_reasons[task_id] = error
        self._set_task_status_unlocked(task_id, TaskStatus.FAILED)
        blocked = self._transitive_dependents_unlocked(task_id)
        for dependent_id in sorted(blocked):
            record = self._case.read_artifact(TaskRecord, dependent_id)
            if record.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}:
                continue
            updated = record.model_copy(update={"status": TaskStatus.BLOCKED})
            self._case.write_artifact(updated)
        self._save_graph_unlocked()
        self._audit_unlocked(
            event_type="task_failed",
            payload={
                "task_id": task_id,
                "error": error,
                "blocked_dependents": sorted(blocked),
            },
        )
        return blocked

    def _transitive_dependents_unlocked(self, task_id: str) -> set[str]:
        reverse_edges: dict[str, set[str]] = {node_id: set() for node_id in self._graph.task_ids}
        for node_id, dependencies in self._graph.edges.items():
            for dependency in dependencies:
                reverse_edges.setdefault(dependency, set()).add(node_id)

        visited: set[str] = set()
        stack = [task_id]
        while stack:
            current = stack.pop()
            for dependent in reverse_edges.get(current, set()):
                if dependent in visited:
                    continue
                visited.add(dependent)
                stack.append(dependent)
        return visited

    def _merge_edges(
        self, base_edges: dict[str, list[str]], new_edges: dict[str, list[str]], known_ids: set[str]
    ) -> dict[str, list[str]]:
        merged: dict[str, list[str]] = {}
        for task_id in sorted(known_ids):
            merged[task_id] = sorted(set(base_edges.get(task_id, [])))

        for task_id, dependencies in new_edges.items():
            if task_id not in known_ids:
                raise ValueError(f"Unknown task in edge definition: {task_id}")
            unknown_dependencies = sorted(
                {dep_id for dep_id in dependencies if dep_id not in known_ids}
            )
            if unknown_dependencies:
                missing = ", ".join(unknown_dependencies)
                raise ValueError(f"Unknown dependency for {task_id}: {missing}")
            merged[task_id] = sorted(set(dependencies))
        return merged

    def _normalize_edges(self, edges: EdgeInput) -> dict[str, list[str]]:
        if isinstance(edges, Mapping):
            return {
                str(task_id): [str(dep_id) for dep_id in dependencies]
                for task_id, dependencies in edges.items()
            }
        normalized: dict[str, list[str]] = {}
        for task_id, dependency in edges:
            normalized.setdefault(str(task_id), []).append(str(dependency))
        return normalized

    def _find_cycle(self, edges: dict[str, list[str]], node_ids: set[str]) -> list[str]:
        visited: set[str] = set()
        active: set[str] = set()
        path: list[str] = []

        def dfs(node_id: str) -> list[str] | None:
            visited.add(node_id)
            active.add(node_id)
            path.append(node_id)

            for dependency in edges.get(node_id, []):
                if dependency not in visited:
                    cycle = dfs(dependency)
                    if cycle:
                        return cycle
                elif dependency in active:
                    cycle_start = path.index(dependency)
                    return path[cycle_start:] + [dependency]

            active.remove(node_id)
            path.pop()
            return None

        for node_id in sorted(node_ids):
            if node_id in visited:
                continue
            cycle = dfs(node_id)
            if cycle:
                return cycle
        return []

    def _audit_unlocked(self, event_type: str, payload: Mapping[str, Any]) -> None:
        event = AuditEvent(
            ts=datetime.now(UTC),
            actor="task_graph",
            event_type=event_type,
            payload=dict(payload),
        )
        self._case.audit(event)
