/* Generated from issue_tree.schema.json. Do not edit manually. */

export type DecisionQuestion = string;
export type MeceJustification = string;
/**
 * @minItems 2
 */
export type Nodes = [IssueNode, IssueNode, ...IssueNode[]];
export type Level = 'high' | 'medium' | 'low';
export type NodeId = string;
export type IssueNodeType = 'root' | 'driver' | 'sub_question';
export type ParentId = string | null;
export type Question = string;
export type ResolutionCriteria = string;
export type SchemaVersion = number;
export type SchemaVersion1 = number;

/**
 * MECE decomposition of the decision into sub-questions.
 *
 * Tasks hang off leaf nodes, which turns "did we investigate enough" from a
 * judgement call into a coverage ratio.
 */
export interface IssueTree {
  decision_question: DecisionQuestion;
  mece_justification: MeceJustification;
  nodes: Nodes;
  schema_version?: SchemaVersion1;
}
export interface IssueNode {
  materiality: Level;
  node_id: NodeId;
  node_type: IssueNodeType;
  parent_id?: ParentId;
  question: Question;
  resolution_criteria: ResolutionCriteria;
  schema_version?: SchemaVersion;
}
