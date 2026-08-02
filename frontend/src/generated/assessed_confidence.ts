/* Generated from assessed_confidence.schema.json. Do not edit manually. */

export type Basis = string;
export type Kind = 'assessed';
export type Value = number;

/**
 * A confidence that was actually assessed (not a coercion default).
 */
export interface AssessedConfidence {
  basis: Basis;
  kind?: Kind;
  value: Value;
}
