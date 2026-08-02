/* Generated from audit_event.schema.json. Do not edit manually. */

export type Actor = string;
export type CliVersion = string | null;
export type DurationMs = number | null;
export type EventType = string;
export type Model = string | null;
export type SchemaVersion = number;
export type Ts = string;
export type InputTokens = number | null;
export type OutputTokens = number | null;
export type SchemaVersion1 = number;
export type TotalTokens = number | null;

export interface AuditEvent {
  actor: Actor;
  cli_version?: CliVersion;
  duration_ms?: DurationMs;
  event_type: EventType;
  model?: Model;
  payload?: Payload;
  schema_version?: SchemaVersion;
  ts: Ts;
  usage?: AuditUsage | null;
}
export interface Payload {
  [k: string]: unknown;
}
export interface AuditUsage {
  input_tokens?: InputTokens;
  output_tokens?: OutputTokens;
  schema_version?: SchemaVersion1;
  total_tokens?: TotalTokens;
}
