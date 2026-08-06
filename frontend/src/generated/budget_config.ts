/* Generated from budget_config.schema.json. Do not edit manually. */

export type MaxAgentInvocations = number;
export type MaxConcurrentWorkers = number;
export type MaxHighTierCalls = number;
export type MaxRepairCycles = number;
export type MaxResearchTasks = number;
export type MaxWallClockS = number;

export interface BudgetConfig {
  max_agent_invocations?: MaxAgentInvocations;
  max_concurrent_workers?: MaxConcurrentWorkers;
  max_high_tier_calls?: MaxHighTierCalls;
  max_repair_cycles?: MaxRepairCycles;
  max_research_tasks?: MaxResearchTasks;
  max_wall_clock_s?: MaxWallClockS;
  [k: string]: unknown;
}
