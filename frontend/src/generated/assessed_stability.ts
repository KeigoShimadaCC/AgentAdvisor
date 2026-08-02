/* Generated from assessed_stability.schema.json. Do not edit manually. */

export type Kind = 'assessed';
export type RunsSupporting = number;
export type RunsTotal = number;
export type Share = number;

/**
 * Model stability that was actually assessed (multiple sensitivity runs).
 */
export interface AssessedStability {
  kind?: Kind;
  runs_supporting: RunsSupporting;
  runs_total: RunsTotal;
  share: Share;
}
