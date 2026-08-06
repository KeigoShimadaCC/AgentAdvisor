import { useParams } from "react-router-dom";
import { useCaseView } from "../shared/useCaseView";
import { RecordInspector } from "./RecordInspector";
import { CaseCrumb } from "../shell/CaseCrumb";
import { Skeleton } from "../shared/Skeleton";

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
      <CaseCrumb caseId={caseId} />
      {loading && <Skeleton shape="sheet" label="Loading the record" />}
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
