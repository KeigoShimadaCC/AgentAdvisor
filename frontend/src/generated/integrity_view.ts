/* Generated from integrity_view.schema.json. Do not edit manually. */

export type Disclosure = {
  [k: string]: unknown;
} | null;
export type Findings = {
  [k: string]: unknown;
}[];
export type Outcome = string;
export type Stage = string;
export type Gates = GateSummaryView[];
export type DivergentConclusion = string | null;
export type EvidenceIds = string[];
export type Reasoning = string;
export type UnsupportedClaims = string[];
export type Verdict = string;
export type ReviewAccepted = boolean | null;
export type ReviewBlockingFindings = {
  [k: string]: unknown;
}[];
export type ReviewDefects = {
  [k: string]: unknown;
}[];
export type ReviewOutcome = string | null;

export interface IntegrityView {
  disclosure?: Disclosure;
  gates?: Gates;
  independent_review?: IndependentReviewView | null;
  review_accepted?: ReviewAccepted;
  review_blocking_findings?: ReviewBlockingFindings;
  review_defects?: ReviewDefects;
  review_outcome?: ReviewOutcome;
}
export interface GateSummaryView {
  findings?: Findings;
  outcome: Outcome;
  stage: Stage;
}
/**
 * SPEC-039's second opinion, structured (SPEC-053).
 *
 * Phase 8 rendered this into a ``brief_sections`` entry as prose, which meant
 * the one verdict that can *block delivery* was reachable only by reading a
 * paragraph. A blocking state has to be a field, or every consumer has to
 * parse English to find out whether it may show a signature button.
 */
export interface IndependentReviewView {
  divergent_conclusion?: DivergentConclusion;
  evidence_ids?: EvidenceIds;
  reasoning: Reasoning;
  unsupported_claims?: UnsupportedClaims;
  verdict: Verdict;
}
