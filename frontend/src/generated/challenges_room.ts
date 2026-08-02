/* Generated from challenges_room.schema.json. Do not edit manually. */

export type Claim = string;
export type Materiality = string;
export type ObjectionId = string;
export type Reasoning = string;
export type ResolutionStatus = string;
export type TargetSection = string;
export type Objections = ObjectionView[];
export type AssumedOutcome = string;
export type FailureModes = {
  [k: string]: unknown;
}[];
export type Horizon = string;
export type MostLikelyFailureMode = string;
export type Agreement = boolean;
export type DivergenceSummary = string;
export type Positions = {
  [k: string]: unknown;
}[];
export type ReconciledAlternative = string | null;
export type Stage = string;

export interface ChallengesRoom {
  objections?: Objections;
  premortem?: PreMortemView | null;
  track_divergence?: TrackDivergenceView | null;
}
export interface ObjectionView {
  claim: Claim;
  materiality: Materiality;
  objection_id: ObjectionId;
  reasoning: Reasoning;
  resolution_status: ResolutionStatus;
  target_section: TargetSection;
}
export interface PreMortemView {
  assumed_outcome: AssumedOutcome;
  failure_modes?: FailureModes;
  horizon: Horizon;
  most_likely_failure_mode: MostLikelyFailureMode;
}
export interface TrackDivergenceView {
  agreement: Agreement;
  divergence_summary: DivergenceSummary;
  positions?: Positions;
  reconciled_alternative?: ReconciledAlternative;
  stage: Stage;
}
