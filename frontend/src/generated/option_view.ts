/* Generated from option_view.schema.json. Do not edit manually. */

export type Alternative = string;
export type DisconfirmationRank = number | null;
export type DisconfirmingEvidenceIds = string[];
export type DisconfirmingWeight = number | null;
export type Eliminated = boolean;
export type ExpectedValue = number | null;
export type ObjectiveScores = {
  [k: string]: number;
} | null;
export type Rank = number;
export type Rationale = string;
export type WeightedRank = number | null;
export type WeightedScore = number | null;

export interface OptionView {
  alternative: Alternative;
  disconfirmation_rank?: DisconfirmationRank;
  disconfirming_evidence_ids?: DisconfirmingEvidenceIds;
  disconfirming_weight?: DisconfirmingWeight;
  eliminated?: Eliminated;
  expected_value?: ExpectedValue;
  objective_scores?: ObjectiveScores;
  rank: Rank;
  rationale: Rationale;
  weighted_rank?: WeightedRank;
  weighted_score?: WeightedScore;
}
