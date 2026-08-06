export interface TranslatedEvent {
  event_type: string;
  message: string;
  technical: boolean;
  raw_payload: Record<string, unknown>;
  line_cursor: number;
  ts?: string | null;
  actor?: string | null;
}

/**
 * How the stream is doing, surfaced so the chrome can say so (SPEC-047).
 *
 * `stale` is the dangerous state and therefore a distinct one: the screen still
 * shows a plausible brief and only an explicit marker distinguishes it from a
 * live one. SPEC-055 renders these; this file owns producing them.
 */
export type ConnectionState = "connecting" | "connected" | "reconnecting" | "stale";

export interface SSEClientOptions {
  since?: number;
  onEvent: (event: TranslatedEvent) => void;
  onError?: (error: Error) => void;
  onClose?: () => void;
  onConnectionChange?: (state: ConnectionState) => void;
  /** Test seam: skip real waiting between retries. */
  now?: () => number;
}

/** Backoff bounds. Jittered so many tabs do not retry in lockstep. */
const BACKOFF_MIN_MS = 1_000;
const BACKOFF_MAX_MS = 30_000;
/** Give up and declare `stale` after this many consecutive failures. */
const MAX_ATTEMPTS_BEFORE_STALE = 6;

/** Where the last-seen cursor lives, so a return visit resumes rather than replays. */
export function cursorStorageKey(caseId: string): string {
  return `agentadvisor:cursor:${caseId}`;
}

/**
 * Whether this reader has ever been on this case (SPEC-052).
 *
 * `readStoredCursor` returns 0 both for "no cursor stored" and for "stored at
 * the very beginning", and those are different facts: a first-time reader was
 * never away, so the away digest must not greet them with three hours of news
 * about a case they have never opened.
 */
export function hasStoredCursor(caseId: string): boolean {
  try {
    return window.localStorage.getItem(cursorStorageKey(caseId)) !== null;
  } catch {
    return false;
  }
}

export function readStoredCursor(caseId: string): number {
  try {
    const raw = window.localStorage.getItem(cursorStorageKey(caseId));
    const parsed = raw === null ? 0 : Number.parseInt(raw, 10);
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
  } catch {
    // Storage can be unavailable (private mode, quota, disabled). A lost cursor
    // is a downgrade to replaying from 0, never a failure. SPEC-055 generalises
    // this into a storage wrapper.
    return 0;
  }
}

function writeStoredCursor(caseId: string, cursor: number): void {
  try {
    window.localStorage.setItem(cursorStorageKey(caseId), String(cursor));
  } catch {
    /* see readStoredCursor */
  }
}

export class SSEClient {
  private controller: AbortController | null = null;
  private cursor: number;
  private attempts = 0;
  private stopped = false;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private connection: ConnectionState = "connecting";

  constructor(
    private caseId: string,
    private opts: SSEClientOptions,
  ) {
    this.cursor = opts.since ?? 0;
  }

  connect(): void {
    this.stopped = false;
    this.open();
  }

  private setConnection(state: ConnectionState): void {
    if (this.connection === state) return;
    this.connection = state;
    this.opts.onConnectionChange?.(state);
  }

  /** Exponential with full jitter, capped. */
  private backoffMs(): number {
    const ceiling = Math.min(BACKOFF_MAX_MS, BACKOFF_MIN_MS * 2 ** (this.attempts - 1));
    return Math.random() * ceiling;
  }

  private scheduleRetry(): void {
    if (this.stopped) return;
    this.attempts += 1;
    // The stream is not merely slow at this point — it has failed repeatedly,
    // and the projection on screen may be arbitrarily out of date. Saying so is
    // the whole point of a separate state.
    this.setConnection(this.attempts >= MAX_ATTEMPTS_BEFORE_STALE ? "stale" : "reconnecting");
    this.retryTimer = setTimeout(() => this.open(), this.backoffMs());
  }

  private open(): void {
    if (this.stopped) return;
    this.controller = new AbortController();
    // Resuming from the cursor is what makes a reconnect lossless: the server
    // replays everything past it, so a dropped connection costs latency and
    // never events.
    const url = `/api/cases/${encodeURIComponent(this.caseId)}/events?since=${this.cursor}`;

    fetch(url, { signal: this.controller.signal, headers: { Accept: "text/event-stream" } })
      .then(async (resp) => {
        if (!resp.ok || !resp.body) {
          this.opts.onError?.(new Error(`SSE connect failed: ${resp.status}`));
          this.scheduleRetry();
          return;
        }
        this.attempts = 0;
        this.setConnection("connected");

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const frames = buffer.split("\n\n");
          buffer = frames.pop() ?? "";

          for (const frame of frames) {
            const line = frame.trim();
            if (!line) continue;
            if (line.startsWith(":")) continue; // heartbeat comment
            if (!line.startsWith("data: ")) continue;
            try {
              const event = JSON.parse(line.slice(6)) as TranslatedEvent;
              // Guard against a replayed frame after a reconnect: the server
              // resumes from `since`, but a duplicate must never be folded
              // twice into a counter.
              if (event.line_cursor <= this.cursor) continue;
              this.cursor = event.line_cursor;
              writeStoredCursor(this.caseId, this.cursor);
              this.opts.onEvent(event);
            } catch {
              // skip unparseable
            }
          }
        }
        this.opts.onClose?.();
        // A clean end-of-stream on a live case means the server closed it; try
        // again rather than going silent.
        this.scheduleRetry();
      })
      .catch((err: Error) => {
        if (err.name === "AbortError") return;
        this.opts.onError?.(err);
        this.scheduleRetry();
      });
  }

  disconnect(): void {
    this.stopped = true;
    if (this.retryTimer !== null) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    this.controller?.abort();
    this.controller = null;
  }

  /** Force an immediate reconnect, for a user-facing "retry now". */
  retryNow(): void {
    if (this.retryTimer !== null) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    this.controller?.abort();
    this.attempts = 0;
    this.setConnection("connecting");
    this.open();
  }

  get currentCursor(): number {
    return this.cursor;
  }

  get connectionState(): ConnectionState {
    return this.connection;
  }
}
