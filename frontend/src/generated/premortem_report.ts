/* Generated from premortem_report.schema.json. Do not edit manually. */

export type AssumedOutcome = string;
/**
 * @minItems 1
 */
export type FailureModes = [FailureMode, ...FailureMode[]];
export type FailureMode1 = string;
/**
 * @minItems 1
 */
export type LeadingIndicators = [string, ...string[]];
export type Narrative = string;
export type PreventiveAction = string;
export type Delta = number;
export type Description = string;
/**
 * @minItems 1
 */
export type EvidenceIds = [string, ...string[]];
export type SchemaVersion = number;
export type Adjustments = ProbabilityAdjustment[];
export type BaseRate = number | null;
export type IntervalHigh = number | null;
export type IntervalLow = number | null;
export type ProbabilityMethod = 'reference_class' | 'scenario_model' | 'structured_subjective';
export type Point = number | null;
export type ReferenceClass = string | null;
export type SchemaVersion1 = number;
export type ReferencedAssumptionIds = string[];
export type ReferencedEvidenceIds = string[];
export type SchemaVersion2 = number;
export type Level = 'high' | 'medium' | 'low';
export type Horizon = string;
export type MostLikelyFailureMode = string;
export type SchemaVersion3 = number;

/**
 * Prospective hindsight: assume the recommendation was taken and it failed.
 *
 * Distinct from the Challenger, which attacks the reasoning as it stands. This
 * attacks the future, and its leading indicators become change-triggers.
 */
export interface PreMortemReport {
  assumed_outcome: AssumedOutcome;
  failure_modes: FailureModes;
  horizon: Horizon;
  most_likely_failure_mode: MostLikelyFailureMode;
  schema_version?: SchemaVersion3;
}
export interface FailureMode {
  failure_mode: FailureMode1;
  leading_indicators: LeadingIndicators;
  narrative: Narrative;
  preventive_action: PreventiveAction;
  probability: ProbabilityEstimate;
  referenced_assumption_ids?: ReferencedAssumptionIds;
  referenced_evidence_ids?: ReferencedEvidenceIds;
  schema_version?: SchemaVersion2;
  severity: Level;
}
export interface ProbabilityEstimate {
  adjustments?: Adjustments;
  base_rate?: BaseRate;
  interval_high?: IntervalHigh;
  interval_low?: IntervalLow;
  method: ProbabilityMethod;
  point?: Point;
  reference_class?: ReferenceClass;
  schema_version?: SchemaVersion1;
}
export interface ProbabilityAdjustment {
  delta: Delta;
  description: Description;
  evidence_ids: EvidenceIds;
  schema_version?: SchemaVersion;
}
