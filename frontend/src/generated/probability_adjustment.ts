/* Generated from probability_adjustment.schema.json. Do not edit manually. */

export type Delta = number;
export type Description = string;
/**
 * @minItems 1
 */
export type EvidenceIds = [string, ...string[]];
export type SchemaVersion = number;

export interface ProbabilityAdjustment {
  delta: Delta;
  description: Description;
  evidence_ids: EvidenceIds;
  schema_version?: SchemaVersion;
}
