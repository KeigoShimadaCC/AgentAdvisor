/* Generated from evidence_batch.schema.json. Do not edit manually. */

export type NoEvidenceFound = boolean;
export type Question = string;
export type Claim = string;
export type Level = 'high' | 'medium' | 'low';
export type EvidenceId = string;
export type Excerpt = string;
export type IndependenceGroup = string;
export type Limitations = string[];
export type PublicationDate = string;
export type Publisher = string;
export type RetrievalDate = string;
export type RetrievedBy = string;
export type SchemaVersion = number;
export type SourceTitle = string;
export type SourceType =
  | 'regulatory_filing'
  | 'official_statistic'
  | 'law_or_standard'
  | 'original_research'
  | 'reputable_secondary'
  | 'specialist_reporting'
  | 'user_document'
  | 'other';
export type SourceUrl = string;
export type Records = EvidenceRecord[];
export type SchemaVersion1 = number;
export type SearchNotes = string;
export type TaskId = string;

/**
 * One researcher invocation's full yield for a single assigned question.
 */
export interface EvidenceBatch {
  no_evidence_found?: NoEvidenceFound;
  question: Question;
  records?: Records;
  schema_version?: SchemaVersion1;
  search_notes: SearchNotes;
  task_id: TaskId;
}
export interface EvidenceRecord {
  claim: Claim;
  directness: Level;
  evidence_id: EvidenceId;
  excerpt: Excerpt;
  independence_group: IndependenceGroup;
  limitations: Limitations;
  publication_date: PublicationDate;
  publisher: Publisher;
  reliability: Level;
  retrieval_date: RetrievalDate;
  retrieved_by: RetrievedBy;
  schema_version?: SchemaVersion;
  source_title: SourceTitle;
  source_type: SourceType;
  source_url: SourceUrl;
}
