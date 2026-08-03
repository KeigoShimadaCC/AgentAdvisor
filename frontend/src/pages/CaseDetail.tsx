import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, type ErrorResponse } from "../api/client";
import { SSEClient, type TranslatedEvent } from "../api/sse";
import type { CaseView } from "../generated/case_view";

export function CaseDetail() {
  const { caseId } = useParams<{ caseId: string }>();
  const [view, setView] = useState<CaseView | null>(null);
  const [events, setEvents] = useState<TranslatedEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!caseId) return;
    setLoading(true);
    api.getCaseView(caseId)
      .then(setView)
      .catch((e: ErrorResponse) => setError(e.detail ?? e.error))
      .finally(() => setLoading(false));

    const sse = new SSEClient(caseId, {
      onEvent: (event) => setEvents((prev) => [...prev, event]),
    });
    sse.connect();
    return () => sse.disconnect();
  }, [caseId]);

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="error">{error}</p>;
  if (!view) return <p>No data.</p>;

  return (
    <div className="case-detail">
      <h2>{view.case_id}</h2>
      <dl className="case-meta">
        <dt>Phase</dt><dd>{view.phase}</dd>
        <dt>Stage</dt><dd>{view.stage}</dd>
        <dt>Needs you</dt><dd>{view.needs_you}</dd>
        <dt>Terminal</dt><dd>{view.is_terminal ? "yes" : "no"}</dd>
      </dl>

      <section className="brief-sections">
        <h3>Brief</h3>
        {view.brief_sections?.map((section) => (
          <div key={section.key} className="brief-section">
            <h4>{section.key} <span className="status-badge">{section.status}</span></h4>
            {section.blocks?.map((block, i) => (
              <p key={i} className="brief-block">
                <small className="provenance">{block.provenance}</small>
                {block.text}
              </p>
            ))}
          </div>
        ))}
      </section>

      <section className="event-log">
        <h3>Live events</h3>
        <ul>
          {events.slice(-20).map((e, i) => (
            <li key={i} className={e.technical ? "event-technical" : "event-user"}>
              <small>[{e.line_cursor}]</small> {e.message}
            </li>
          ))}
        </ul>
      </section>

      <section className="raw-view">
        <h3>Raw CaseView (inspector)</h3>
        <pre>{JSON.stringify(view, null, 2)}</pre>
      </section>
    </div>
  );
}
