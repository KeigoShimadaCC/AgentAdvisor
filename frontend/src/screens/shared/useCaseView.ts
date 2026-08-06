import { useEffect, useMemo, useRef, useState } from "react";
import { api, type ErrorResponse } from "../../api/client";
import { SSEClient, type ConnectionState, type TranslatedEvent } from "../../api/sse";
import { INITIAL_NARRATION, reduceNarration, type NarrationState } from "../../narration/reducer";
import type { CaseView } from "../../generated/case_view";

/** How long to wait for a burst of events to settle before refetching. */
const REFETCH_DEBOUNCE_MS = 250;

export interface CaseViewState {
  view: CaseView | null;
  events: TranslatedEvent[];
  narration: NarrationState;
  connection: ConnectionState;
  loading: boolean;
  error: string | null;
}

/**
 * The case's live state: projection plus stream (SPEC-047).
 *
 * Before this, the projection was fetched once per mount and never again.
 * Events accumulated in a list underneath a page that never changed, so the
 * "living brief" was frozen at page load and a finished case looked identical
 * to a stalled one. The fix is small — refetch when something meaningful
 * happens — and it is the single highest-value repair in the phase.
 *
 * Three properties are deliberate:
 *
 *  - **Debounced.** A burst of events produces one request, not one per event.
 *  - **Non-blanking.** The previous view stays on screen while the next one
 *    loads, so the reader never watches their brief disappear and come back.
 *  - **Technical events do not trigger a fetch.** Retries and bookkeeping change
 *    the Method room, not the projection, and refetching on them would be pure
 *    load.
 */
export function useCaseView(caseId: string | undefined): CaseViewState {
  const [view, setView] = useState<CaseView | null>(null);
  const [events, setEvents] = useState<TranslatedEvent[]>([]);
  const [narration, setNarration] = useState<NarrationState>(INITIAL_NARRATION);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Refs so the debounce survives re-renders without re-subscribing the stream.
  const refetchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inFlight = useRef(false);
  const pending = useRef(false);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;

    setLoading(true);
    setError(null);
    setEvents([]);
    setNarration(INITIAL_NARRATION);

    const fetchView = () => {
      if (cancelled) return;
      if (inFlight.current) {
        // Coalesce: one more fetch after the current one lands, not a queue.
        pending.current = true;
        return;
      }
      inFlight.current = true;
      api
        .getCaseView(caseId)
        .then((v) => {
          if (!cancelled) setView(v);
        })
        .catch((e: ErrorResponse) => {
          // A failed refetch must not blank a good view; the previous one is
          // stale at worst, and the connection state says so.
          if (!cancelled && view === null) setError(e.detail ?? e.error);
        })
        .finally(() => {
          inFlight.current = false;
          if (pending.current && !cancelled) {
            pending.current = false;
            fetchView();
          }
        });
    };

    api
      .getCaseView(caseId)
      .then((v) => {
        if (!cancelled) setView(v);
      })
      .catch((e: ErrorResponse) => {
        if (!cancelled) setError(e.detail ?? e.error);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    const scheduleRefetch = () => {
      if (refetchTimer.current !== null) clearTimeout(refetchTimer.current);
      refetchTimer.current = setTimeout(fetchView, REFETCH_DEBOUNCE_MS);
    };

    const sse = new SSEClient(caseId, {
      onEvent: (event) => {
        if (cancelled) return;
        setEvents((prev) => [...prev, event]);
        setNarration((prev) => reduceNarration(prev, event));
        // Only content-bearing events move the projection.
        if (!event.technical) scheduleRefetch();
      },
      onConnectionChange: (state) => {
        if (!cancelled) setConnection(state);
      },
    });
    sse.connect();

    return () => {
      cancelled = true;
      if (refetchTimer.current !== null) clearTimeout(refetchTimer.current);
      sse.disconnect();
    };
    // `view` is read inside fetchView's catch only to decide whether an error is
    // fatal; including it would resubscribe the stream on every projection
    // update, which is exactly what this hook exists to avoid.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  return useMemo(
    () => ({ view, events, narration, connection, loading, error }),
    [view, events, narration, connection, loading, error],
  );
}
