/**
 * The words for uncertainty (SPEC-054).
 *
 * Held in one place so a phrase cannot drift between screens. A probability
 * described as "Likely" on the answer and "Probable" in a room is two different
 * claims to a reader, and nothing in the code would have flagged it.
 *
 * These are the *existing* thresholds from `copy/terms.ts`, moved rather than
 * re-chosen: this spec is presentation only, and re-drawing a band boundary
 * would silently change what every historical case is reported to have said.
 */

export interface Band {
  /** Inclusive lower bound. */
  threshold: number;
  label: string;
  key: string;
}

/** Verbal probability. Section 9's vocabulary, ordered high to low. */
export const PROBABILITY_PHRASES: Band[] = [
  { threshold: 0.9, label: "Very likely", key: "very_likely" },
  { threshold: 0.7, label: "Likely", key: "likely" },
  { threshold: 0.55, label: "More likely than not", key: "more_likely_than_not" },
  { threshold: 0.45, label: "Roughly even odds", key: "even" },
  { threshold: 0.3, label: "Unlikely", key: "unlikely" },
  { threshold: 0.1, label: "Quite unlikely", key: "quite_unlikely" },
  { threshold: 0, label: "Very unlikely", key: "very_unlikely" },
];

/** Recommendation confidence. Five steps, never a percentage. */
export const CONFIDENCE_BANDS: Band[] = [
  { threshold: 0.85, label: "Very high", key: "very_high" },
  { threshold: 0.65, label: "High", key: "high" },
  { threshold: 0.45, label: "Moderate", key: "moderate" },
  { threshold: 0.25, label: "Low", key: "low" },
  { threshold: 0, label: "Very low", key: "very_low" },
];

/** Evidence strength. An ordinal judgement, so a letter rather than a number. */
export const SOURCE_GRADES: Band[] = [
  { threshold: 0.9, label: "A", key: "a" },
  { threshold: 0.75, label: "B", key: "b" },
  { threshold: 0.55, label: "C", key: "c" },
  { threshold: 0.35, label: "D", key: "d" },
  { threshold: 0, label: "F", key: "f" },
];

/** What each grade means, so a letter is not asked to carry it alone. */
export const SOURCE_GRADE_MEANINGS: Record<string, string> = {
  A: "Primary sources, independently corroborated.",
  B: "Solid: a mix of primary and reputable secondary sources.",
  C: "Mixed: usable, with gaps or concentration worth knowing about.",
  D: "Thin: few sources, or several tracing to the same origin.",
  F: "Weak: the evidence does not carry the conclusion on its own.",
};

/** The band a value falls in, or null when there is no value. */
export function bandFor(bands: Band[], value: number | null | undefined): Band | null {
  if (value == null || Number.isNaN(value)) return null;
  return bands.find((band) => value >= band.threshold) ?? bands[bands.length - 1];
}

export const NOT_ASSESSED_MARK = "—";

/** The one sentence the *Not assessed* stamp says when it has no reason of its own. */
export const NOT_ASSESSED_DEFAULT = "This was not assessed for this case.";
