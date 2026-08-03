import { useParams, Link } from "react-router-dom";
import { useCaseView } from "../shared/useCaseView";
import { RecordInspector } from "./RecordInspector";

/**
 * Standalone, route-addressable inspector at
 * `/cases/:caseId/inspector/:artifactId` for deep links and notifications.
 */
export function InspectorPage() {
  const { caseId, artifactId } = useParams<{ caseId: string; artifactId: string }>();
  const { events, loading } = useCaseView(caseId);

  if (!caseId || !artifactId) return <p>No record specified.</p>;

  return (
    <div className="inspector-page">
      <Link to={`/cases/${caseId}`} className="back-link">← Back to case</Link>
      {loading && <p>Loading…</p>}
      <div className="inspector-page-panel">
        <RecordInspector
          caseId={caseId}
          artifactId={artifactId}
          events={events}
          onClose={() => window.history.back()}
        />
      </div>
    </div>
  );
}
