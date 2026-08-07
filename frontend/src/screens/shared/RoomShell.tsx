import { type ReactNode } from "react";
import { useParams } from "react-router-dom";
import { useCaseView } from "./useCaseView";
import { useCaseData } from "./caseContext";
import { Skeleton } from "./Skeleton";
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
 * A room's frame (SPEC-048).
 *
 * Was: a back link, a second nav bar of room tabs, its own inspector host and
 * its own fetch — page chrome for something that is not a page. A room is a
 * part of one case, so it now renders inside the case surface's context panel
 * and the surface owns the chrome.
 *
 * The fallback fetch exists so a room still stands up alone; when the case
 * surface is above it, `caseId` is passed as `undefined` and no second stream
 * is opened.
 */
export function RoomShell({ room, children }: RoomShellProps) {
  const { caseId } = useParams<{ caseId: string }>();
  const shared = useCaseData();
  const own = useCaseView(shared ? undefined : caseId);

  const view = shared ? shared.view : own.view;
  const events = shared ? shared.events : own.events;
  const loading = shared ? false : own.loading;
  const error = shared ? null : own.error;

  const descriptor = ROOMS[room];

  const body = (
    <div className="room">
      <div className="room-header">
        {/* Inside the panel the frame already names the room; repeating it here
            would give the same room two headings. */}
        {!shared && <h3 className="room-title">{descriptor.label}</h3>}
        <p className="room-blurb">{descriptor.blurb}</p>
      </div>

      <div className="room-body">
        {loading && <Skeleton shape="sheet" label={`Loading ${descriptor.label}`} />}
        {error && <p className="error">{error}</p>}
        {!loading && !error && view && children(view, events)}
        {!loading && !error && !view && <p>No data.</p>}
      </div>
    </div>
  );

  // The case surface already hosts the inspector; a standalone room provides
  // its own so citations still open rather than throwing.
  return shared ? body : <InspectorHost events={events}>{body}</InspectorHost>;
}
