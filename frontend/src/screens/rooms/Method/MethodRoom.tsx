import { useMemo, useState } from "react";
import { RoomShell } from "../../shared/RoomShell";
import type { CaseView } from "../../../generated/case_view";
import type { TranslatedEvent } from "../../../api/sse";
import { api } from "../../../api/client";
import { eventTypeLabel, roleLabel, stageLabel, ROOMS } from "../../../copy/terms";

export function MethodRoom() {
  return (
    <RoomShell room="method">
      {(view, events) => <MethodBody view={view} events={events} />}
    </RoomShell>
  );
}

type EventFilter = "all" | "user" | "technical";

const EVENT_FILTER_LABELS: Record<EventFilter, string> = {
  all: "All events",
  user: "Progress only",
  technical: "Machinery only",
};

function MethodBody({ view, events }: { view: CaseView; events: TranslatedEvent[] }) {
  const [eventFilter, setEventFilter] = useState<EventFilter>("all");
  const [rawPath, setRawPath] = useState<string | null>(null);
  const [rawContent, setRawContent] = useState<string | null>(null);
  const [rawLoading, setRawLoading] = useState(false);

  const effort = view.effort;
  const byRole = effort?.by_role ?? {};
  const eventCounts = effort?.event_counts ?? {};

  const filteredEvents = useMemo(() => {
    if (eventFilter === "all") return events;
    if (eventFilter === "user") return events.filter((e) => !e.technical);
    return events.filter((e) => e.technical);
  }, [events, eventFilter]);

  // Phase timeline from gates + audit events (stage_completed).
  const timeline = useMemo(() => {
    const seen = new Set<string>();
    const items: { stage: string; label: string; source: string }[] = [];
    for (const g of view.integrity?.gates ?? []) {
      if (!seen.has(g.stage)) {
        seen.add(g.stage);
        items.push({ stage: g.stage, label: `${stageLabel(g.stage)} — gate ${g.outcome}`, source: "gate" });
      }
    }
    for (const e of events) {
      if (e.event_type === "stage_completed") {
        const stage = String(e.raw_payload["stage"] ?? "");
        if (stage && !seen.has(stage)) {
          seen.add(stage);
          items.push({ stage, label: stageLabel(stage), source: "event" });
        }
      }
    }
    return items;
  }, [view, events]);

  function loadRaw(path: string) {
    setRawPath(path);
    setRawLoading(true);
    setRawContent(null);
    const caseId = view.case_id;
    api
      .getFile(caseId, path)
      .then(setRawContent)
      .catch(() => setRawContent("File not available."))
      .finally(() => setRawLoading(false));
  }

  return (
    <div className="method-room">
      {/* Phase timeline */}
      {timeline.length > 0 && (
        <section className="method-timeline" aria-label="Phase timeline">
          <h3>Phases</h3>
          <ol className="timeline-list">
            {timeline.map((t, i) => (
              <li key={`${t.stage}-${i}`} className="timeline-item">
                <span className="timeline-dot" aria-hidden="true" />
                <span className="timeline-label">{t.label}</span>
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* Gate reports */}
      {(view.integrity?.gates ?? []).length > 0 && (
        <section className="method-gates" aria-label="Gate reports">
          <h3>Gates</h3>
          <ul className="gate-list">
            {(view.integrity?.gates ?? []).map((g, i) => (
              <li key={i} className="gate-row">
                <span className="gate-stage">{stageLabel(g.stage)}</span>
                <span className={`gate-outcome gate-outcome-${g.outcome}`}>{g.outcome}</span>
                <ul className="gate-findings">
                  {(g.findings ?? []).map((f, j) => (
                    <li key={j} className="gate-finding">
                      <span className="gate-check-id">{String(f["check_id"] ?? "—")}</span>
                      {": "}
                      {String(f["message"] ?? "—")}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Invocation table */}
      <section className="method-invocations" aria-label="Agent invocations">
        <h3>Agent invocations</h3>
        {Object.keys(byRole).length === 0 ? (
          <p className="screen-help">No agent invocations recorded yet.</p>
        ) : (
          <table className="invocation-table">
            <thead>
              <tr>
                <th scope="col">Role</th>
                <th scope="col">Attempts</th>
                <th scope="col">Input tokens</th>
                <th scope="col">Output tokens</th>
                <th scope="col">Total tokens</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(byRole).map(([role, counts]) => (
                <tr key={role}>
                  <th scope="row">{roleLabel(role)}</th>
                  <td>{counts["attempts"] ?? 0}</td>
                  <td>{counts["input_tokens"] ?? 0}</td>
                  <td>{counts["output_tokens"] ?? 0}</td>
                  <td>{counts["total_tokens"] ?? 0}</td>
                </tr>
              ))}
            </tbody>
            {effort && (
              <tfoot>
                <tr>
                  <th scope="row">Total</th>
                  <td>{effort.invocation_attempts}</td>
                  <td>{effort.input_tokens}</td>
                  <td>{effort.output_tokens}</td>
                  <td>{effort.total_tokens}</td>
                </tr>
              </tfoot>
            )}
          </table>
        )}
      </section>

      {/* Effort meters vs caps */}
      {effort && (
        <section className="method-effort" aria-label="Effort and limits">
          <h3>Effort and limits</h3>
          <ul className="effort-meters">
            <li>Invocations: {effort.invocation_attempts} / {effort.budget_caps?.["max_agent_invocations"] ?? "—"}</li>
            <li>Retries: {effort.retries}</li>
            <li>Wall clock: {effort.wall_clock_s != null ? `${Math.round(effort.wall_clock_s)}s` : "—"}</li>
          </ul>
        </section>
      )}

      {/* Event counts */}
      {Object.keys(eventCounts).length > 0 && (
        <section className="method-event-counts" aria-label="Event counts">
          <h3>Event counts</h3>
          <ul className="event-count-list">
            {Object.entries(eventCounts).map(([type, count]) => (
              <li key={type}>
                {eventTypeLabel(type)}: {count}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Audit event log */}
      <section className="method-event-log" aria-label="Audit event log">
        <h3>Audit log</h3>
        <div className="method-event-filters" role="group" aria-label="Filter audit events">
          {(Object.keys(EVENT_FILTER_LABELS) as EventFilter[]).map((key) => (
            <button
              key={key}
              type="button"
              className={`filter-chip${eventFilter === key ? " filter-chip-active" : ""}`}
              aria-pressed={eventFilter === key}
              onClick={() => setEventFilter(key)}
            >
              {EVENT_FILTER_LABELS[key]}
            </button>
          ))}
        </div>
        {filteredEvents.length === 0 ? (
          <p className="screen-help">No events yet.</p>
        ) : (
          <ul className="audit-log-list">
            {filteredEvents.map((e, i) => (
              <li key={i} className={e.technical ? "audit-log-item audit-log-technical" : "audit-log-item audit-log-user"}>
                <small className="audit-log-cursor">[{e.line_cursor}]</small>
                <span className="audit-log-type">{eventTypeLabel(e.event_type)}</span>
                <span className="audit-log-message">{e.message}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Raw file browser */}
      <section className="method-raw" aria-label="Raw artifact browser">
        <h3>Raw files</h3>
        <p className="screen-help">
          Enter a file path (e.g. <code>audit.jsonl</code> or <code>evidence_critique.yaml</code>)
          to view the raw artifact.
        </p>
        <form
          className="raw-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (rawPath) loadRaw(rawPath);
          }}
        >
          <input
            className="raw-path-input"
            type="text"
            placeholder="audit.jsonl"
            value={rawPath ?? ""}
            onChange={(e) => setRawPath(e.target.value)}
            aria-label="File path"
          />
          <button type="submit" className="secondary-action">View</button>
        </form>
        {rawLoading && <p>Loading…</p>}
        {rawContent != null && (
          <pre className="method-raw-view">{rawContent}</pre>
        )}
      </section>
    </div>
  );
}
