from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator.artifacts import (
    IssueNode,
    IssueNodeType,
    IssueTree,
    Level,
    PriorityLevel,
    TaskRecord,
    TaskRole,
    TaskStatus,
)
from orchestrator.issue_tree import compute_coverage


def _node(
    node_id: str,
    parent_id: str | None,
    node_type: IssueNodeType = IssueNodeType.SUB_QUESTION,
) -> IssueNode:
    return IssueNode(
        node_id=node_id,
        parent_id=parent_id,
        question=f"Question {node_id}",
        node_type=node_type,
        materiality=Level.MEDIUM,
        resolution_criteria=f"Criteria for {node_id}",
    )


def _tree() -> IssueTree:
    return IssueTree(
        decision_question="Root decision",
        nodes=[
            _node("Q-1", None, IssueNodeType.ROOT),
            _node("Q-1.1", "Q-1", IssueNodeType.DRIVER),
            _node("Q-1.2", "Q-1", IssueNodeType.DRIVER),
            _node("Q-1.1.1", "Q-1.1"),
            _node("Q-1.1.2", "Q-1.1"),
        ],
        mece_justification="Two drivers exhaust the decision; tax is out of scope.",
    )


def _task(
    task_id: str, node_id: str | None, status: TaskStatus = TaskStatus.COMPLETED
) -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        role=TaskRole.RESEARCHER,
        issue_node_id=node_id,
        question=f"Investigate {node_id}",
        why_it_matters="It bears on the decision.",
        expected_information_gain=Level.HIGH,
        materiality=Level.HIGH,
        probability_of_changing_conclusion=0.5,
        estimated_cost=1.0,
        inputs=["decision_spec"],
        required_output="evidence_batch",
        completion_criteria="Sources found",
        status=status,
        priority=PriorityLevel.HIGH,
        priority_score=50,
        priority_rationale="Material",
    )


def test_leaves_are_the_nodes_without_children() -> None:
    assert _tree().leaf_node_ids() == ["Q-1.2", "Q-1.1.1", "Q-1.1.2"]


def test_coverage_is_zero_when_no_task_is_attached() -> None:
    coverage = compute_coverage(_tree(), [_task("T-001", None)])

    assert coverage.leaf_count == 3
    assert coverage.covered_leaf_count == 0
    assert coverage.covered_share == 0.0
    assert coverage.unattached_task_ids == ("T-001",)


def test_completed_task_covers_its_leaf_only() -> None:
    coverage = compute_coverage(_tree(), [_task("T-001", "Q-1.1.1")])

    assert coverage.covered_leaf_count == 1
    assert coverage.covered_share == pytest.approx(1 / 3, abs=1e-4)
    assert set(coverage.uncovered_node_ids) == {"Q-1.2", "Q-1.1.2"}


def test_completed_task_on_inner_node_covers_every_leaf_beneath_it() -> None:
    coverage = compute_coverage(_tree(), [_task("T-001", "Q-1.1")])

    assert set(coverage.uncovered_node_ids) == {"Q-1.2"}
    assert coverage.covered_leaf_count == 2


def test_incomplete_task_does_not_count_as_coverage() -> None:
    coverage = compute_coverage(_tree(), [_task("T-001", "Q-1.1.1", status=TaskStatus.ACTIVE)])
    assert coverage.covered_leaf_count == 0


def test_full_coverage_reports_one() -> None:
    coverage = compute_coverage(
        _tree(),
        [
            _task("T-001", "Q-1.1"),
            _task("T-002", "Q-1.2"),
        ],
    )
    assert coverage.covered_share == 1.0
    assert coverage.uncovered_node_ids == ()


def test_tree_with_two_roots_is_rejected() -> None:
    with pytest.raises(ValidationError, match="exactly one root"):
        IssueTree(
            decision_question="Root decision",
            nodes=[
                _node("Q-1", None, IssueNodeType.ROOT),
                _node("Q-2", None, IssueNodeType.ROOT),
            ],
            mece_justification="Invalid",
        )


def test_tree_with_unknown_parent_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown parent"):
        IssueTree(
            decision_question="Root decision",
            nodes=[
                _node("Q-1", None, IssueNodeType.ROOT),
                _node("Q-1.1", "Q-9"),
            ],
            mece_justification="Invalid",
        )
