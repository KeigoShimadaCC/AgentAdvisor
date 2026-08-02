/* Generated from review_report.schema.json. Do not edit manually. */

export type ItemId = string;
export type Justification = string;
export type SchemaVersion = number;
export type Supported = boolean;
export type CitationVerdicts = CitationVerdict[];
export type ReviewDefectType =
  'false_precision' | 'unsupported_citation' | 'confidence_language_mismatch' | 'independence_overstatement';
export type Explanation = string;
export type SchemaVersion1 = number;
export type TargetId = string;
export type Defects = ReviewDefect[];
export type ReviewOutcome = 'pass' | 'fail';
export type SchemaVersion2 = number;

export interface ReviewReport {
  citation_verdicts?: CitationVerdicts;
  defects?: Defects;
  outcome: ReviewOutcome;
  schema_version?: SchemaVersion2;
}
export interface CitationVerdict {
  item_id: ItemId;
  justification: Justification;
  schema_version?: SchemaVersion;
  supported: Supported;
}
export interface ReviewDefect {
  defect_type: ReviewDefectType;
  explanation: Explanation;
  schema_version?: SchemaVersion1;
  target_id: TargetId;
}
