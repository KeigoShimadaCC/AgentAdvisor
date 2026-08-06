/* Generated from decision_spec.schema.json. Do not edit manually. */

/**
 * @minItems 1
 */
export type Alternatives = [string, ...string[]];
export type Constraints = string[];
export type Deadline = string;
export type DecisionId = string;
export type Depth = 'light' | 'standard' | 'deep';
export type ObjectiveWeights = {
  [k: string]: number;
} | null;
/**
 * @minItems 1
 */
export type Objectives = [string, ...string[]];
export type Owner = string;
export type Question = string;
export type Reversibility = 'fully_reversible' | 'partially_reversible' | 'irreversible';
export type RiskTolerance = 'low' | 'moderate' | 'high';
export type SchemaVersion = number;

export interface DecisionSpec {
  alternatives: Alternatives;
  constraints?: Constraints;
  deadline: Deadline;
  decision_id: DecisionId;
  depth: Depth;
  objective_weights?: ObjectiveWeights;
  objectives: Objectives;
  owner: Owner;
  question: Question;
  reversibility: Reversibility;
  risk_tolerance: RiskTolerance;
  schema_version?: SchemaVersion;
}
