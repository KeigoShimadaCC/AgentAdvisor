/* Generated from integrity_view.schema.json. Do not edit manually. */

export type Disclosure = {
  [k: string]: unknown;
} | null;
export type Findings = {
  [k: string]: unknown;
}[];
export type Outcome = string;
export type Stage = string;
export type Gates = GateSummaryView[];
export type ReviewAccepted = boolean | null;
export type ReviewDefects = {
  [k: string]: unknown;
}[];
export type ReviewOutcome = string | null;

export interface IntegrityView {
  disclosure?: Disclosure;
  gates?: Gates;
  review_accepted?: ReviewAccepted;
  review_defects?: ReviewDefects;
  review_outcome?: ReviewOutcome;
}
export interface GateSummaryView {
  findings?: Findings;
  outcome: Outcome;
  stage: Stage;
}
