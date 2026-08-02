/* Generated from verification_worksheet.schema.json. Do not edit manually. */

export type CheckId = string;
export type Message = string;
export type SchemaVersion = number;
/**
 * Ordered: a gate's outcome is the maximum severity among its findings.
 */
export type GateSeverity = 'pass' | 'warn' | 'block';
export type TargetIds = string[];
export type DeterministicFindings = GateFinding[];
export type Instructions = string;
export type CitedIds = string[];
export type Claim = string;
export type DanglingIds = string[];
export type EvidenceExcerpts = string[];
export type ItemId = string;
export type SchemaVersion1 = number;
export type Items = CitationCheckItem[];
export type SchemaVersion2 = number;

export interface VerificationWorksheet {
  deterministic_findings?: DeterministicFindings;
  instructions: Instructions;
  items?: Items;
  schema_version?: SchemaVersion2;
}
export interface GateFinding {
  check_id: CheckId;
  message: Message;
  schema_version?: SchemaVersion;
  severity: GateSeverity;
  target_ids?: TargetIds;
}
/**
 * One claim paired with the excerpts of the evidence it cites.
 *
 * The reviewer must return a verdict per item, so "the citations look fine" is not
 * an available answer.
 */
export interface CitationCheckItem {
  cited_ids?: CitedIds;
  claim: Claim;
  dangling_ids?: DanglingIds;
  evidence_excerpts?: EvidenceExcerpts;
  item_id: ItemId;
  schema_version?: SchemaVersion1;
}
