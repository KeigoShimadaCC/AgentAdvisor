from __future__ import annotations

import random
import threading
import time
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import Level, PriorityLevel, TaskRecord, TaskRole, TaskStatus
from orchestrator.case_store import Case, create_case
from orchestrator.task_graph import TaskExecutionResult, TaskGraph, TaskGraphCycleError


class _AlwaysAllowLedger:
    def try_consume(self, kind: str, model: str | None = None) -> bool:
        del kind, model
        return True


class _RefusingLedger:
    def try_consume(self, kind: str, model: str | None = None) -> bool:
        del kind, model
        return False


def _task(
    task_id: str,
    *,
    status: TaskStatus = TaskStatus.PLANNED,
    materiality: Level = Level.MEDIUM,
    expected_information_gain: Level = Level.MEDIUM,
    probability_of_changing_conclusion: float = 0.5,
    estimated_cost: float = 1.0,
    priority_score: int = 50,
    priority: PriorityLevel = PriorityLevel.MEDIUM,
) -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        role=TaskRole.RESEARCHER,
        question=f"question-{task_id}",
        why_it_matters=f"why-{task_id}",
        expected_information_gain=expected_information_gain,
        materiality=materiality,
        probability_of_changing_conclusion=probability_of_changing_conclusion,
        estimated_cost=estimated_cost,
        inputs=["shared/decision_spec.yaml"],
        required_output="evidence",
        completion_criteria="done",
        status=status,
        priority=priority,
        priority_score=priority_score,
        priority_rationale="rationale",
    )


def _new_graph(tmp_path: Path, slug: str = "task-graph") -> tuple[Case, TaskGraph]:
    case = create_case(slug, cases_root=tmp_path)
    graph = TaskGraph(case, budget_ledger=_AlwaysAllowLedger())
    return case, graph


def test_dependency_ordering_under_concurrency_with_randomized_durations(
    tmp_path: Path,
) -> None:
    for seed in range(20):
        _, graph = _new_graph(tmp_path, slug=f"dep-order-{seed}")
        tasks = [_task("T-001"), _task("T-002"), _task("T-003"), _task("T-004")]
        graph.add_tasks(
            tasks,
            edges={
                "T-002": ["T-001"],
                "T-003": ["T-002"],
                "T-004": ["T-001"],
            },
        )

        timings: dict[str, tuple[float, float]] = {}
        lock = threading.Lock()
        rng = random.Random(seed)

        def runner(
            task: TaskRecord,
            *,
            rng: random.Random = rng,
            lock: threading.Lock = lock,
            timings: dict[str, tuple[float, float]] = timings,
        ) -> TaskExecutionResult:
            start = time.perf_counter()
            time.sleep(rng.uniform(0.001, 0.02))
            end = time.perf_counter()
            with lock:
                timings[task.task_id] = (start, end)
            return TaskExecutionResult(output_payload={"task_id": task.task_id})

        summary = graph.dispatch(runner, max_concurrent=3)
        assert sorted(summary.completed) == ["T-001", "T-002", "T-003", "T-004"]

        assert timings["T-002"][0] >= timings["T-001"][1]
        assert timings["T-003"][0] >= timings["T-002"][1]
        assert timings["T-004"][0] >= timings["T-001"][1]


def test_concurrency_cap_max_three(tmp_path: Path) -> None:
    _, graph = _new_graph(tmp_path, slug="concurrency-cap")
    graph.add_tasks([_task(f"T-{index:03d}") for index in range(1, 13)])

    state_lock = threading.Lock()
    in_flight = 0
    max_seen = 0

    def runner(task: TaskRecord) -> TaskExecutionResult:
        nonlocal in_flight, max_seen
        del task
        with state_lock:
            in_flight += 1
            max_seen = max(max_seen, in_flight)
        time.sleep(0.01)
        with state_lock:
            in_flight -= 1
        return TaskExecutionResult()

    summary = graph.dispatch(runner, max_concurrent=3)
    assert len(summary.completed) == 12
    assert max_seen <= 3


def test_task_status_failed_round_trip(tmp_path: Path) -> None:
    case, graph = _new_graph(tmp_path, slug="task-status-failed")
    graph.add_tasks([_task("T-001", status=TaskStatus.FAILED)])

    loaded = case.read_artifact(TaskRecord, "T-001")
    assert loaded.status is TaskStatus.FAILED


def test_failure_blocks_transitive_dependents_and_independent_branch_completes(
    tmp_path: Path,
) -> None:
    case, graph = _new_graph(tmp_path, slug="failure-propagation")
    graph.add_tasks(
        [
            _task("T-001"),
            _task("T-002"),
            _task("T-003"),
            _task("T-004"),
            _task("T-005"),
        ],
        edges={
            "T-002": ["T-001"],
            "T-003": ["T-002"],
            "T-005": ["T-004"],
        },
    )

    def runner(task: TaskRecord) -> TaskExecutionResult:
        if task.task_id == "T-002":
            raise RuntimeError("runner boom")
        return TaskExecutionResult()

    summary = graph.dispatch(runner, max_concurrent=3)
    assert "T-002" in summary.failed
    assert set(summary.blocked) == {"T-003"}
    assert {"T-001", "T-004", "T-005"}.issubset(set(summary.completed))

    failed = case.read_artifact(TaskRecord, "T-002")
    blocked = case.read_artifact(TaskRecord, "T-003")
    independent = case.read_artifact(TaskRecord, "T-005")
    assert failed.status is TaskStatus.FAILED
    assert blocked.status is TaskStatus.BLOCKED
    assert independent.status is TaskStatus.COMPLETED


def test_cycle_addition_rejected_and_graph_unchanged(tmp_path: Path) -> None:
    case, graph = _new_graph(tmp_path, slug="cycle-reject")
    graph.add_tasks([_task("T-001"), _task("T-002")], edges={"T-002": ["T-001"]})
    before_graph = (case.root / "shared" / "task_graph.yaml").read_text(encoding="utf-8")

    with pytest.raises(TaskGraphCycleError, match=r"Cycle detected: T-001 -> T-003 -> T-001"):
        graph.add_tasks([_task("T-003")], edges={"T-001": ["T-003"], "T-003": ["T-001"]})

    after_graph = (case.root / "shared" / "task_graph.yaml").read_text(encoding="utf-8")
    assert before_graph == after_graph
    assert not (case.root / "shared" / "tasks" / "T-003.yaml").exists()


def test_priority_ordering_deterministic_across_runs(tmp_path: Path) -> None:
    _, graph = _new_graph(tmp_path, slug="priority-order")
    graph.add_tasks(
        [
            _task(
                "T-010",
                materiality=Level.HIGH,
                expected_information_gain=Level.HIGH,
                probability_of_changing_conclusion=0.4,
                estimated_cost=2.0,
                priority_score=70,
                priority=PriorityLevel.HIGH,
            ),
            _task(
                "T-005",
                materiality=Level.HIGH,
                expected_information_gain=Level.MEDIUM,
                probability_of_changing_conclusion=0.5,
                estimated_cost=1.0,
                priority_score=90,
                priority=PriorityLevel.HIGH,
            ),
            _task(
                "T-001",
                materiality=Level.LOW,
                expected_information_gain=Level.MEDIUM,
                probability_of_changing_conclusion=0.9,
                estimated_cost=1.0,
                priority_score=10,
                priority=PriorityLevel.LOW,
            ),
            _task(
                "T-002",
                materiality=Level.LOW,
                expected_information_gain=Level.HIGH,
                probability_of_changing_conclusion=0.9,
                estimated_cost=1.0,
                priority_score=90,
                priority=PriorityLevel.HIGH,
            ),
            _task(
                "T-003",
                materiality=Level.HIGH,
                expected_information_gain=Level.HIGH,
                probability_of_changing_conclusion=0.9,
                estimated_cost=10.0,
                priority_score=100,
                priority=PriorityLevel.LOW,
            ),
        ]
    )

    expected = ["T-005", "T-001", "T-002", "T-010", "T-003"]
    for _ in range(10):
        assert [task.task_id for task in graph.ready()] == expected


def test_marginal_value_gate_refuses_dispatch_and_audits_numbers(tmp_path: Path) -> None:
    case = create_case("marginal-value-refusal", cases_root=tmp_path)
    graph = TaskGraph(
        case,
        enforce_marginal_value_gate=True,
        budget_ledger=_AlwaysAllowLedger(),
    )
    graph.add_tasks(
        [
            _task(
                "T-001",
                materiality=Level.MEDIUM,
                probability_of_changing_conclusion=0.4,
                estimated_cost=1.0,
            )
        ]
    )

    def runner(task: TaskRecord) -> TaskExecutionResult:
        raise AssertionError(f"runner should not be called for {task.task_id}")

    summary = graph.dispatch(runner, max_concurrent=1)
    assert summary.started == ()
    assert summary.completed == ()

    record = case.read_artifact(TaskRecord, "T-001")
    assert record.status is TaskStatus.PLANNED

    audit_lines = (case.root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    events = [yaml.safe_load(line) for line in audit_lines]
    refusal_events = [
        event for event in events if event["event_type"] == "task_marginal_value_refused"
    ]
    assert len(refusal_events) == 1
    assert refusal_events[0]["payload"] == {
        "task_id": "T-001",
        "materiality_weight": 2.0,
        "probability_of_changing_conclusion": 0.4,
        "estimated_cost": 1.0,
        "expected_marginal_value": 0.8,
    }


def test_marginal_value_gate_dispatches_above_threshold(tmp_path: Path) -> None:
    case = create_case("marginal-value-pass", cases_root=tmp_path)
    graph = TaskGraph(
        case,
        enforce_marginal_value_gate=True,
        budget_ledger=_AlwaysAllowLedger(),
    )
    graph.add_tasks(
        [
            _task(
                "T-001",
                materiality=Level.HIGH,
                probability_of_changing_conclusion=0.8,
                estimated_cost=2.0,
            )
        ]
    )

    def runner(task: TaskRecord) -> TaskExecutionResult:
        return TaskExecutionResult(output_payload={"task_id": task.task_id})

    summary = graph.dispatch(runner, max_concurrent=1)
    assert summary.started == ("T-001",)
    assert summary.completed == ("T-001",)

    record = case.read_artifact(TaskRecord, "T-001")
    assert record.status is TaskStatus.COMPLETED


def test_marginal_value_gate_can_be_disabled(tmp_path: Path) -> None:
    case = create_case("marginal-value-disabled", cases_root=tmp_path)
    graph = TaskGraph(
        case,
        enforce_marginal_value_gate=False,
        budget_ledger=_AlwaysAllowLedger(),
    )
    graph.add_tasks(
        [
            _task(
                "T-001",
                materiality=Level.MEDIUM,
                probability_of_changing_conclusion=0.4,
                estimated_cost=1.0,
            )
        ]
    )

    def runner(task: TaskRecord) -> TaskExecutionResult:
        return TaskExecutionResult(output_payload={"task_id": task.task_id})

    summary = graph.dispatch(runner, max_concurrent=1)
    assert summary.started == ("T-001",)
    assert summary.completed == ("T-001",)


def test_budget_refusal_leaves_tasks_planned_and_dispatch_returns_cleanly(tmp_path: Path) -> None:
    case = create_case("budget-refusal", cases_root=tmp_path)
    graph = TaskGraph(case, budget_ledger=_RefusingLedger())
    graph.add_tasks([_task("T-001"), _task("T-002")])

    def runner(task: TaskRecord) -> TaskExecutionResult:
        del task
        return TaskExecutionResult()

    summary = graph.dispatch(runner, max_concurrent=2)
    assert summary.budget_refused is True
    assert summary.started == ()

    first = case.read_artifact(TaskRecord, "T-001")
    second = case.read_artifact(TaskRecord, "T-002")
    assert first.status is TaskStatus.PLANNED
    assert second.status is TaskStatus.PLANNED


def test_reconciliation_writes_outputs_and_emits_audit_event(tmp_path: Path) -> None:
    case, graph = _new_graph(tmp_path, slug="reconcile")
    graph.add_tasks([_task("T-001")])

    def runner(task: TaskRecord) -> TaskExecutionResult:
        return TaskExecutionResult(
            output_payload={"worker": task.task_id, "result": {"ok": True}},
            audit_payload={"runner": "stub"},
        )

    summary = graph.dispatch(runner, max_concurrent=1)
    assert summary.completed == ("T-001",)

    output_path = case.root / "shared" / "task_outputs" / "T-001.yaml"
    assert output_path.exists()
    output_data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    assert output_data == {"result": {"ok": True}, "worker": "T-001"}

    audit_path = case.root / "audit.jsonl"
    lines = [line for line in audit_path.read_text(encoding="utf-8").splitlines() if line]
    completed_events = [yaml.safe_load(line) for line in lines if "task_completed" in line]
    assert len(completed_events) == 1
    assert completed_events[0]["event_type"] == "task_completed"
    assert completed_events[0]["payload"]["task_id"] == "T-001"
