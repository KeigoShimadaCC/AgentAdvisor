/* Generated from objection_view.schema.json. Do not edit manually. */

export type Claim = string;
export type Materiality = string;
export type ObjectionId = string;
export type Reasoning = string;
export type ResolutionStatus = string;
export type TargetSection = string;

export interface ObjectionView {
  claim: Claim;
  materiality: Materiality;
  objection_id: ObjectionId;
  reasoning: Reasoning;
  resolution_status: ResolutionStatus;
  target_section: TargetSection;
}
