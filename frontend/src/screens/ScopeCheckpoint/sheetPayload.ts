/**
 * Payload-assembly and summary-hash helpers for the scope checkpoint sheet.
 *
 * Kept pure (no React) so they can be unit-tested directly.  All user input
 * serializes into the existing ``FramingApproval`` payload shapes:
 *   - prose edits → ``edits``
 *   - clarification answers → ``clarification_answers``
 *   - per-item confirmations → the checkpoint POST's ``confirmations`` list
 *   - a ``summary_hash`` of the rendered sheet content
 */

import type { ScopeCheckpointPayload } from "../../api/client";

/**
 * The editable sheet state, mirrored from the component.  Kept here as a
 * plain interface so the assembly function is testable without React.
 */
export interface SheetState {
  /** Edited restatement prose (may equal the original). */
  restatement: string;
  /** Current option strings (some may be removed). */
  options: string[];
  /** Original option strings, for diffing. */
  originalOptions: string[];
  /** Outline question strings that have been struck through. */
  excludedQuestions: string[];
  /** Free-text notes the user attached to options (option text → note). */
  optionAnnotations: Record<string, string>;
  /** Ground-rule values the user overrode on the sheet (key → new value). */
  groundRuleEdits: Record<string, string>;
  /** Per-item ground-rule confirmations (key → confirmed). */
  confirmations: Record<string, boolean>;
  /** Ground-rule keys in display order. */
  groundRuleKeys: string[];
  /** Clarification answers collected upstream (field → value). */
  clarificationAnswers: Record<string, string>;
  /**
   * SPEC-038. Points allocated to each objective (objective → points).  Empty
   * when the framing proposed no weights and the user set none, in which case
   * the case runs without a value model exactly as before.
   */
  objectiveWeights?: Record<string, number>;
  /** The weights the framing proposed, for diffing. */
  originalObjectiveWeights?: Record<string, number>;
}

/** Total points allocated across objectives. */
export function weightTotal(weights: Record<string, number> | undefined): number {
  if (!weights) return 0;
  return Object.values(weights).reduce((sum, n) => sum + (Number.isFinite(n) ? n : 0), 0);
}

/**
 * True when the allocation is usable: it sums to exactly {@link WEIGHT_BUDGET}
 * and every objective carries a positive share.
 *
 * An empty allocation is valid — it means "no value model", not "invalid".
 */
export function weightsAreValid(weights: Record<string, number> | undefined): boolean {
  if (!weights || Object.keys(weights).length === 0) return true;
  if (Object.values(weights).some((n) => !Number.isFinite(n) || n <= 0)) return false;
  return weightTotal(weights) === WEIGHT_BUDGET;
}

/** The number of points the user distributes across objectives. */
export const WEIGHT_BUDGET = 100;

/** Weights with zero/blank entries dropped, in stable key order. */
function meaningfulWeights(state: SheetState): Array<[string, number]> {
  return Object.entries(state.objectiveWeights ?? {})
    .filter(([, points]) => Number.isFinite(points) && points > 0)
    .sort(([a], [b]) => a.localeCompare(b));
}

/** True when the user changed the allocation the framing proposed. */
function weightsChanged(state: SheetState): boolean {
  const current = Object.fromEntries(meaningfulWeights(state));
  const original = state.originalObjectiveWeights ?? {};
  const keys = new Set([...Object.keys(current), ...Object.keys(original)]);
  for (const key of keys) {
    if (current[key] !== original[key]) return true;
  }
  return false;
}

/** Annotations with the blank entries dropped, in stable key order. */
function meaningfulAnnotations(state: SheetState): Array<[string, string]> {
  return Object.entries(state.optionAnnotations)
    .map(([option, note]) => [option, note.trim()] as [string, string])
    .filter(([, note]) => note.length > 0)
    .sort(([a], [b]) => a.localeCompare(b));
}

/** Ground-rule overrides with blanks dropped, in stable key order. */
function meaningfulGroundRuleEdits(state: SheetState): Array<[string, string]> {
  return Object.entries(state.groundRuleEdits)
    .map(([key, value]) => [key, value.trim()] as [string, string])
    .filter(([, value]) => value.length > 0)
    .sort(([a], [b]) => a.localeCompare(b));
}

/**
 * Build the ``edits`` object from the sheet state.
 *
 * Edits are only populated when the user actually changed something:
 *   - ``question`` — restated prose
 *   - ``alternatives`` — the surviving option list
 *   - ``excluded_questions`` — struck outline items
 */
export function buildEdits(state: SheetState): Record<string, unknown> {
  const edits: Record<string, unknown> = {};

  // We always send the (possibly edited) restatement as ``question`` so the
  // engine can adopt the user's wording.  The diff is handled by the caller
  // deciding whether to route through the revision path.
  edits.question = state.restatement.trim();

  // Only include alternatives if they changed.
  const sameOptions =
    state.options.length === state.originalOptions.length &&
    state.options.every((o, i) => o === state.originalOptions[i]);
  if (!sameOptions) {
    edits.alternatives = state.options;
  }

  if (state.excludedQuestions.length > 0) {
    edits.excluded_questions = state.excludedQuestions;
  }

  const annotations = meaningfulAnnotations(state);
  if (annotations.length > 0) {
    edits.option_annotations = Object.fromEntries(annotations);
  }

  // Ground-rule overrides go up as first-class spec fields (``deadline``,
  // ``risk_tolerance``, ``reversibility``) so the revised framing adopts the
  // constraint the user actually signed off on.
  for (const [key, value] of meaningfulGroundRuleEdits(state)) {
    edits[key] = value;
  }

  // SPEC-038: the elicited value model rides the same edits path, so a weight
  // change is auditable rather than silent.
  if (weightsChanged(state)) {
    edits.objective_weights = Object.fromEntries(meaningfulWeights(state));
  }

  return edits;
}

/**
 * True when the sheet has edits that require a framing revision before
 * a clean sign can happen (options changed or questions struck).
 *
 * Restatement edits are checked separately via {@link needsRevision} which
 * compares against the original prose.
 */
export function hasSheetEdits(state: SheetState): boolean {
  const edits = buildEdits(state);
  // ``question`` is always present, so anything else in the object is a real
  // edit — that keeps this in step with buildEdits as new edit kinds are added.
  return Object.keys(edits).some((key) => key !== "question");
}

/**
 * The list of confirmed ground-rule keys, in display order.
 */
export function confirmedKeys(state: SheetState): string[] {
  return state.groundRuleKeys.filter((k) => state.confirmations[k] === true);
}

/**
 * True when every ground-rule item has been individually confirmed.
 */
export function allGroundRulesConfirmed(state: SheetState): boolean {
  return state.groundRuleKeys.length > 0 && confirmedKeys(state).length === state.groundRuleKeys.length;
}

/**
 * Assemble the full approve payload (clean sign, no edits).
 */
export function buildApprovePayload(
  state: SheetState,
  summaryHash: string,
  approvedBy = "user",
): ScopeCheckpointPayload {
  return {
    decision: "approve",
    confirmations: confirmedKeys(state),
    summary_hash: summaryHash,
    approved_by: approvedBy,
  };
}

/**
 * Assemble the revision payload (edits and/or clarification answers).
 */
export function buildRevisionPayload(
  state: SheetState,
): ScopeCheckpointPayload {
  const edits = buildEdits(state);
  const hasEdits = hasSheetEdits(state);
  const hasAnswers = Object.keys(state.clarificationAnswers).length > 0;

  // If both edits and answers exist, "edit" takes precedence (matches the
  // engine's FramingDecision logic).
  const decision = hasEdits ? "edit" : "answer_clarifications";

  return {
    decision,
    edits: hasEdits ? edits : {},
    clarification_answers: hasAnswers ? state.clarificationAnswers : {},
  };
}

/**
 * Determine whether the sheet needs a revision pass before a clean sign.
 *
 * A revision is needed when the restatement prose changed, options were
 * removed/added/reordered, or outline questions were struck.
 */
export function needsRevision(
  state: SheetState,
  originalRestatement: string,
): boolean {
  const restatementChanged = state.restatement.trim() !== originalRestatement.trim();
  return restatementChanged || hasSheetEdits(state);
}

/**
 * A canonical, deterministic serialization of the rendered sheet content.
 *
 * The exact algorithm is not mandated by the spec; it only needs to be a
 * stable digest of what the user saw when they signed, so the consent
 * moment is reconstructable.  We join the sheet sections in a fixed order.
 */
export function canonicalSheetContent(state: SheetState): string {
  return [
    "restatement",
    state.restatement.trim(),
    "options",
    state.options.join("\n"),
    "excluded_questions",
    state.excludedQuestions.join("\n"),
    "option_annotations",
    meaningfulAnnotations(state).map(([option, note]) => `${option}=${note}`).join("\n"),
    "ground_rule_edits",
    meaningfulGroundRuleEdits(state).map(([key, value]) => `${key}=${value}`).join("\n"),
    "ground_rules",
    state.groundRuleKeys.map((k) => `${k}=${state.confirmations[k] ? "confirmed" : "unconfirmed"}`).join("\n"),
    "objective_weights",
    meaningfulWeights(state).map(([name, points]) => `${name}=${points}`).join("\n"),
  ].join("\n");
}

/**
 * Compute a short deterministic hash (djb2 variant) of the sheet content.
 *
 * Synchronous so it can be used inline in event handlers and tests.  Returns
 * a hex string.
 */
export function computeSummaryHash(content: string): string {
  let hash = 5381;
  for (let i = 0; i < content.length; i++) {
    hash = ((hash << 5) + hash) ^ content.charCodeAt(i);
    hash = hash >>> 0; // keep unsigned 32-bit
  }
  return hash.toString(16).padStart(8, "0");
}
