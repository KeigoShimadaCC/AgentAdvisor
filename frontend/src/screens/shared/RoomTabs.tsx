import { NavLink } from "react-router-dom";
import { ROOMS, ROOM_TAB_ORDER, type RoomKey } from "../../copy/terms";

interface RoomTabsProps {
  caseId: string;
  /** Rooms that have new content since the last visit (SSE-driven). */
  newContent?: Set<RoomKey>;
}

/**
 * Keyboard-accessible room navigation tabs.
 *
 * Renders one tab per room in the canonical order. Active state is driven
 * by react-router's NavLink so deep links stay in sync. A new-content dot
 * is shown when the room is in the `newContent` set.
 */
export function RoomTabs({ caseId, newContent }: RoomTabsProps) {
  return (
    <nav className="room-tabs" aria-label="Rooms">
      <ul className="room-tab-list">
        {ROOM_TAB_ORDER.map((key) => {
          const room = ROOMS[key];
          const isNew = newContent?.has(key) ?? false;
          return (
            <li key={key} className="room-tab-item">
              <NavLink
                to={`/cases/${caseId}/rooms/${key}`}
                className={({ isActive }) =>
                  `room-tab${isActive ? " room-tab-active" : ""}`
                }
              >
                <span className="room-tab-label">{room.label}</span>
                {isNew && (
                  <span className="room-tab-dot" aria-label="new content" />
                )}
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
