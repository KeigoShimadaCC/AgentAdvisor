/* Generated from final_recommendation.schema.json. Do not edit manually. */

/**
 * @minItems 1
 */
export type AlternativesConsidered = [AlternativeAssessment, ...AlternativeAssessment[]];
export type Alternative = string;
export type Rank = number;
export type Rationale = string;
export type SchemaVersion = number;
export type Citations = string[];
export type CriticalAssumptions = string[];
export type DecisionConfidenceSummary = string;
export type Basis = string;
export type SchemaVersion1 = number;
export type Value = number;
/**
 * @minItems 1
 */
export type KeyReasons = [string, ...string[]];
export type RunsSupporting = number;
export type RunsTotal = number;
export type SchemaVersion2 = number;
export type ShareOfSensitivityRunsSupportingRecommendation = number;
/**
 * @minItems 1
 */
export type NextActions = [NextAction, ...NextAction[]];
export type Action = string;
export type ActionId = string;
export type ByDate = string;
export type DependsOn = string[];
export type EstimatedCost = string | null;
export type FirstStep = string;
export type Owner = string;
export type SchemaVersion3 = number;
export type WhyNow = string;
export type Delta = number;
export type Description = string;
/**
 * @minItems 1
 */
export type EvidenceIds = [string, ...string[]];
export type SchemaVersion4 = number;
export type Adjustments = ProbabilityAdjustment[];
export type BaseRate = number | null;
export type IntervalHigh = number | null;
export type IntervalLow = number | null;
export type ProbabilityMethod = 'reference_class' | 'scenario_model' | 'structured_subjective';
export type Point = number | null;
export type ReferenceClass = string | null;
export type SchemaVersion5 = number;
export type QuantitativeFindings = string[];
export type RecommendationChangeTriggers = string[];
export type RecommendedAction = string;
/**
 * @minItems 1
 */
export type ScenarioAnalysis = [ScenarioAssessment, ...ScenarioAssessment[]];
export type ScenarioName = string;
export type SchemaVersion6 = number;
export type Summary = string;
export type SchemaVersion7 = number;
export type Claim = string;
export type Resolution = string;
export type Resolved = boolean;
export type SchemaVersion8 = number;
export type StrongestCounterarguments = Counterargument[];
export type Timing = string;

export interface FinalRecommendation {
  alternatives_considered: AlternativesConsidered;
  citations?: Citations;
  critical_assumptions?: CriticalAssumptions;
  decision_confidence_summary: DecisionConfidenceSummary;
  evidence_confidence: ConfidenceAssessment;
  key_reasons: KeyReasons;
  model_stability: ModelStability;
  next_actions: NextActions;
  outcome_probabilities: OutcomeProbabilities;
  quantitative_findings?: QuantitativeFindings;
  recommendation_change_triggers?: RecommendationChangeTriggers;
  recommendation_confidence: ConfidenceAssessment;
  recommended_action: RecommendedAction;
  scenario_analysis: ScenarioAnalysis;
  schema_version?: SchemaVersion7;
  strongest_counterarguments?: StrongestCounterarguments;
  timing: Timing;
}
export interface AlternativeAssessment {
  alternative: Alternative;
  rank: Rank;
  rationale: Rationale;
  schema_version?: SchemaVersion;
}
export interface ConfidenceAssessment {
  basis: Basis;
  schema_version?: SchemaVersion1;
  value: Value;
}
export interface ModelStability {
  runs_supporting: RunsSupporting;
  runs_total: RunsTotal;
  schema_version?: SchemaVersion2;
  share_of_sensitivity_runs_supporting_recommendation: ShareOfSensitivityRunsSupportingRecommendation;
}
/**
 * One executable step, not a sentence about a step.
 *
 * ``first_step`` is what makes the record useful: an action the reader cannot
 * start today is not an action.
 */
export interface NextAction {
  action: Action;
  action_id: ActionId;
  by_date: ByDate;
  depends_on?: DependsOn;
  estimated_cost?: EstimatedCost;
  first_step: FirstStep;
  owner: Owner;
  schema_version?: SchemaVersion3;
  why_now: WhyNow;
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
  schema_version?: SchemaVersion5;
}
export interface ProbabilityAdjustment {
  delta: Delta;
  description: Description;
  evidence_ids: EvidenceIds;
  schema_version?: SchemaVersion4;
}
export interface ScenarioAssessment {
  probability: ProbabilityEstimate;
  scenario_name: ScenarioName;
  schema_version?: SchemaVersion6;
  summary: Summary;
}
export interface Counterargument {
  claim: Claim;
  resolution: Resolution;
  resolved: Resolved;
  schema_version?: SchemaVersion8;
}
