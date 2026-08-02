/* Generated from not_assessed.schema.json. Do not edit manually. */

export type Kind = 'not_assessed';
export type Reason = string;

/**
 * A confidence/stability that is a sentinel placeholder.
 */
export interface NotAssessed {
  kind?: Kind;
  reason: Reason;
}
