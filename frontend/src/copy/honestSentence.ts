import type { UncertaintyView } from "../generated/uncertainty_view";

/**
 * One honest sentence about how sure this is (SPEC-050).
 *
 * The delivery screen put four uncertainty instruments — a probability band,
 * confidence bands, a source-strength grade and stability dots — between the
 * answer and its reasons. Four encodings is not four times the information; a
 * reader who wants "how sure is this" gets a dashboard and has to do the
 * synthesis the product exists to do.
 *
 * The composition rule, against north star Section 9: **the sentence may not
 * claim more than the encodings carry.** So it says which measures were
 * assessed and names the weakest one, rather than combining them into a score.
 * There is no arithmetic here on purpose — averaging a source grade with a
 * stability share would produce a number with no referent, which is exactly the
 * kind of false precision the four separate encodings exist to avoid.
 *
 * A not-assessed measure is named as not assessed. That is the honest reading
 * and it is also the useful one: "stability was not assessed" tells a reader
 * what to go and check.
 */

export interface HonestSentence {
  /** The sentence itself. */
  text: string;
  /** Which measures had no assessment, for the caller to render as gaps. */
  notAssessed: string[];
}

function isAssessed(measure: { kind?: string } | undefined): boolean {
  return measure != null && measure.kind !== "not_assessed";
}

/** Words for a 0–1 confidence. Deliberately coarse: the value is not precise. */
function confidenceWords(value: number): string {
  if (value >= 0.8) return "high confidence";
  if (value >= 0.6) return "moderate confidence";
  if (value >= 0.4) return "limited confidence";
  return "low confidence";
}

function evidenceWords(value: number): string {
  if (value >= 0.8) return "strong evidence";
  if (value >= 0.6) return "reasonable evidence";
  if (value >= 0.4) return "thin evidence";
  return "weak evidence";
}

function stabilityWords(share: number): string {
  if (share >= 0.9) return "held across every sensitivity run";
  if (share >= 0.7) return "held across most sensitivity runs";
  if (share >= 0.5) return "held in only about half the sensitivity runs";
  return "did not hold across sensitivity runs";
}

export function honestSentence(uncertainty: UncertaintyView | null | undefined): HonestSentence {
  if (!uncertainty) {
    return {
      text: "None of the four uncertainty measures was assessed for this case, so there is nothing here to tell you how sure this is.",
      notAssessed: ["recommendation confidence", "evidence strength", "stability", "probability"],
    };
  }

  const notAssessed: string[] = [];
  const clauses: string[] = [];

  const recommendation = uncertainty.recommendation_confidence;
  if (isAssessed(recommendation) && "value" in recommendation) {
    clauses.push(confidenceWords(recommendation.value));
  } else {
    notAssessed.push("recommendation confidence");
  }

  const evidence = uncertainty.evidence_confidence;
  if (isAssessed(evidence) && "value" in evidence) {
    clauses.push(evidenceWords(evidence.value));
  } else {
    notAssessed.push("evidence strength");
  }

  const stability = uncertainty.model_stability;
  const stabilityClause =
    isAssessed(stability) && "share" in stability ? stabilityWords(stability.share) : null;
  if (!stabilityClause) notAssessed.push("stability");

  if (clauses.length === 0 && !stabilityClause) {
    return {
      text: "None of the four uncertainty measures was assessed for this case, so there is nothing here to tell you how sure this is.",
      notAssessed,
    };
  }

  const head =
    clauses.length > 0
      ? `This is a recommendation made with ${joinClauses(clauses)}`
      : "This recommendation's confidence and evidence were not assessed";
  const tail = stabilityClause ? `, and it ${stabilityClause}` : "";
  const gap =
    notAssessed.length > 0
      ? ` ${capitalise(joinClauses(notAssessed))} ${notAssessed.length === 1 ? "was" : "were"} not assessed.`
      : "";

  return { text: `${head}${tail}.${gap}`, notAssessed };
}

function joinClauses(parts: string[]): string {
  if (parts.length === 1) return parts[0];
  if (parts.length === 2) return `${parts[0]} and ${parts[1]}`;
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

function capitalise(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}
