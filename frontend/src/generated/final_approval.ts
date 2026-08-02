/* Generated from final_approval.schema.json. Do not edit manually. */

export type ApprovedAt = string;
export type ApprovedBy = string;
export type FinalDecision = 'accept' | 'revise';
export type Note = string;
export type SchemaVersion = number;

export interface FinalApproval {
  approved_at: ApprovedAt;
  approved_by: ApprovedBy;
  decision: FinalDecision;
  note?: Note;
  schema_version?: SchemaVersion;
}
