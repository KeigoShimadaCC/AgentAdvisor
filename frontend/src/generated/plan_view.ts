/* Generated from plan_view.schema.json. Do not edit manually. */

export type CoverageFraction = number;
export type DecisionQuestion = string;
export type MeceJustification = string;
export type Covered = boolean;
export type Materiality = string;
export type NodeId = string;
export type NodeType = string;
export type ParentId = string | null;
export type Question = string;
export type ResolutionCriteria = string;
export type Nodes = IssueNodeView[];

export interface PlanView {
  coverage_fraction?: CoverageFraction;
  decision_question: DecisionQuestion;
  mece_justification?: MeceJustification;
  nodes?: Nodes;
}
export interface IssueNodeView {
  covered?: Covered;
  materiality: Materiality;
  node_id: NodeId;
  node_type: NodeType;
  parent_id?: ParentId;
  question: Question;
  resolution_criteria: ResolutionCriteria;
}
