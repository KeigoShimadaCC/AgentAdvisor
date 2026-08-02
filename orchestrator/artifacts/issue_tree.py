from __future__ import annotations

from collections import Counter
from enum import StrEnum

from pydantic import Field, model_validator

from orchestrator.artifacts.common import (
    ArtifactModel,
    IssueNodeId,
    Level,
    NonEmptyStr,
)


class IssueNodeType(StrEnum):
    ROOT = "root"
    DRIVER = "driver"
    SUB_QUESTION = "sub_question"


class IssueNode(ArtifactModel):
    node_id: IssueNodeId
    parent_id: IssueNodeId | None = None
    question: NonEmptyStr
    node_type: IssueNodeType
    materiality: Level
    resolution_criteria: NonEmptyStr


class IssueTree(ArtifactModel):
    """MECE decomposition of the decision into sub-questions.

    Tasks hang off leaf nodes, which turns "did we investigate enough" from a
    judgement call into a coverage ratio.
    """

    decision_question: NonEmptyStr
    nodes: list[IssueNode] = Field(min_length=2)
    mece_justification: NonEmptyStr

    @model_validator(mode="after")
    def validate_tree_shape(self) -> IssueTree:
        duplicate_ids = sorted(
            node_id
            for node_id, count in Counter(node.node_id for node in self.nodes).items()
            if count > 1
        )
        if duplicate_ids:
            raise ValueError(f"nodes contains duplicate node_ids: {duplicate_ids}")

        by_id = {node.node_id: node for node in self.nodes}

        roots = [node for node in self.nodes if node.parent_id is None]
        if len(roots) != 1:
            raise ValueError(
                f"issue tree must have exactly one root node (parent_id null), found {len(roots)}."
            )
        if roots[0].node_type is not IssueNodeType.ROOT:
            raise ValueError("the node without a parent must have node_type 'root'.")

        for node in self.nodes:
            if node.parent_id is None:
                continue
            if node.parent_id not in by_id:
                raise ValueError(
                    f"node '{node.node_id}' references unknown parent '{node.parent_id}'."
                )
            if node.node_type is IssueNodeType.ROOT:
                raise ValueError(f"node '{node.node_id}' has a parent but node_type 'root'.")

        for node in self.nodes:
            seen: set[str] = set()
            cursor = node
            while cursor.parent_id is not None:
                if cursor.node_id in seen:
                    raise ValueError(f"issue tree contains a cycle through '{cursor.node_id}'.")
                seen.add(cursor.node_id)
                cursor = by_id[cursor.parent_id]

        return self

    def leaf_node_ids(self) -> list[str]:
        parents = {node.parent_id for node in self.nodes if node.parent_id is not None}
        return [node.node_id for node in self.nodes if node.node_id not in parents]
