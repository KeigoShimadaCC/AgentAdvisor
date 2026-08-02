/* Generated from assumption_view.schema.json. Do not edit manually. */

export type AssumptionId = string;
export type Claim = string;
export type Confidence = string;
export type EstimatePoint = number | null;
export type EvidenceAgainst = string[];
export type EvidenceFor = string[];
export type Materiality = string;
export type Status = string;
export type Type = string;

export interface AssumptionView {
  assumption_id: AssumptionId;
  claim: Claim;
  confidence: Confidence;
  estimate_point?: EstimatePoint;
  evidence_against?: EvidenceAgainst;
  evidence_for?: EvidenceFor;
  materiality: Materiality;
  status: Status;
  type: Type;
}
