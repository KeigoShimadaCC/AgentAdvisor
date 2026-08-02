/* Generated from preliminary_recommendation.schema.json. Do not edit manually. */

export type Basis = string;
export type SchemaVersion = number;
export type Value = number;
export type KeyAssumptions = string[];
export type MajorRisks = string[];
export type RunsSupporting = number;
export type RunsTotal = number;
export type SchemaVersion1 = number;
export type ShareOfSensitivityRunsSupportingRecommendation = number;
export type Delta = number;
export type Description = string;
/**
 * @minItems 1
 */
export type EvidenceIds = [string, ...string[]];
export type SchemaVersion2 = number;
export type Adjustments = ProbabilityAdjustment[];
export type BaseRate = number | null;
export type IntervalHigh = number | null;
export type IntervalLow = number | null;
export type ProbabilityMethod = 'reference_class' | 'scenario_model' | 'structured_subjective';
export type Point = number | null;
export type ReferenceClass = string | null;
export type SchemaVersion3 = number;
export type PreferredAlternative = string;
/**
 * @minItems 1
 */
export type Rationale = [string, ...string[]];
export type SchemaVersion4 = number;
export type UnresolvedEvidenceGaps = string[];

export interface PreliminaryRecommendation {
  evidence_confidence: ConfidenceAssessment;
  key_assumptions?: KeyAssumptions;
  major_risks?: MajorRisks;
  model_stability: ModelStability;
  outcome_probabilities: OutcomeProbabilities;
  preferred_alternative: PreferredAlternative;
  rationale: Rationale;
  recommendation_confidence: ConfidenceAssessment;
  schema_version?: SchemaVersion4;
  unresolved_evidence_gaps?: UnresolvedEvidenceGaps;
}
export interface ConfidenceAssessment {
  basis: Basis;
  schema_version?: SchemaVersion;
  value: Value;
}
export interface ModelStability {
  runs_supporting: RunsSupporting;
  runs_total: RunsTotal;
  schema_version?: SchemaVersion1;
  share_of_sensitivity_runs_supporting_recommendation: ShareOfSensitivityRunsSupportingRecommendation;
}
export interface OutcomeProbabilities {
  [k: string]: ProbabilityEstimate;
}
export interface ProbabilityEstimate {
  adjustments?: Adjustments;
  base_rate?: BaseRate;
  interval_high?: IntervalHigh;
  interval_low?: IntervalLow;
  method: ProbabilityMethod;
  point?: Point;
  reference_class?: ReferenceClass;
  schema_version?: SchemaVersion3;
}
export interface ProbabilityAdjustment {
  delta: Delta;
  description: Description;
  evidence_ids: EvidenceIds;
  schema_version?: SchemaVersion2;
}
