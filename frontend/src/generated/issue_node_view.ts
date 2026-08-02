/* Generated from issue_node_view.schema.json. Do not edit manually. */

export type Covered = boolean;
export type Materiality = string;
export type NodeId = string;
export type NodeType = string;
export type ParentId = string | null;
export type Question = string;
export type ResolutionCriteria = string;

export interface IssueNodeView {
  covered?: Covered;
  materiality: Materiality;
  node_id: NodeId;
  node_type: NodeType;
  parent_id?: ParentId;
  question: Question;
  resolution_criteria: ResolutionCriteria;
}
