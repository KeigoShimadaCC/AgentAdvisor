import { useEffect, useState } from "react";
import { api, type ErrorResponse } from "../../api/client";
import { SSEClient, type TranslatedEvent } from "../../api/sse";
import type { CaseView } from "../../generated/case_view";

export interface CaseViewState {
  view: CaseView | null;
  events: TranslatedEvent[];
  loading: boolean;
  error: string | null;
}

/**
 * Shared loader for the CaseView projection + live SSE event stream.
 *
 * Every room and the inspector consume this so the projection is fetched
 * once per navigation and live events append new-content markers.
 */
export function useCaseView(caseId: string | undefined): CaseViewState {
  const [view, setView] = useState<CaseView | null>(null);
  const [events, setEvents] = useState<TranslatedEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    setEvents([]);
    api
      .getCaseView(caseId)
      .then((v) => setView(v))
      .catch((e: ErrorResponse) => setError(e.detail ?? e.error))
      .finally(() => setLoading(false));

    const sse = new SSEClient(caseId, {
      onEvent: (event) => setEvents((prev) => [...prev, event]),
    });
    sse.connect();
    return () => sse.disconnect();
  }, [caseId]);

  return { view, events, loading, error };
}
