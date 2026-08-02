/* Generated from counterargument.schema.json. Do not edit manually. */

export type Claim = string;
export type Resolution = string;
export type Resolved = boolean;
export type SchemaVersion = number;

export interface Counterargument {
  claim: Claim;
  resolution: Resolution;
  resolved: Resolved;
  schema_version?: SchemaVersion;
}
