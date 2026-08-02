/* Generated from sources_room.schema.json. Do not edit manually. */

export type CorpusAuthorityMean = number | null;
export type IndependentGroupCount = number | null;
export type MaxClusterShare = number | null;
export type PrimarySourceShare = number | null;
export type AuthorityScore = number | null;
export type Claim = string;
export type ClusterShare = number | null;
export type Directness = string;
export type EvidenceId = string;
export type Flags = string[];
export type IndependenceGroup = string;
export type PublicationDate = string;
export type Publisher = string;
export type Reliability = string;
export type SourceTier = string | null;
export type SourceType = string;
export type SourceUrl = string;
export type Sources = SourceView[];

export interface SourcesRoom {
  corpus_authority_mean?: CorpusAuthorityMean;
  independent_group_count?: IndependentGroupCount;
  max_cluster_share?: MaxClusterShare;
  primary_source_share?: PrimarySourceShare;
  sources?: Sources;
}
/**
 * An evidence record joined with its critique scores/tiers/flags.
 */
export interface SourceView {
  authority_score?: AuthorityScore;
  claim: Claim;
  cluster_share?: ClusterShare;
  directness: Directness;
  evidence_id: EvidenceId;
  flags?: Flags;
  independence_group: IndependenceGroup;
  publication_date: PublicationDate;
  publisher: Publisher;
  reliability: Reliability;
  source_tier?: SourceTier;
  source_type: SourceType;
  source_url: SourceUrl;
}
