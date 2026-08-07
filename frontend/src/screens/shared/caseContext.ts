import { createContext, useContext } from "react";
import type { CaseView } from "../../generated/case_view";
import type { TranslatedEvent } from "../../api/sse";

export interface CaseData {
  view: CaseView;
  events: TranslatedEvent[];
}

/**
 * The loaded case, shared downwards (SPEC-048).
 *
 * Rooms used to be pages, so each one mounted `useCaseView` and opened its own
 * SSE connection to the same case — six streams for one decision, and six
 * separate ideas of what the projection currently said. Now the case surface
 * loads once and rooms render inside it, reading what is already there.
 *
 * The context is optional on purpose: a room rendered on its own (in a unit
 * test, or a future standalone route) falls back to loading for itself.
 */
export const CaseDataContext = createContext<CaseData | null>(null);

export function useCaseData(): CaseData | null {
  return useContext(CaseDataContext);
}
