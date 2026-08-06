/* Generated from alternative_assessment.schema.json. Do not edit manually. */

export type Alternative = string;
export type ObjectiveScores = {
  [k: string]: number;
} | null;
export type Rank = number;
export type Rationale = string;
export type SchemaVersion = number;

export interface AlternativeAssessment {
  alternative: Alternative;
  objective_scores?: ObjectiveScores;
  rank: Rank;
  rationale: Rationale;
  schema_version?: SchemaVersion;
}
