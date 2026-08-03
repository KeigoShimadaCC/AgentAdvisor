/* Generated from option_view.schema.json. Do not edit manually. */

export type Alternative = string;
export type Eliminated = boolean;
export type ExpectedValue = number | null;
export type Rank = number;
export type Rationale = string;

export interface OptionView {
  alternative: Alternative;
  eliminated?: Eliminated;
  expected_value?: ExpectedValue;
  rank: Rank;
  rationale: Rationale;
}
