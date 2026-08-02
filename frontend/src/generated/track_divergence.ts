/* Generated from track_divergence.schema.json. Do not edit manually. */

export type Agreement = boolean;
export type DivergenceSummary = string;
/**
 * @minItems 2
 */
export type Positions = [TrackPosition, TrackPosition, ...TrackPosition[]];
export type Model = string;
export type ModelFamily = string;
export type PreferredAlternative = string;
export type RecommendationConfidence = number;
export type SchemaVersion = number;
export type TopReason = string;
export type TrackId = string;
export type ReconciledAlternative = string | null;
export type SchemaVersion1 = number;
export type Stage = string;

/**
 * Result of running two independent theses on different model families.
 *
 * This is a diversity signal, not a probability. It never feeds ``model_stability``
 * and the positions are never averaged; disagreement is reported as disagreement.
 */
export interface TrackDivergence {
  agreement: Agreement;
  divergence_summary: DivergenceSummary;
  positions: Positions;
  reconciled_alternative?: ReconciledAlternative;
  schema_version?: SchemaVersion1;
  stage: Stage;
}
export interface TrackPosition {
  model: Model;
  model_family: ModelFamily;
  preferred_alternative: PreferredAlternative;
  recommendation_confidence: RecommendationConfidence;
  schema_version?: SchemaVersion;
  top_reason: TopReason;
  track_id: TrackId;
}
