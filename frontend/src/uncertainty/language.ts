import {
  PROBABILITY_PHRASES,
  CONFIDENCE_BANDS,
  SOURCE_GRADES,
  SOURCE_GRADE_MEANINGS,
  bandFor,
  NOT_ASSESSED_DEFAULT,
} from "../copy/uncertainty";
import type {
  AssessedConfidence,
  AssessedStability,
  NotAssessed,
  ProbabilityView,
} from "../generated/uncertainty_view";

/**
 * The uncertainty grammar (SPEC-054).
 *
 * The product's differentiator is that it keeps four kinds of uncertainty
 * separate and refuses to collapse them into one number. That commitment
 * reached the screen as four unrelated widgets in a grid on one route, built
 * from five components sharing no visual grammar — so a user learned four
 * encodings once and never saw them again.
 *
 * This is the mapping, as data, because the property that matters — that the
 * same thing always looks the same — is only enforceable if there is one place
 * it lives. Four kinds of value, four idioms:
 *
 *  - **band** — an ordinal position among named steps (confidence).
 *  - **range** — a point *or* an interval, rendered visibly differently,
 *    because Section 9's point-XOR-interval rule is a claim about what is
 *    known, not a formatting preference.
 *  - **countable** — marks a reader can literally count, for anything derived
 *    from a run count. "9 of 10 runs" is a fact; "90%" is a number that invites
 *    comparison with the other three measures, which is exactly what must not
 *    happen.
 *  - **grade** — an ordinal judgement as a letter, never a number dressed as a
 *    measurement.
 *
 * And one sentinel: **not_assessed**, always explicit, never a zero, never an
 * empty state.
 *
 * The rule this file exists to hold: **no encoding combines two measures.**
 * Four measures that disagree are the honest output, and a dial averaging them
 * would destroy the property `NotAssessed` and `AssessedStability` were built
 * to protect.
 */

export type Scale = "inline" | "summary" | "full";

export type Encoding =
  | { kind: "band"; label: string; index: number; total: number; basis: string }
  | {
      kind: "range";
      /** Exactly one of these is set. */
      point: number | null;
      low: number | null;
      high: number | null;
      phrase: string;
      method: string;
    }
  | { kind: "countable"; filled: number; total: number; caption: string }
  | { kind: "grade"; letter: string; meaning: string; basis: string }
  | { kind: "not_assessed"; reason: string };

function isNotAssessed(value: { kind?: string } | null | undefined): boolean {
  return value == null || value.kind === "not_assessed";
}

function reasonOf(value: NotAssessed | null | undefined): string {
  return value?.reason || NOT_ASSESSED_DEFAULT;
}

/** Recommendation confidence → a band. */
export function encodeConfidence(
  value: AssessedConfidence | NotAssessed | null | undefined,
): Encoding {
  if (isNotAssessed(value)) return { kind: "not_assessed", reason: reasonOf(value as NotAssessed) };
  const assessed = value as AssessedConfidence;
  const band = bandFor(CONFIDENCE_BANDS, assessed.value);
  const index = band ? CONFIDENCE_BANDS.indexOf(band) : -1;
  return {
    kind: "band",
    label: band?.label ?? "Not assessed",
    index,
    total: CONFIDENCE_BANDS.length,
    basis: assessed.basis ?? "",
  };
}

/** Evidence strength → a grade. */
export function encodeEvidence(
  value: AssessedConfidence | NotAssessed | null | undefined,
): Encoding {
  if (isNotAssessed(value)) return { kind: "not_assessed", reason: reasonOf(value as NotAssessed) };
  const assessed = value as AssessedConfidence;
  const grade = bandFor(SOURCE_GRADES, assessed.value);
  const letter = grade?.label ?? "—";
  return {
    kind: "grade",
    letter,
    meaning: SOURCE_GRADE_MEANINGS[letter] ?? "",
    basis: assessed.basis ?? "",
  };
}

/** Model stability → countable marks, never a percentage. */
export function encodeStability(
  value: AssessedStability | NotAssessed | null | undefined,
): Encoding {
  if (isNotAssessed(value)) return { kind: "not_assessed", reason: reasonOf(value as NotAssessed) };
  const assessed = value as AssessedStability;
  return {
    kind: "countable",
    filled: assessed.runs_supporting,
    total: assessed.runs_total,
    caption: `held in ${assessed.runs_supporting} of ${assessed.runs_total} sensitivity runs`,
  };
}

/**
 * Outcome probability → a range.
 *
 * Point and interval are preserved as they arrive. A `ProbabilityView` with a
 * point renders as a point and one with an interval renders as an interval, and
 * the component must not turn an interval into its midpoint — the interval is
 * the statement that the midpoint is not known.
 */
export function encodeProbability(
  value: ProbabilityView | NotAssessed | null | undefined,
): Encoding {
  if (value == null || (value as NotAssessed).kind === "not_assessed") {
    return { kind: "not_assessed", reason: reasonOf(value as NotAssessed) };
  }
  const probability = value as ProbabilityView;
  const point = probability.point ?? null;
  const low = probability.interval_low ?? null;
  const high = probability.interval_high ?? null;
  // The phrase describes the point when there is one; an interval has no single
  // phrase, and inventing one from its midpoint is the collapse this forbids.
  const band = point != null ? bandFor(PROBABILITY_PHRASES, point) : null;
  return {
    kind: "range",
    point,
    low,
    high,
    phrase: band?.label ?? "",
    method: probability.method ?? "",
  };
}

/** Whether an encoding carries a real assessment. */
export function isAssessed(encoding: Encoding): boolean {
  return encoding.kind !== "not_assessed";
}

/**
 * The class list for an encoding at a scale.
 *
 * Every consumer goes through this, which is what makes "the same measure looks
 * the same everywhere" checkable rather than aspirational.
 */
export function encodingClass(encoding: Encoding, scale: Scale): string {
  return `u-${encoding.kind} u-scale-${scale}`;
}
