"""Issue-tree coverage: how much of the decomposed problem has actually been worked.

Turns "have we investigated enough" from a judgement call into a ratio the stop
evaluator can read.
"""

from __future__ import annotations

from dataclasses import dataclass

from orchestrator.artifacts import IssueTree, TaskRecord, TaskStatus


@dataclass(frozen=True, slots=True)
class IssueCoverage:
    leaf_count: int
    covered_leaf_count: int
    covered_share: float
    uncovered_node_ids: tuple[str, ...]
    unattached_task_ids: tuple[str, ...]


def compute_coverage(tree: IssueTree, tasks: list[TaskRecord]) -> IssueCoverage:
    leaves = tree.leaf_node_ids()
    node_ids = {node.node_id for node in tree.nodes}

    completed_nodes: set[str] = set()
    unattached: list[str] = []
    for task in tasks:
        if task.issue_node_id is None:
            unattached.append(task.task_id)
            continue
        if task.status is TaskStatus.COMPLETED:
            completed_nodes.add(task.issue_node_id)

    # A completed task on an inner node covers every leaf beneath it.
    parent_by_id = {node.node_id: node.parent_id for node in tree.nodes}

    def covers(leaf_id: str) -> bool:
        cursor: str | None = leaf_id
        while cursor is not None and cursor in node_ids:
            if cursor in completed_nodes:
                return True
            cursor = parent_by_id.get(cursor)
        return False

    covered = [leaf_id for leaf_id in leaves if covers(leaf_id)]
    uncovered = [leaf_id for leaf_id in leaves if leaf_id not in covered]
    share = len(covered) / len(leaves) if leaves else 0.0

    return IssueCoverage(
        leaf_count=len(leaves),
        covered_leaf_count=len(covered),
        covered_share=round(share, 4),
        uncovered_node_ids=tuple(uncovered),
        unattached_task_ids=tuple(unattached),
    )
