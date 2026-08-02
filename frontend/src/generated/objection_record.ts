/* Generated from objection_record.schema.json. Do not edit manually. */

export type Claim = string;
export type CommissionedTasks = string[];
export type Level = 'high' | 'medium' | 'low';
export type ObjectionId = string;
export type Reasoning = string;
export type ReferencedAssumptionIds = string[];
export type ReferencedEvidenceIds = string[];
export type ObjectionResolutionStatus = 'open' | 'partially_resolved' | 'resolved' | 'dismissed';
export type ReversalEvidence = string;
export type SchemaVersion = number;
export type TargetSection = string;

export interface ObjectionRecord {
  claim: Claim;
  commissioned_tasks?: CommissionedTasks;
  materiality: Level;
  objection_id: ObjectionId;
  reasoning: Reasoning;
  referenced_assumption_ids?: ReferencedAssumptionIds;
  referenced_evidence_ids?: ReferencedEvidenceIds;
  resolution_status: ObjectionResolutionStatus;
  reversal_evidence: ReversalEvidence;
  schema_version?: SchemaVersion;
  target_section: TargetSection;
}
