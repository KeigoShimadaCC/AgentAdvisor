import { type ReactNode } from "react";
import { useParams, Link } from "react-router-dom";
import { useCaseView } from "./useCaseView";
import { RoomTabs } from "./RoomTabs";
import { InspectorHost } from "../inspector/InspectorHost";
import { ROOMS, type RoomKey } from "../../copy/terms";
import type { CaseView } from "../../generated/case_view";
import type { TranslatedEvent } from "../../api/sse";

interface RoomShellProps {
  room: RoomKey;
  /** Render the room body from the loaded CaseView + live events. */
  children: (
    view: CaseView,
    events: TranslatedEvent[],
  ) => ReactNode;
}

/**
 * Shared chrome for every room: back link, room tabs, loading/error states,
 * the inspector host (so citation clicks open the slide-over), then the room
 * body. Keeps the room components focused on their projection.
 */
export function RoomShell({ room, children }: RoomShellProps) {
  const { caseId } = useParams<{ caseId: string }>();
  const { view, events, loading, error } = useCaseView(caseId);

  const descriptor = ROOMS[room];

  return (
    <InspectorHost events={events}>
      <div className="room">
        <div className="room-header">
          <Link to={`/cases/${caseId}`} className="back-link">← Back to case</Link>
          <h2 className="room-title">{descriptor.label}</h2>
          <p className="room-blurb">{descriptor.blurb}</p>
        </div>

        {caseId && <RoomTabs caseId={caseId} />}

        <div className="room-body">
          {loading && <p>Loading…</p>}
          {error && <p className="error">{error}</p>}
          {!loading && !error && view && children(view, events)}
          {!loading && !error && !view && <p>No data.</p>}
        </div>
      </div>
    </InspectorHost>
  );
}
