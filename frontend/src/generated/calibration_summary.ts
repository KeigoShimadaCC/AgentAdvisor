/* Generated from calibration_summary.schema.json. Do not edit manually. */

export type BrierScore = number | null;
export type Interpretation = string;
export type MeanForecast = number | null;
export type MeanRealized = number | null;
export type SampleSize = number;
export type SchemaVersion = number;

export interface CalibrationSummary {
  brier_score?: BrierScore;
  interpretation: Interpretation;
  mean_forecast?: MeanForecast;
  mean_realized?: MeanRealized;
  sample_size: SampleSize;
  schema_version?: SchemaVersion;
}
