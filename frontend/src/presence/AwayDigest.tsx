import { useMemo, useState } from "react";
import { digestSince, digestLines } from "./digest";
import type { TranslatedEvent } from "../api/sse";

interface AwayDigestProps {
  events: TranslatedEvent[];
  /** The last cursor this reader had seen, from SPEC-047's persisted cursor. */
  sinceCursor: number | null;
}

/**
 * What happened while you were away (SPEC-051).
 *
 * A run reaches 191 minutes and the product tells you to leave the page. Coming
 * back, there was no way to tell a case that had done three hours of work from
 * one that had done nothing — the brief simply looked different, with no account
 * of how it got there.
 *
 * Suppressed entirely when the gap is empty. "Nothing happened while you were
 * away" is a line that trains people to ignore the component.
 */
export function AwayDigest({ events, sinceCursor }: AwayDigestProps) {
  const [dismissed, setDismissed] = useState(false);

  const lines = useMemo(() => {
    if (sinceCursor == null) return [];
    return digestLines(digestSince(events, sinceCursor));
  }, [events, sinceCursor]);

  if (dismissed || lines.length === 0) return null;

  return (
    <section className="away-digest" aria-label="What happened while you were away">
      <div className="away-digest-head">
        <h3>While you were away</h3>
        <button
          type="button"
          className="away-digest-dismiss"
          onClick={() => setDismissed(true)}
        >
          Dismiss
        </button>
      </div>
      <ul className="away-digest-list">
        {lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </section>
  );
}
