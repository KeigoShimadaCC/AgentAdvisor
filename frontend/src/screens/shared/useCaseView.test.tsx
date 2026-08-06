import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useCaseView } from "./useCaseView";
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
