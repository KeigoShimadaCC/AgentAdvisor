/* Generated from confidence_assessment.schema.json. Do not edit manually. */

export type Basis = string;
export type SchemaVersion = number;
export type Value = number;

export interface ConfidenceAssessment {
  basis: Basis;
  schema_version?: SchemaVersion;
  value: Value;
}
