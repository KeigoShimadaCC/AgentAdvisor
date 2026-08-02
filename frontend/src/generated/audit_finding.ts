/* Generated from audit_finding.schema.json. Do not edit manually. */

export type AuditFindingType = 'irrelevant_task' | 'duplicated_work' | 'mandate_violation' | 'unsupported_claim';
export type HighStakesEscalation = boolean;
export type Reason = string;
export type SchemaVersion = number;
export type Level = 'high' | 'medium' | 'low';
/**
 * @minItems 1
 */
export type TargetIds = [string, ...string[]];
export type Findings = AuditIssue[];
export type SchemaVersion1 = number;
export type Deadline = string | null;
export type DepthLimitReached = boolean;
export type ExpectedValueOfMoreResearchLow = boolean;
export type ExpectedValueOfMoreResearchLowReason = string;
export type OpenCriticalEvidenceGaps = boolean;
export type OpenCriticalEvidenceGapsReason = string;
export type RecommendationStable = boolean;
export type RecommendationStableReason = string;
export type SchemaVersion2 = number;
export type UnresolvedMaterialObjections = boolean;
export type UnresolvedMaterialObjectionsReason = string;

export interface AuditFinding {
  findings?: Findings;
  schema_version?: SchemaVersion1;
  stop_input: AuditStopInput;
}
export interface AuditIssue {
  finding_type: AuditFindingType;
  high_stakes_escalation?: HighStakesEscalation;
  reason: Reason;
  schema_version?: SchemaVersion;
  severity: Level;
  target_ids: TargetIds;
}
export interface AuditStopInput {
  deadline?: Deadline;
  depth_limit_reached?: DepthLimitReached;
  expected_value_of_more_research_low: ExpectedValueOfMoreResearchLow;
  expected_value_of_more_research_low_reason: ExpectedValueOfMoreResearchLowReason;
  open_critical_evidence_gaps: OpenCriticalEvidenceGaps;
  open_critical_evidence_gaps_reason: OpenCriticalEvidenceGapsReason;
  recommendation_stable: RecommendationStable;
  recommendation_stable_reason: RecommendationStableReason;
  remaining_budget?: RemainingBudget;
  schema_version?: SchemaVersion2;
  unresolved_material_objections: UnresolvedMaterialObjections;
  unresolved_material_objections_reason: UnresolvedMaterialObjectionsReason;
}
export interface RemainingBudget {
  [k: string]: number;
}
