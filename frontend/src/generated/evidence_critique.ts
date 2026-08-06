/* Generated from evidence_critique.schema.json. Do not edit manually. */

/**
 * @minItems 1
 */
export type EvidenceIds = [string, ...string[]];
export type IndependenceGroup = string;
export type SchemaVersion = number;
export type ShareOfCorpus = number;
export type Clusters = IndependenceCluster[];
export type CorpusAuthorityMean = number;
export type EvidenceCount = number;
export type Gaps = string[];
export type IndependentGroupCount = number;
export type MaxClusterShare = number;
export type PrimarySourceShare = number;
export type SchemaVersion1 = number;
export type AgeDays = number;
export type AuthorityScore = number;
export type EvidenceId = string;
export type EvidenceFlag =
  | 'single_source_cluster'
  | 'stale'
  | 'low_directness'
  | 'low_reliability'
  | 'missing_limitations'
  | 'weak_source_tier'
  | 'user_supplied';
export type Flags = EvidenceFlag[];
export type IndependenceGroup1 = string;
export type SchemaVersion2 = number;
/**
 * Authority tier of an evidence source, ordered strongest to weakest.
 */
export type SourceTier = 'primary' | 'official' | 'reputable' | 'weak' | 'unverifiable';
export type Scored = EvidenceAuthorityScore[];
export type WeakestEvidenceIds = string[];

/**
 * Deterministic quality assessment of the whole evidence corpus.
 *
 * Computed by ``orchestrator.evidence_critic`` from the blackboard, never asserted
 * by an agent, so it cannot be talked up.
 */
export interface EvidenceCritique {
  clusters?: Clusters;
  corpus_authority_mean: CorpusAuthorityMean;
  evidence_count: EvidenceCount;
  gaps?: Gaps;
  independent_group_count: IndependentGroupCount;
  max_cluster_share: MaxClusterShare;
  primary_source_share: PrimarySourceShare;
  schema_version?: SchemaVersion1;
  scored?: Scored;
  weakest_evidence_ids?: WeakestEvidenceIds;
}
export interface IndependenceCluster {
  evidence_ids: EvidenceIds;
  independence_group: IndependenceGroup;
  schema_version?: SchemaVersion;
  share_of_corpus: ShareOfCorpus;
}
export interface EvidenceAuthorityScore {
  age_days: AgeDays;
  authority_score: AuthorityScore;
  evidence_id: EvidenceId;
  flags?: Flags;
  independence_group: IndependenceGroup1;
  schema_version?: SchemaVersion2;
  source_tier: SourceTier;
}
