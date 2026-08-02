/* Generated from probability_view.schema.json. Do not edit manually. */

export type Adjustments = {
  [k: string]: unknown;
}[];
export type IntervalHigh = number | null;
export type IntervalLow = number | null;
export type Method = string;
export type Point = number | null;

/**
 * One outcome probability entry, preserving point-XOR-interval.
 */
export interface ProbabilityView {
  adjustments?: Adjustments;
  interval_high?: IntervalHigh;
  interval_low?: IntervalLow;
  method: Method;
  point?: Point;
}
