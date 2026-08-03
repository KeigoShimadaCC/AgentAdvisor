import { useParams, Link } from "react-router-dom";
import { useCaseView } from "../screens/shared/useCaseView";
import { RoomTabs } from "../screens/shared/RoomTabs";
import { stageLabel, NEEDS_YOU } from "../copy/terms";

export function CaseDetail() {
  const { caseId } = useParams<{ caseId: string }>();
  const { view, events, loading, error } = useCaseView(caseId);

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="error">{error}</p>;
  if (!view) return <p>No data.</p>;

  const needsYou = NEEDS_YOU[view.needs_you];

  return (
    <div className="case-detail">
      <h2>{view.case_id}</h2>
      <dl className="case-meta">
        <dt>Phase</dt><dd>{stageLabel(view.stage)}</dd>
        <dt>Stage</dt><dd>{view.stage}</dd>
        <dt>Status</dt><dd>{needsYou.badge || "In progress"}</dd>
        <dt>Terminal</dt><dd>{view.is_terminal ? "yes" : "no"}</dd>
      </dl>

      {caseId && (
        <p>
          <Link
            to={
              view.stage === "done" || view.stage === "awaiting_final_approval"
                ? `/cases/${caseId}/delivery`
                : `/cases/${caseId}/brief`
            }
            className="primary-action"
          >
            {view.stage === "done" || view.stage === "awaiting_final_approval"
              ? "Review delivery"
              : "Open living brief"}
          </Link>
        </p>
      )}

      {caseId && <RoomTabs caseId={caseId} />}

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

      <p className="back-link">
        <Link to="/">← All cases</Link>
      </p>
    </div>
  );
}
