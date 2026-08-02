/* Generated from gate_report.schema.json. Do not edit manually. */

export type CancelledTaskIds = string[];
export type CheckedAt = string;
export type CheckId = string;
export type Message = string;
export type SchemaVersion = number;
/**
 * Ordered: a gate's outcome is the maximum severity among its findings.
 */
export type GateSeverity = 'pass' | 'warn' | 'block';
export type TargetIds = string[];
export type Findings = GateFinding[];
export type SchemaVersion1 = number;
export type Stage = string;

/**
 * Result of the deterministic process gate run at a stage boundary.
 */
export interface GateReport {
  cancelled_task_ids?: CancelledTaskIds;
  checked_at: CheckedAt;
  findings?: Findings;
  outcome: GateSeverity;
  schema_version?: SchemaVersion1;
  stage: Stage;
}
export interface GateFinding {
  check_id: CheckId;
  message: Message;
  schema_version?: SchemaVersion;
  severity: GateSeverity;
  target_ids?: TargetIds;
}
