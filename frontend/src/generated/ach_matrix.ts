/* Generated from ach_matrix.schema.json. Do not edit manually. */

/**
 * @minItems 2
 */
export type Alternatives = [string, string, ...string[]];
/**
 * @minItems 1
 */
export type Cells = [ACHCell, ...ACHCell[]];
export type Alternative = string;
/**
 * How an evidence record bears on a hypothesis.
 */
export type ACHConsistency =
  'strongly_inconsistent' | 'inconsistent' | 'neutral' | 'consistent' | 'strongly_consistent';
export type EvidenceId = string;
export type Note = string;
export type SchemaVersion = number;
export type DecisionQuestion = string;
/**
 * @minItems 1
 */
export type EvidenceIds = [string, ...string[]];
export type EvidenceId1 = string;
export type Reason = string;
export type SchemaVersion1 = number;
export type ExcludedEvidenceIds = ACHExclusion[];
export type SchemaVersion2 = number;

/**
 * A complete hypothesis × evidence consistency matrix.
 *
 * Completeness is enforced: a partially filled matrix would let the ranking be driven
 * by which cells the model bothered to fill.
 */
export interface ACHMatrix {
  alternatives: Alternatives;
  cells: Cells;
  decision_question: DecisionQuestion;
  evidence_ids: EvidenceIds;
  excluded_evidence_ids?: ExcludedEvidenceIds;
  schema_version?: SchemaVersion2;
}
/**
 * One evidence record scored against one alternative.
 */
export interface ACHCell {
  alternative: Alternative;
  consistency: ACHConsistency;
  evidence_id: EvidenceId;
  note: Note;
  schema_version?: SchemaVersion;
}
/**
 * An evidence record left out of the matrix, and why.
 */
export interface ACHExclusion {
  evidence_id: EvidenceId1;
  reason: Reason;
  schema_version?: SchemaVersion1;
}
