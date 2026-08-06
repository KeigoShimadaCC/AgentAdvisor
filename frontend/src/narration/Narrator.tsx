import { useEffect, useState } from "react";
import type { TranslatedEvent } from "../api/sse";
import { narrationLine, type NarrationState } from "./reducer";

interface NarratorProps {
  narration: NarrationState;
  events: TranslatedEvent[];
  /**
   * Whether to offer the collapsed transcript.
   *
   * False on the Brief, where `MarginNarration` already renders the narration
   * stream with its citations — two copies of the same events on one screen is
   * exactly the noise this component exists to remove.
   */
  showTranscript?: boolean;
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

/**
 * One present-tense line that rewrites in place (SPEC-047).
 *
 * This replaces a scrolling list of `[47] researcher — attempt 1: ok`, which
 * was a debug view wearing a product's clothes: it showed raw cursors and enum
 * statuses, grew without bound, and still left the reader unable to answer the
 * only question they had, which is whether anything is happening.
 *
 * Announcement policy (SPEC-055 generalises it): the line is `aria-live`
 * polite so a screen reader hears transitions, but the elapsed timer is marked
 * `aria-hidden` — it changes every second, and announcing it would make the
 * page unusable. Transitions are announced; heartbeats are not.
 */
export function Narrator({ narration, events, showTranscript = true }: NarratorProps) {
  const [now, setNow] = useState(() => Date.now());
  const [transcriptOpen, setTranscriptOpen] = useState(false);

  const working = narration.activity.kind === "working";

  useEffect(() => {
    if (!working) return;
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [working]);

  const line = narrationLine(narration);
  if (line === null && narration.announcements.length === 0) return null;

  const since =
    narration.activity.kind === "working" ? narration.activity.since : null;
  const elapsedS = since ? Math.max(0, (now - new Date(since).getTime()) / 1000) : 0;

  // The narration stream, not the audit log: see the transcript note below.
  const narratable = events.filter((e) => !e.technical);

  const counters: string[] = [];
  if (narration.evidenceCount > 0) counters.push(`${narration.evidenceCount} evidence`);
  if (narration.assumptionCount > 0) counters.push(`${narration.assumptionCount} assumptions`);
  if (narration.objectionCount > 0) counters.push(`${narration.objectionCount} objections`);

  return (
    <section className="narrator" aria-label="What is happening now">
      {line && (
        <p className="narrator-line" aria-live="polite">
          <span className={`narrator-dot${working ? " pulsing" : ""}`} aria-hidden="true" />
          <span className="narrator-text">{line}</span>
          {working && Number.isFinite(elapsedS) && elapsedS > 0 && (
            // Hidden from assistive tech on purpose: a per-second counter read
            // aloud is noise, and the transition it belongs to was already
            // announced by the line itself.
            <span className="narrator-elapsed" aria-hidden="true">
              {formatElapsed(elapsedS)}
            </span>
          )}
        </p>
      )}

      {counters.length > 0 && (
        <p className="narrator-counters" aria-hidden="true">
          {counters.join(" · ")}
        </p>
      )}

      {narration.announcements.length > 0 && (
        <ul className="narrator-announcements">
          {narration.announcements.slice(-3).map((a) => (
            <li key={a.id} className={`narrator-announcement narrator-announcement-${a.kind}`}>
              {a.text}
            </li>
          ))}
        </ul>
      )}

      {showTranscript && narratable.length > 0 && (
        <details
          className="narrator-transcript"
          open={transcriptOpen}
          onToggle={(e) => setTranscriptOpen((e.target as HTMLDetailsElement).open)}
        >
          <summary>Full transcript ({narratable.length})</summary>
          {/* Technical events are deliberately absent. The lexicon's `technical`
              flag is the product's existing rule for "this describes the
              machinery, not the investigation", and the Method room is where
              the unfiltered log lives. A transcript that leaked retries and
              coercion notices would re-create the debug view this replaced. */}
          <ul className="narrator-transcript-list" tabIndex={0} role="list">
            {narratable.slice(-100).map((e) => (
              <li key={e.line_cursor} className="narrator-entry">
                {e.message}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
