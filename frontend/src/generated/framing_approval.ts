/* Generated from framing_approval.schema.json. Do not edit manually. */

export type ApprovedAt = string;
export type ApprovedBy = string;
export type FramingDecision = 'approve' | 'edit' | 'answer_clarifications';
export type SchemaVersion = number;

export interface FramingApproval {
  approved_at: ApprovedAt;
  approved_by: ApprovedBy;
  clarification_answers?: ClarificationAnswers;
  decision: FramingDecision;
  edits?: Edits;
  schema_version?: SchemaVersion;
}
export interface ClarificationAnswers {
  [k: string]: string;
}
export interface Edits {
  [k: string]: unknown;
}
