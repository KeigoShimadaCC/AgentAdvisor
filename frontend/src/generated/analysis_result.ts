/* Generated from analysis_result.schema.json. Do not edit manually. */

export type AssumptionIds = string[];
export type FavoredAlternativeAbove = string;
export type FavoredAlternativeBelow = string;
export type Parameter = string;
export type SchemaVersion = number;
export type ThresholdValue = number;
export type BreakEvenThresholds = BreakEvenThreshold[];
export type EvidenceIds = string[];
export type ResultsPath = string;
/**
 * @minItems 1
 */
export type Scenarios = [AnalysisScenario, ...AnalysisScenario[]];
export type Delta = number;
export type Description = string;
/**
 * @minItems 1
 */
export type EvidenceIds1 = [string, ...string[]];
export type SchemaVersion1 = number;
export type Adjustments = ProbabilityAdjustment[];
export type BaseRate = number | null;
export type IntervalHigh = number | null;
export type IntervalLow = number | null;
export type ProbabilityMethod = 'reference_class' | 'scenario_model' | 'structured_subjective';
export type Point = number | null;
export type ReferenceClass = string | null;
export type SchemaVersion2 = number;
export type ScenarioName = string;
export type SchemaVersion3 = number;
export type SchemaVersion4 = number;
export type ScriptPath = string;
/**
 * @minItems 1
 */
export type SensitivityTable = [SensitivityRow, ...SensitivityRow[]];
export type Parameter1 = string;
export type ParameterValue = number | string;
export type PreferredAlternative = string;
export type SchemaVersion5 = number;
export type TaskId = string;

export interface AnalysisResult {
  assumption_ids?: AssumptionIds;
  break_even_thresholds?: BreakEvenThresholds;
  evidence_ids?: EvidenceIds;
  expected_values_by_alternative: ExpectedValuesByAlternative;
  results_path: ResultsPath;
  scenarios: Scenarios;
  schema_version?: SchemaVersion4;
  script_path: ScriptPath;
  sensitivity_table: SensitivityTable;
  task_id: TaskId;
}
export interface BreakEvenThreshold {
  favored_alternative_above: FavoredAlternativeAbove;
  favored_alternative_below: FavoredAlternativeBelow;
  parameter: Parameter;
  schema_version?: SchemaVersion;
  threshold_value: ThresholdValue;
}
export interface ExpectedValuesByAlternative {
  [k: string]: number;
}
export interface AnalysisScenario {
  probability: ProbabilityEstimate;
  scenario_name: ScenarioName;
  schema_version?: SchemaVersion3;
}
export interface ProbabilityEstimate {
  adjustments?: Adjustments;
  base_rate?: BaseRate;
  interval_high?: IntervalHigh;
  interval_low?: IntervalLow;
  method: ProbabilityMethod;
  point?: Point;
  reference_class?: ReferenceClass;
  schema_version?: SchemaVersion2;
}
export interface ProbabilityAdjustment {
  delta: Delta;
  description: Description;
  evidence_ids: EvidenceIds1;
  schema_version?: SchemaVersion1;
}
export interface SensitivityRow {
  parameter: Parameter1;
  parameter_value: ParameterValue;
  preferred_alternative: PreferredAlternative;
  resulting_expected_values: ResultingExpectedValues;
  schema_version?: SchemaVersion5;
}
export interface ResultingExpectedValues {
  [k: string]: number;
}
