/* Generated from audit_usage.schema.json. Do not edit manually. */

export type InputTokens = number | null;
export type OutputTokens = number | null;
export type SchemaVersion = number;
export type TotalTokens = number | null;

export interface AuditUsage {
  input_tokens?: InputTokens;
  output_tokens?: OutputTokens;
  schema_version?: SchemaVersion;
  total_tokens?: TotalTokens;
}
