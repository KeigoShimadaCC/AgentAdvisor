/* Generated from thesis_revision.schema.json. Do not edit manually. */

export type Changed = boolean;
export type ChangedBecauseAssumptionIds = string[];
export type ChangedBecauseEvidenceIds = string[];
export type ChangedBecauseObjectionIds = string[];
export type EvidenceConfidence = number;
export type PreferredAlternative = string;
export type PreviousAlternative = string | null;
export type RationaleDigest = string[];
export type RecommendationConfidence = number;
export type RecordedAt = string;
export type Revision = number;
export type SchemaVersion = number;
export type ThesisTrigger = 'provisional' | 'reconciliation' | 'investigation_wave' | 'preliminary' | 'repair';

/**
 * One entry in the append-only thesis ledger.
 *
 * The ledger makes belief movement inspectable: what the system thought, when it
 * changed its mind, and what changed it.
 */
export interface ThesisRevision {
  changed: Changed;
  changed_because_assumption_ids?: ChangedBecauseAssumptionIds;
  changed_because_evidence_ids?: ChangedBecauseEvidenceIds;
  changed_because_objection_ids?: ChangedBecauseObjectionIds;
  evidence_confidence: EvidenceConfidence;
  preferred_alternative: PreferredAlternative;
  previous_alternative?: PreviousAlternative;
  rationale_digest?: RationaleDigest;
  recommendation_confidence: RecommendationConfidence;
  recorded_at: RecordedAt;
  revision: Revision;
  schema_version?: SchemaVersion;
  trigger: ThesisTrigger;
}
