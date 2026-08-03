import { useState } from "react";
import { CitationLink } from "../inspector/CitationLink";
import type { TranslatedEvent } from "../../api/sse";

interface MarginNarrationProps {
  events: TranslatedEvent[];
}

/** Recursively extract quoted artifact id strings from a raw payload. */
function findCitedArtifactIds(raw: Record<string, unknown>): string[] {
  const ids = new Set<string>();
  const json = JSON.stringify(raw);
  const matches = json.match(/"[A-Z]{1,2}-\d+"/g);
  if (matches) {
    for (const m of matches) {
      ids.add(m.replace(/"/g, ""));
    }
  }
  return [...ids];
}

function formatTs(ts: string | null | undefined): string {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts.includes("T") ? ts.slice(11, 19) : ts;
  return d.toLocaleTimeString();
}

/**
 * Non-technical progress narration from the SSE stream.
 * Retries and coercion events are filtered out upstream by the technical flag.
 * Each card is expandable to the artifact ids it cites.
 */
export function MarginNarration({ events }: MarginNarrationProps) {
  const visible = events.filter((e) => !e.technical);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  if (visible.length === 0) return null;

  function toggle(i: number) {
    setExpanded((prev) => ({ ...prev, [i]: !prev[i] }));
  }

  return (
    <section className="margin-narration" aria-label="Progress narration">
      <h3>What happened</h3>
      <ul className="margin-narration-list">
        {visible.map((e, i) => {
          const cited = findCitedArtifactIds(e.raw_payload);
          const isOpen = expanded[i] ?? false;
          return (
            <li key={`${e.line_cursor}-${i}`} className="margin-narration-card">
              <button
                type="button"
                className="margin-narration-header"
                onClick={() => toggle(i)}
                aria-expanded={isOpen}
              >
                <span className="margin-narration-ts">{formatTs(e.ts)}</span>
                <span className="margin-narration-message">{e.message}</span>
              </button>
              {isOpen && cited.length > 0 && (
                <div className="margin-narration-citations">
                  <span className="margin-narration-citations-label">Cited:</span>
                  {cited.map((id) => (
                    <CitationLink key={id} id={id} />
                  ))}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
