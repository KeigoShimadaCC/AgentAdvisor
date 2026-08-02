/* Generated from prior_evidence_digest.schema.json. Do not edit manually. */

export type AuthorityScore = number;
export type Claim = string;
export type FromCaseId = string;
export type PublicationDate = string;
export type Publisher = string;
export type SchemaVersion = number;
export type SourceTitle = string;
export type SourceType =
  | 'regulatory_filing'
  | 'official_statistic'
  | 'law_or_standard'
  | 'original_research'
  | 'reputable_secondary'
  | 'specialist_reporting'
  | 'other';
export type SourceUrl = string;
export type Topics = string[];
export type Entries = PriorEvidenceEntry[];
export type GeneratedAt = string;
export type SchemaVersion1 = number;
export type StalenessWarning = string;

/**
 * Standing-research-program output: evidence carried over from earlier cases.
 *
 * Records here are stale by construction and must be re-verified before citation;
 * they are never written to the blackboard by the orchestrator.
 */
export interface PriorEvidenceDigest {
  entries?: Entries;
  generated_at: GeneratedAt;
  schema_version?: SchemaVersion1;
  staleness_warning: StalenessWarning;
}
export interface PriorEvidenceEntry {
  authority_score: AuthorityScore;
  claim: Claim;
  from_case_id: FromCaseId;
  publication_date: PublicationDate;
  publisher: Publisher;
  schema_version?: SchemaVersion;
  source_title: SourceTitle;
  source_type: SourceType;
  source_url: SourceUrl;
  topics?: Topics;
}
