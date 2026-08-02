/* Generated from history_view.schema.json. Do not edit manually. */

export type ApprovedAt = string;
export type ApprovedBy = string;
export type Decision = string;
export type Kind = 'framing' | 'final';
export type Approvals = ApprovalRecordView[];
export type Changed = boolean;
export type EvidenceConfidence = number;
export type PreferredAlternative = string;
export type PreviousAlternative = string | null;
export type RationaleDigest = string[];
export type RecommendationConfidence = number;
export type Revision = number;
export type Trigger = string;
export type ThesisRevisions = ThesisRevisionView[];

export interface HistoryView {
  approvals?: Approvals;
  thesis_revisions?: ThesisRevisions;
}
export interface ApprovalRecordView {
  approved_at: ApprovedAt;
  approved_by: ApprovedBy;
  decision: Decision;
  kind: Kind;
}
export interface ThesisRevisionView {
  changed: Changed;
  evidence_confidence: EvidenceConfidence;
  preferred_alternative: PreferredAlternative;
  previous_alternative?: PreviousAlternative;
  rationale_digest?: RationaleDigest;
  recommendation_confidence: RecommendationConfidence;
  revision: Revision;
  trigger: Trigger;
}
