/* Generated from gate_summary_view.schema.json. Do not edit manually. */

export type Findings = {
  [k: string]: unknown;
}[];
export type Outcome = string;
export type Stage = string;

export interface GateSummaryView {
  findings?: Findings;
  outcome: Outcome;
  stage: Stage;
}
