/* Generated from approval_record_view.schema.json. Do not edit manually. */

export type ApprovedAt = string;
export type ApprovedBy = string;
export type Decision = string;
export type Kind = 'framing' | 'final';

export interface ApprovalRecordView {
  approved_at: ApprovedAt;
  approved_by: ApprovedBy;
  decision: Decision;
  kind: Kind;
}
