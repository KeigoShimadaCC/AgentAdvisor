import { Link, useParams } from "react-router-dom";
import { ROOMS, ROOM_TAB_ORDER } from "../../copy/terms";

/**
 * Room navigation in the rail (SPEC-048).
 *
 * `RoomTabs` was a second horizontal nav bar under the app's own, which is one
 * nav bar more than a screen can have without the user having to work out which
 * one moves them where. The same six destinations live in the rail, and they
 * open the context panel instead of replacing the page.
 */
export function RoomRail({ activeRoom }: { activeRoom?: string }) {
  const { caseId } = useParams<{ caseId: string }>();
  if (!caseId) return null;

  return (
    <nav className="room-rail" aria-label="Rooms">
      <p className="room-rail-label">Look closer</p>
      <ul className="room-rail-list">
        {ROOM_TAB_ORDER.map((key) => (
          <li key={key}>
            <Link
              to={`/cases/${caseId}/rooms/${key}`}
              className={`room-rail-link${activeRoom === key ? " selected" : ""}`}
              aria-current={activeRoom === key ? "page" : undefined}
            >
              {ROOMS[key].label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
