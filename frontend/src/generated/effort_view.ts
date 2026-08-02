/* Generated from effort_view.schema.json. Do not edit manually. */

export type InputTokens = number;
export type InvocationAttempts = number;
export type InvocationSuccesses = number;
export type OutputTokens = number;
export type Retries = number;
export type TotalTokens = number;
export type WallClockS = number | null;

export interface EffortView {
  budget_caps?: BudgetCaps;
  budget_counters?: BudgetCounters;
  by_role?: ByRole;
  event_counts?: EventCounts;
  input_tokens?: InputTokens;
  invocation_attempts?: InvocationAttempts;
  invocation_successes?: InvocationSuccesses;
  output_tokens?: OutputTokens;
  retries?: Retries;
  total_tokens?: TotalTokens;
  wall_clock_s?: WallClockS;
}
export interface BudgetCaps {
  [k: string]: number;
}
export interface BudgetCounters {
  [k: string]: number;
}
export interface ByRole {
  [k: string]: {
    [k: string]: number;
  };
}
export interface EventCounts {
  [k: string]: number;
}
