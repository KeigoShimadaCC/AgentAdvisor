/* Generated from assumption_record.schema.json. Do not edit manually. */

export type AssumptionId = string;
export type Claim = string;
export type Level = 'high' | 'medium' | 'low';
export type Delta = number;
export type Description = string;
/**
 * @minItems 1
 */
export type EvidenceIds = [string, ...string[]];
export type SchemaVersion = number;
export type Adjustments = ProbabilityAdjustment[];
export type BaseRate = number | null;
export type IntervalHigh = number | null;
export type IntervalLow = number | null;
export type ProbabilityMethod = 'reference_class' | 'scenario_model' | 'structured_subjective';
export type Point = number | null;
export type ReferenceClass = string | null;
export type SchemaVersion1 = number;
export type EvidenceAgainst = string[];
export type EvidenceFor = string[];
export type SchemaVersion2 = number;
export type AssumptionStatus = 'unresolved' | 'supported' | 'contradicted' | 'retired';
export type AssumptionType = 'forecast' | 'structural' | 'operational' | 'financial' | 'regulatory' | 'behavioral';

export interface AssumptionRecord {
  assumption_id: AssumptionId;
  claim: Claim;
  confidence: Level;
  estimate: ProbabilityEstimate;
  evidence_against?: EvidenceAgainst;
  evidence_for?: EvidenceFor;
  materiality: Level;
  schema_version?: SchemaVersion2;
  status: AssumptionStatus;
  type: AssumptionType;
}
export interface ProbabilityEstimate {
  adjustments?: Adjustments;
  base_rate?: BaseRate;
  interval_high?: IntervalHigh;
  interval_low?: IntervalLow;
  method: ProbabilityMethod;
  point?: Point;
  reference_class?: ReferenceClass;
  schema_version?: SchemaVersion1;
}
export interface ProbabilityAdjustment {
  delta: Delta;
  description: Description;
  evidence_ids: EvidenceIds;
  schema_version?: SchemaVersion;
}
