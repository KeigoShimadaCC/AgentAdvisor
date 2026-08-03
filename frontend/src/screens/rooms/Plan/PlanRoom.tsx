import { useMemo } from "react";
import { RoomShell } from "../../shared/RoomShell";
import { CoverageBar } from "../../shared/CoverageBar";
import { HonestEmpty } from "../../shared/HonestEmpty";
import type { CaseView, IssueNodeView } from "../../../generated/case_view";
import { nodeTypeLabel, levelLabel, ROOMS } from "../../../copy/terms";

export function PlanRoom() {
  return (
    <RoomShell room="plan">
      {(view) => <PlanBody view={view} />}
    </RoomShell>
  );
}

function PlanBody({ view }: { view: CaseView }) {
  const plan = view.rooms?.plan ?? null;

  if (!plan) {
    return (
      <HonestEmpty
        truth="not_yet"
        heading={`${ROOMS.plan.label}: not yet — the question tree has not been built for this case.`}
      />
    );
  }

  const nodes = plan.nodes ?? [];
  const leafNodes = nodes.filter((n) => !nodes.some((c) => c.parent_id === n.node_id));
  const coveredLeaves = leafNodes.filter((n) => n.covered).length;
  const totalLeaves = leafNodes.length;

  // Build a tree from the flat node list.
  const tree = useMemo(() => buildTree(nodes), [nodes]);

  return (
    <div className="plan-room">
      <section className="plan-decision-question">
        <h3>Decision question</h3>
        <p>{plan.decision_question}</p>
      </section>

      <section className="plan-coverage">
        <h3>Coverage</h3>
        <CoverageBar
          fraction={plan.coverage_fraction ?? 0}
          covered={coveredLeaves}
          total={totalLeaves}
        />
      </section>

      {plan.mece_justification && (
        <section className="plan-mece">
          <h3>Why this covers the decision</h3>
          <p>{plan.mece_justification}</p>
        </section>
      )}

      <section className="plan-tree" aria-label="Question tree">
        <h3>Question tree</h3>
        <ul className="tree-root" role="tree">
          {tree.map((node) => (
            <TreeNode key={node.node.node_id} node={node} depth={0} />
          ))}
        </ul>
      </section>
    </div>
  );
}

interface TreeNodeData {
  node: IssueNodeView;
  children: TreeNodeData[];
}

function buildTree(nodes: IssueNodeView[]): TreeNodeData[] {
  const byId = new Map<string, TreeNodeData>();
  for (const n of nodes) byId.set(n.node_id, { node: n, children: [] });
  const roots: TreeNodeData[] = [];
  for (const n of nodes) {
    const data = byId.get(n.node_id)!;
    if (n.parent_id && byId.has(n.parent_id)) {
      byId.get(n.parent_id)!.children.push(data);
    } else {
      roots.push(data);
    }
  }
  return roots;
}

interface TreeNodeProps {
  node: TreeNodeData;
  depth: number;
}

function TreeNode({ node, depth }: TreeNodeProps) {
  const hasChildren = node.children.length > 0;
  return (
    <li role="treeitem" aria-expanded={hasChildren ? true : undefined} className={`tree-node tree-node-${node.node.node_type}`}>
      <div className="tree-node-head" style={{ paddingLeft: `${depth * 1.25}rem` }}>
        <span className="tree-node-type">{nodeTypeLabel(node.node.node_type)}</span>
        <span className={`tree-node-question${node.node.covered ? "" : " tree-node-uncovered"}`}>
          {node.node.question}
        </span>
        {!node.node.covered && <span className="tree-node-coverage-mark">uncovered</span>}
      </div>
      <div className="tree-node-detail">
        <span className="tree-node-materiality">{levelLabel(node.node.materiality)} materiality</span>
        <span className="tree-node-criteria">
          Resolved when: {node.node.resolution_criteria}
        </span>
      </div>
      {hasChildren && (
        <ul role="group" className="tree-children">
          {node.children.map((child) => (
            <TreeNode key={child.node.node_id} node={child} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  );
}
