/* Generated from monitoring_plan.schema.json. Do not edit manually. */

export type CaseId = string;
export type Concretized = boolean;
export type DeliveredAt = string;
export type Horizon = string;
export type CheckCadenceDays = number;
export type ImplicatedAlternative = string | null;
export type IndicatorId = string;
export type Observable = string;
export type SchemaVersion = number;
export type IndicatorSource = 'premortem_failure_mode' | 'change_trigger';
export type SourceRef = string;
export type Threshold = string;
export type WouldImply = string;
export type Indicators = MonitoredIndicator[];
export type FailureMode = string;
export type Mitigation = string;
export type MitigationId = string;
export type Owner = string;
export type SchemaVersion1 = number;
export type Severity = string;
export type MitigationStatus = 'not_started' | 'in_place' | 'not_applicable';
export type TriggeredBy = string[];
export type Mitigations = TrackedMitigation[];
export type SchemaVersion2 = number;

/**
 * What to watch after the report is delivered, and what to do about it.
 */
export interface MonitoringPlan {
  case_id: CaseId;
  concretized?: Concretized;
  delivered_at: DeliveredAt;
  horizon: Horizon;
  indicators?: Indicators;
  mitigations?: Mitigations;
  schema_version?: SchemaVersion2;
}
/**
 * One thing to watch, and what its breach would mean.
 */
export interface MonitoredIndicator {
  check_cadence_days: CheckCadenceDays;
  implicated_alternative?: ImplicatedAlternative;
  indicator_id: IndicatorId;
  observable: Observable;
  schema_version?: SchemaVersion;
  source: IndicatorSource;
  source_ref: SourceRef;
  threshold: Threshold;
  would_imply: WouldImply;
}
/**
 * A prepared response, with an owner.
 *
 * Sourced from ``FailureMode.preventive_action``, which the pipeline generates on every
 * case and has never carried into the deliverable.
 */
export interface TrackedMitigation {
  failure_mode: FailureMode;
  mitigation: Mitigation;
  mitigation_id: MitigationId;
  owner: Owner;
  schema_version?: SchemaVersion1;
  severity: Severity;
  status?: MitigationStatus;
  triggered_by?: TriggeredBy;
}
