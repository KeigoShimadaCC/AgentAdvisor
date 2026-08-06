/* Generated from independent_review.schema.json. Do not edit manually. */

export type DivergentConclusion = string | null;
export type EvidenceIds = string[];
export type Reasoning = string;
export type SchemaVersion = number;
export type UnsupportedClaims = string[];
export type IndependentVerdict = 'concur' | 'concur_with_reservations' | 'dissent';

/**
 * A second opinion on the substance, from a reviewer that never saw the reasoning.
 *
 * The existing ``ReviewReport`` is a conformance check: citations resolve, confidence
 * language matches, worksheet items are all answered.  It catches malformed output but
 * cannot catch a well-formed conclusion the evidence does not support, because nobody
 * re-derives the answer.
 *
 * This role receives the conclusion and the raw evidence ledger but not the thesis
 * history, objections, track divergence or pre-mortem, and answers one question: would
 * you reach this conclusion from this evidence?
 */
export interface IndependentReview {
  divergent_conclusion?: DivergentConclusion;
  evidence_ids?: EvidenceIds;
  reasoning: Reasoning;
  schema_version?: SchemaVersion;
  unsupported_claims?: UnsupportedClaims;
  verdict: IndependentVerdict;
}
