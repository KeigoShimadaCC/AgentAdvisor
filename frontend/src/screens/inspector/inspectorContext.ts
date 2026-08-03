import { createContext, useContext } from "react";

export interface InspectorContextValue {
  /** Open the slide-over for a given artifact id. */
  open: (artifactId: string) => void;
  /** Close the slide-over. */
  close: () => void;
  /** The currently-open artifact id, or null. */
  openId: string | null;
}

export const InspectorContext = createContext<InspectorContextValue | null>(null);

/**
 * Open the record inspector for an artifact id.
 *
 * Throws if used outside an `InspectorHost` so missing wiring fails loudly
 * rather than silently swallowing citation clicks.
 */
export function useInspector(): InspectorContextValue {
  const ctx = useContext(InspectorContext);
  if (!ctx) {
    throw new Error("useInspector must be used inside an <InspectorHost>");
  }
  return ctx;
}
