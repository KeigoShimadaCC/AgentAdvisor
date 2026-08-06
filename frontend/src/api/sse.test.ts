import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SSEClient, readStoredCursor, cursorStorageKey, type ConnectionState } from "./sse";

/**
 * The resilient stream (SPEC-047).
 *
 * Before this, one dropped connection ended the stream permanently: the client
 * aborted and never retried, so a laptop sleep left a live case rendering a
 * frozen brief with no indication it had stopped listening. The cursor needed
 * to fix it already existed — `since=` has been in the API since SPEC-033 — it
 * was simply never used on reconnect.
 */

/** Build a streaming Response whose body emits the given SSE frames. */
function sseResponse(frames: string[], { ok = true, status = 200 } = {}): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder();
      for (const frame of frames) controller.enqueue(encoder.encode(frame));
      controller.close();
    },
  });
  return { ok, status, body } as unknown as Response;
}

function frame(cursor: number, eventType = "stage_completed", technical = false): string {
  return `data: ${JSON.stringify({
    event_type: eventType,
    message: `event ${cursor}`,
    technical,
    raw_payload: {},
    line_cursor: cursor,
  })}\n\n`;
}

const originalFetch = globalThis.fetch;

beforeEach(() => {
  vi.useFakeTimers();
  window.localStorage.clear();
});

afterEach(() => {
  vi.useRealTimers();
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

describe("SSEClient", () => {
  it("delivers events and advances the cursor", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(sseResponse([frame(1), frame(2)]));
    const received: number[] = [];
    const client = new SSEClient("case-1", { onEvent: (e) => received.push(e.line_cursor) });

    client.connect();
    await vi.waitFor(() => expect(received).toEqual([1, 2]));
    expect(client.currentCursor).toBe(2);
    client.disconnect();
  });

  it("resumes from the stored cursor rather than replaying from zero", async () => {
    const fetchMock = vi.fn().mockResolvedValue(sseResponse([frame(8)]));
    globalThis.fetch = fetchMock;
    const client = new SSEClient("case-1", { since: 7, onEvent: () => {} });

    client.connect();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(String(fetchMock.mock.calls[0][0])).toContain("since=7");
    client.disconnect();
  });

  it("never delivers the same cursor twice across a reconnect", async () => {
    // The server replays everything past `since`, and a boundary frame can
    // arrive again. Folding it twice would double a counter, which is exactly
    // the kind of bug that is invisible until a long case.
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce(sseResponse([frame(1), frame(2)]))
      .mockResolvedValue(sseResponse([frame(2), frame(3)]));

    const received: number[] = [];
    const client = new SSEClient("case-1", { onEvent: (e) => received.push(e.line_cursor) });

    client.connect();
    await vi.waitFor(() => expect(received).toEqual([1, 2]));
    await vi.advanceTimersByTimeAsync(35_000); // let the retry fire
    await vi.waitFor(() => expect(received).toEqual([1, 2, 3]));
    client.disconnect();
  });

  it("retries after a failed connect instead of going silent", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(sseResponse([], { ok: false, status: 503 }))
      .mockResolvedValue(sseResponse([frame(1)]));
    globalThis.fetch = fetchMock;

    const received: number[] = [];
    const client = new SSEClient("case-1", { onEvent: (e) => received.push(e.line_cursor) });

    client.connect();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await vi.advanceTimersByTimeAsync(35_000);
    await vi.waitFor(() => expect(received).toEqual([1]));
    client.disconnect();
  });

  it("reports reconnecting, then stale once retries keep failing", async () => {
    // `stale` is the dangerous state and therefore a distinct one: the screen
    // still shows a plausible brief, and only this marker distinguishes it from
    // a live one.
    globalThis.fetch = vi.fn().mockResolvedValue(sseResponse([], { ok: false, status: 500 }));
    const states: ConnectionState[] = [];
    const client = new SSEClient("case-1", {
      onEvent: () => {},
      onConnectionChange: (s) => states.push(s),
    });

    client.connect();
    for (let i = 0; i < 8; i += 1) await vi.advanceTimersByTimeAsync(35_000);

    expect(states).toContain("reconnecting");
    expect(states).toContain("stale");
    client.disconnect();
  });

  it("stops retrying once disconnected", async () => {
    const fetchMock = vi.fn().mockResolvedValue(sseResponse([], { ok: false, status: 500 }));
    globalThis.fetch = fetchMock;
    const client = new SSEClient("case-1", { onEvent: () => {} });

    client.connect();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    client.disconnect();
    await vi.advanceTimersByTimeAsync(120_000);

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("persists the cursor so a return visit resumes where it left off", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(sseResponse([frame(1), frame(2), frame(3)]));
    const client = new SSEClient("case-42", { onEvent: () => {} });

    client.connect();
    await vi.waitFor(() => expect(client.currentCursor).toBe(3));
    expect(window.localStorage.getItem(cursorStorageKey("case-42"))).toBe("3");
    expect(readStoredCursor("case-42")).toBe(3);
    client.disconnect();
  });

  it("treats unavailable storage as a downgrade, not a failure", async () => {
    // Private mode, quota, disabled storage. Losing the cursor costs a replay
    // from zero; it must never throw into a render path.
    const spy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("storage disabled");
    });
    expect(readStoredCursor("case-1")).toBe(0);
    spy.mockRestore();
  });
});
