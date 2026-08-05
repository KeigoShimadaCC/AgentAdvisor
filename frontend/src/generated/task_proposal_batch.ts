/* Generated from task_proposal_batch.schema.json. Do not edit manually. */

export type PlanningMode = 'initial' | 'repair';
export type DependsOnIndices = number[];
export type ResolvesObjections = string[];
export type SchemaVersion = number;
export type CompletionCriteria = string;
/**
 * Estimated cost in expected agent-invocation units.
 */
export type EstimatedCost = number;
export type Level = 'high' | 'medium' | 'low';
/**
 * @minItems 1
 */
export type Inputs = [string, ...string[]];
export type IssueNodeId = string | null;
export type PriorityLevel = 'high' | 'medium' | 'low';
export type PriorityRationale = string;
export type PriorityScore = number;
/**
 * Estimated probability that this task's output changes the recommendation.
 */
export type ProbabilityOfChangingConclusion = number;
export type Question = string;
export type RequiredOutput = string;
export type TaskRole =
  | 'intake'
  | 'planner'
  | 'director'
  | 'structurer'
  | 'challenger'
  | 'premortem'
  | 'auditor'
  | 'researcher'
  | 'analyst'
  | 'assumption_analyst'
  | 'ach'
  | 'monitor'
  | 'synthesizer'
  | 'reviewer'
  | 'specialist';
export type SchemaVersion1 = number;
export type WhyItMatters = string;
export type Proposals = TaskProposal[];
export type SchemaVersion2 = number;

export interface TaskProposalBatch {
  mode: PlanningMode;
  proposals?: Proposals;
  schema_version?: SchemaVersion2;
}
export interface TaskProposal {
  depends_on_indices?: DependsOnIndices;
  resolves_objections?: ResolvesObjections;
  schema_version?: SchemaVersion;
  task: TaskProposalRecord;
}
export interface TaskProposalRecord {
  completion_criteria: CompletionCriteria;
  estimated_cost?: EstimatedCost;
  expected_information_gain: Level;
  inputs: Inputs;
  issue_node_id?: IssueNodeId;
  materiality: Level;
  priority: PriorityLevel;
  priority_rationale: PriorityRationale;
  priority_score: PriorityScore;
  probability_of_changing_conclusion?: ProbabilityOfChangingConclusion;
  question: Question;
  required_output: RequiredOutput;
  role: TaskRole;
  schema_version?: SchemaVersion1;
  why_it_matters: WhyItMatters;
}
