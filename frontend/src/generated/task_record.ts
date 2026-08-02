/* Generated from task_record.schema.json. Do not edit manually. */

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
  | 'synthesizer'
  | 'reviewer'
  | 'specialist';
export type SchemaVersion = number;
export type TaskStatus = 'planned' | 'active' | 'completed' | 'failed' | 'blocked' | 'cancelled';
export type TaskId = string;
export type WhyItMatters = string;

export interface TaskRecord {
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
  schema_version?: SchemaVersion;
  status: TaskStatus;
  task_id: TaskId;
  why_it_matters: WhyItMatters;
}
