import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useCaseView, MAX_RETAINED_EVENTS, STALL_WINDOW_MS } from "./useCaseView";
import type { TranslatedEvent } from "../../api/sse";

/**
 * The living projection (SPEC-047).
 *
 * The defect this fixes: `useCaseView` fetched the projection once per mount
 * and never again, so the brief was frozen at page load while events piled up
 * in a list underneath it. A finished case and a stalled one rendered
 * identically. These tests hold the three properties of the fix — it refetches
 * on content, it coalesces bursts, and it never blanks the screen.
 */

const emitted: ((event: TranslatedEvent) => void)[] = [];
let getCaseViewCalls = 0;

vi.mock("../../api/client", () => ({
  api: {
    getCaseView: () => {
      getCaseViewCalls += 1;
      return Promise.resolve({ case_id: "case-1", phase: "investigation", stage: "investigation" });
    },
  },
}));

vi.mock("../../api/sse", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/sse")>();
  return {
    ...actual,
    SSEClient: class {
      constructor(
        _caseId: string,
        private opts: { onEvent: (e: TranslatedEvent) => void },
      ) {}
      connect() {
        emitted.push(this.opts.onEvent);
      }
      disconnect() {}
    },
  };
});

function event(cursor: number, technical = false): TranslatedEvent {
  return {
    event_type: technical ? "role_invocation_attempt" : "evidence_batch_unpacked",
    message: `event ${cursor}`,
    technical,
    raw_payload: { record_count: 1 },
    line_cursor: cursor,
  };
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  emitted.length = 0;
  getCaseViewCalls = 0;
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useCaseView", () => {
  it("fetches the projection once on mount", async () => {
    renderHook(() => useCaseView("case-1"));
    await waitFor(() => expect(getCaseViewCalls).toBe(1));
  });

  it("coalesces a burst of events into a single refetch", async () => {
    // Ten events inside the debounce window is one request, not ten. A refetch
    // per event would put the projection under load exactly when the engine is
    // busiest.
    const { result } = renderHook(() => useCaseView("case-1"));
    await waitFor(() => expect(getCaseViewCalls).toBe(1));

    const emit = emitted[0];
    for (let i = 1; i <= 10; i += 1) emit(event(i));

    await vi.advanceTimersByTimeAsync(400);
    await waitFor(() => expect(getCaseViewCalls).toBe(2));
    expect(result.current.events).toHaveLength(10);
  });

  it("does not refetch on technical events", async () => {
    // Retries and coercion notices change the Method room, not the projection.
    renderHook(() => useCaseView("case-1"));
    await waitFor(() => expect(getCaseViewCalls).toBe(1));

    const emit = emitted[0];
    emit(event(1, true));
    emit(event(2, true));
    await vi.advanceTimersByTimeAsync(400);

    expect(getCaseViewCalls).toBe(1);
  });

  it("folds events into narration as they arrive", async () => {
    const { result } = renderHook(() => useCaseView("case-1"));
    await waitFor(() => expect(getCaseViewCalls).toBe(1));

    emitted[0](event(1));
    await waitFor(() => expect(result.current.narration.evidenceCount).toBe(1));
    expect(result.current.narration.cursor).toBe(1);
  });

  it("keeps the previous view on screen while refetching", async () => {
    // The reader must never watch their brief disappear and come back.
    const { result } = renderHook(() => useCaseView("case-1"));
    await waitFor(() => expect(result.current.view).not.toBeNull());

    emitted[0](event(1));
    await vi.advanceTimersByTimeAsync(300);

    expect(result.current.view).not.toBeNull();
    expect(result.current.loading).toBe(false);
  });
});

// ── Budgets and degraded states (SPEC-055) ───────────────────────────────────

describe("the event buffer is bounded", () => {
  it("retains a fixed number of events across a very long case", async () => {
    // A 191-minute run with twenty-second progress heartbeats produces
    // thousands of events. The old buffer grew without limit *and* copied the
    // whole array on every append — O(n²) work, O(n) memory, invisible until
    // exactly the case the product is built for.
    const { result } = renderHook(() => useCaseView("case-1"));
    await waitFor(() => expect(result.current.view).not.toBeNull());

    const emit = emitted[emitted.length - 1];
    await act(async () => {
      for (let i = 1; i <= 3000; i += 1) emit(event(i));
    });

    expect(result.current.events.length).toBeLessThanOrEqual(MAX_RETAINED_EVENTS);
    // It keeps the recent end, which is what the transcript and margin show.
    const last = result.current.events[result.current.events.length - 1];
    expect(last.line_cursor).toBe(3000);
  });

  it("keeps the narration correct over the whole stream, not just what is retained", async () => {
    // Nothing a reader sees is lost by bounding the buffer: the reducer folds
    // every event as it arrives, so counters are computed from all 3,000.
    const { result } = renderHook(() => useCaseView("case-1"));
    await waitFor(() => expect(result.current.view).not.toBeNull());

    const emit = emitted[emitted.length - 1];
    await act(async () => {
      for (let i = 1; i <= 600; i += 1) {
        emit({
          event_type: "evidence_batch_unpacked",
          message: "evidence",
          technical: false,
          raw_payload: { record_count: 1 },
          line_cursor: i,
        });
      }
    });

    expect(result.current.events.length).toBeLessThanOrEqual(MAX_RETAINED_EVENTS);
    // 600 events counted, even though fewer than 600 are retained.
    expect(result.current.narration.evidenceCount).toBe(600);
  });
});

describe("a case that never starts", () => {
  it("is not called stalled while events are arriving", async () => {
    vi.useFakeTimers();
    try {
      const { result } = renderHook(() => useCaseView("case-1"));
      await vi.waitFor(() => expect(emitted.length).toBeGreaterThan(0));
      const emit = emitted[emitted.length - 1];

      act(() => {
        emit(event(1));
        vi.advanceTimersByTime(STALL_WINDOW_MS * 2);
      });
      expect(result.current.stalled).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it("is surfaced as stalled when nothing happens within the window", async () => {
    // The gap SPEC-046's non-blocking creation opened: a worker that dies at
    // startup leaves a case that looks like it is about to begin, forever.
    vi.useFakeTimers();
    try {
      const { result } = renderHook(() => useCaseView("case-1"));
      await vi.waitFor(() => expect(emitted.length).toBeGreaterThan(0));

      act(() => {
        vi.advanceTimersByTime(STALL_WINDOW_MS + 1000);
      });
      expect(result.current.stalled).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });
});
