/* Generated from source_view.schema.json. Do not edit manually. */

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
