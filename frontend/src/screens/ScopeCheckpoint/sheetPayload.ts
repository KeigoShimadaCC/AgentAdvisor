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
  /** Per-item ground-rule confirmations (key → confirmed). */
  confirmations: Record<string, boolean>;
  /** Ground-rule keys in display order. */
  groundRuleKeys: string[];
  /** Clarification answers collected upstream (field → value). */
  clarificationAnswers: Record<string, string>;
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
  return edits.alternatives !== undefined || edits.excluded_questions !== undefined;
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
  const hasEdits = edits.alternatives !== undefined || edits.excluded_questions !== undefined;
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
  const optionsChanged =
    state.options.length !== state.originalOptions.length ||
    state.options.some((o, i) => o !== state.originalOptions[i]);
  const questionsStruck = state.excludedQuestions.length > 0;
  return restatementChanged || optionsChanged || questionsStruck;
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
    "ground_rules",
    state.groundRuleKeys.map((k) => `${k}=${state.confirmations[k] ? "confirmed" : "unconfirmed"}`).join("\n"),
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
