import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type ErrorResponse } from "../../api/client";
import { SSEClient, type ConnectionState, type TranslatedEvent } from "../../api/sse";
import { INITIAL_NARRATION, reduceNarration, type NarrationState } from "../../narration/reducer";
import type { CaseView } from "../../generated/case_view";

/** How long to wait for a burst of events to settle before refetching. */
const REFETCH_DEBOUNCE_MS = 250;

/**
 * How many raw events to retain (SPEC-055).
 *
 * The buffer used to be unbounded and copied on every append, which is O(n²)
 * work and O(n) memory in the length of a case — invisible until a 191-minute
 * run with SPEC-046's twenty-second progress heartbeats, at which point the tab
 * is holding thousands of objects and re-allocating the array for each new one.
 *
 * Nothing is lost that anyone reads: the narrator's reducer folds *every* event
 * into state as it arrives, so counters, loops and announcements are computed
 * from the whole stream regardless of what is retained. What the buffer feeds
 * is the transcript and the margin — both of which show the recent end — and
 * the inspector, which fetches records by id rather than scanning.
 */
const MAX_RETAINED_EVENTS = 500;

/**
 * How long a freshly created case may produce nothing before it is called
 * stalled (SPEC-055).
 *
 * SPEC-046 made creation return 202 as soon as the case is durable, which is
 * right — but it opened a gap between "created" and "running" that nothing
 * watched. A worker that dies at startup leaves a case that looks like it is
 * about to begin, forever.
 *
 * The value is derived from what actually happens rather than chosen: the
 * fixture case's first audit event lands well inside a second, and the stub
 * pipeline's inside two. Ninety seconds is roughly an order of magnitude above
 * the slowest first invocation observed on a real backend, which is the margin
 * that keeps a slow start from being reported as a failure. It is deliberately
 * generous: a false "stalled" on a working case is worse than a late one on a
 * broken case, because it teaches people to ignore the signal.
 */
export const STALL_WINDOW_MS = 90_000;

export { MAX_RETAINED_EVENTS };

export interface CaseViewState {
  view: CaseView | null;
  events: TranslatedEvent[];
  narration: NarrationState;
  connection: ConnectionState;
  loading: boolean;
  error: string | null;
  /** SPEC-055: the typed failure, so a screen can tell "not running" from "not found". */
  failure: ErrorResponse | null;
  /** Retry after a failure, without a reload. */
  retry: () => void;
  /** SPEC-055: created, but nothing has happened for {@link STALL_WINDOW_MS}. */
  stalled: boolean;
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
  const [failure, setFailure] = useState<ErrorResponse | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [stalled, setStalled] = useState(false);

  // Refs so the debounce survives re-renders without re-subscribing the stream.
  const refetchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inFlight = useRef(false);
  const pending = useRef(false);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;

    setLoading(true);
    setError(null);
    setFailure(null);
    setStalled(false);
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
        if (!cancelled) {
          setError(e.detail ?? e.error);
          setFailure(e);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    const scheduleRefetch = () => {
      if (refetchTimer.current !== null) clearTimeout(refetchTimer.current);
      refetchTimer.current = setTimeout(fetchView, REFETCH_DEBOUNCE_MS);
    };

    // Armed on mount and disarmed by the first event. A case that is already
    // running has events immediately, so this only ever fires on the gap
    // non-blocking creation opened.
    let stallTimer: ReturnType<typeof setTimeout> | null = setTimeout(() => {
      if (!cancelled) setStalled(true);
    }, STALL_WINDOW_MS);

    const sse = new SSEClient(caseId, {
      onEvent: (event) => {
        if (cancelled) return;
        if (stallTimer !== null) {
          clearTimeout(stallTimer);
          stallTimer = null;
          setStalled(false);
        }
        setEvents((prev) => {
          const next = prev.length >= MAX_RETAINED_EVENTS ? prev.slice(1) : prev.slice();
          next.push(event);
          return next;
        });
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
      if (stallTimer !== null) clearTimeout(stallTimer);
      sse.disconnect();
    };
    // `view` is read inside fetchView's catch only to decide whether an error is
    // fatal; including it would resubscribe the stream on every projection
    // update, which is exactly what this hook exists to avoid.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  return useMemo(
    () => ({ view, events, narration, connection, loading, error, failure, retry, stalled }),
    [view, events, narration, connection, loading, error, failure, retry, stalled],
  );
}
