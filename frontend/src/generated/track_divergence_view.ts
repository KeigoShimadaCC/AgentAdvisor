/* Generated from track_divergence_view.schema.json. Do not edit manually. */

export type Agreement = boolean;
export type DivergenceSummary = string;
export type Positions = {
  [k: string]: unknown;
}[];
export type ReconciledAlternative = string | null;
export type Stage = string;

export interface TrackDivergenceView {
  agreement: Agreement;
  divergence_summary: DivergenceSummary;
  positions?: Positions;
  reconciled_alternative?: ReconciledAlternative;
  stage: Stage;
}
