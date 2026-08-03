export interface TranslatedEvent {
  event_type: string;
  message: string;
  technical: boolean;
  raw_payload: Record<string, unknown>;
  line_cursor: number;
  ts?: string | null;
  actor?: string | null;
}

export interface SSEClientOptions {
  since?: number;
  onEvent: (event: TranslatedEvent) => void;
  onError?: (error: Error) => void;
  onClose?: () => void;
}

export class SSEClient {
  private controller: AbortController | null = null;
  private cursor: number;

  constructor(
    private caseId: string,
    private opts: SSEClientOptions,
  ) {
    this.cursor = opts.since ?? 0;
  }

  connect(): void {
    this.controller = new AbortController();
    const url = `/api/cases/${encodeURIComponent(this.caseId)}/events?since=${this.cursor}`;

    fetch(url, {
      signal: this.controller.signal,
      headers: { Accept: "text/event-stream" },
    }).then(async (resp) => {
      if (!resp.ok || !resp.body) {
        this.opts.onError?.(new Error(`SSE connect failed: ${resp.status}`));
        return;
      }
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
          if (line.startsWith("data: ")) {
            try {
              const event = JSON.parse(line.slice(6)) as TranslatedEvent;
              this.cursor = event.line_cursor;
              this.opts.onEvent(event);
            } catch {
              // skip unparseable
            }
          }
        }
      }
      this.opts.onClose?.();
    }).catch((err: Error) => {
      if (err.name !== "AbortError") {
        this.opts.onError?.(err);
      }
    });
  }

  disconnect(): void {
    this.controller?.abort();
    this.controller = null;
  }

  get currentCursor(): number {
    return this.cursor;
  }
}
