/* Generated from disclosure_record.schema.json. Do not edit manually. */

/**
 * @minItems 1
 */
export type ExhaustedDimensions = [string, ...string[]];
export type SchemaVersion = number;
export type StopReason =
  | 'no_critical_evidence_gaps_remain'
  | 'recommendation_stable_across_plausible_sensitivity_ranges'
  | 'no_unresolved_objection_likely_to_change_decision'
  | 'expected_value_of_more_research_low'
  | 'investigation_budget_exhausted'
  | 'user_deadline_or_depth_limit_reached';
export type StopReasons = StopReason[];

export interface DisclosureRecord {
  exhausted_dimensions: ExhaustedDimensions;
  schema_version?: SchemaVersion;
  stop_reasons: StopReasons;
}
