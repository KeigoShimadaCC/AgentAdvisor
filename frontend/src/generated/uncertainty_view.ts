/* Generated from uncertainty_view.schema.json. Do not edit manually. */

export type EvidenceConfidence = AssessedConfidence | NotAssessed;
export type Basis = string;
export type Kind = 'assessed';
export type Value = number;
export type Kind1 = 'not_assessed';
export type Reason = string;
export type ModelStability = AssessedStability | NotAssessed;
export type Kind2 = 'assessed';
export type RunsSupporting = number;
export type RunsTotal = number;
export type Share = number;
export type Adjustments = {
  [k: string]: unknown;
}[];
export type IntervalHigh = number | null;
export type IntervalLow = number | null;
export type Method = string;
export type Point = number | null;
export type RecommendationConfidence = AssessedConfidence | NotAssessed;

export interface UncertaintyView {
  evidence_confidence: EvidenceConfidence;
  model_stability: ModelStability;
  outcome_probabilities?: OutcomeProbabilities;
  recommendation_confidence: RecommendationConfidence;
}
/**
 * A confidence that was actually assessed (not a coercion default).
 */
export interface AssessedConfidence {
  basis: Basis;
  kind?: Kind;
  value: Value;
}
/**
 * A confidence/stability that is a sentinel placeholder.
 */
export interface NotAssessed {
  kind?: Kind1;
  reason: Reason;
}
/**
 * Model stability that was actually assessed (multiple sensitivity runs).
 */
export interface AssessedStability {
  kind?: Kind2;
  runs_supporting: RunsSupporting;
  runs_total: RunsTotal;
  share: Share;
}
export interface OutcomeProbabilities {
  [k: string]: ProbabilityView;
}
/**
 * One outcome probability entry, preserving point-XOR-interval.
 */
export interface ProbabilityView {
  adjustments?: Adjustments;
  interval_high?: IntervalHigh;
  interval_low?: IntervalLow;
  method: Method;
  point?: Point;
}
