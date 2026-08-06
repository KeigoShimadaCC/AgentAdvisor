import { useEffect } from "react";
import { PHASE_LABELS } from "../copy/terms";
import type { CaseView } from "../generated/case_view";

/**
 * The document title as a progress channel (SPEC-051).
 *
 * A run reaches 191 minutes and the product's honest advice is "you can leave
 * the page". Nothing then told anyone to come back — and the one channel that
 * works whether or not the tab is focused, costs nothing, and needs no
 * permission was showing a constant string.
 *
 * Three states, distinguishable at a glance in a tab strip:
 *  - at a gate:  "● Needs you — <question>"
 *  - running:    "Investigation — <question>"
 *  - finished:   "✓ <question>"
 */
const BASE_TITLE = "AgentAdvisor";

export function caseTitle(view: CaseView | null): string {
  if (!view) return BASE_TITLE;
  const subject = view.decision_question || view.case_id;
  if (view.needs_you !== "none") return `● Needs you — ${subject}`;
  if (view.is_terminal) return `✓ ${subject}`;
  const phase = PHASE_LABELS[view.phase] ?? view.phase;
  return `${phase} — ${subject}`;
}

/** Set the title from a case while mounted, and put it back on the way out. */
export function useCaseTitle(view: CaseView | null): void {
  useEffect(() => {
    const previous = document.title;
    document.title = caseTitle(view);
    return () => {
      // Restored on unmount: a stale "● Needs you" on the library screen would
      // be a lie about a case the user is no longer looking at.
      document.title = previous;
    };
  }, [view]);
}
