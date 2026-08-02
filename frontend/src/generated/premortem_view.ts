/* Generated from premortem_view.schema.json. Do not edit manually. */

export type AssumedOutcome = string;
export type FailureModes = {
  [k: string]: unknown;
}[];
export type Horizon = string;
export type MostLikelyFailureMode = string;

export interface PreMortemView {
  assumed_outcome: AssumedOutcome;
  failure_modes?: FailureModes;
  horizon: Horizon;
  most_likely_failure_mode: MostLikelyFailureMode;
}
