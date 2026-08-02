/* Generated from model_stability.schema.json. Do not edit manually. */

export type RunsSupporting = number;
export type RunsTotal = number;
export type SchemaVersion = number;
export type ShareOfSensitivityRunsSupportingRecommendation = number;

export interface ModelStability {
  runs_supporting: RunsSupporting;
  runs_total: RunsTotal;
  schema_version?: SchemaVersion;
  share_of_sensitivity_runs_supporting_recommendation: ShareOfSensitivityRunsSupportingRecommendation;
}
