import { useEffect, useRef, type ReactNode } from "react";

interface AppShellProps {
  rail?: ReactNode;
  children: ReactNode;
  panel?: ReactNode;
  panelTitle?: string;
  onPanelClose?: () => void;
}

/**
 * Three-region shell (SPEC-048): rail, content, context panel.
 *
 * The panel is what replaces navigating to a room. Following a citation used to
 * be a full page change, which cost the reader their place in the argument —
 * the one thing a reader cannot spare. The panel slides in beside the content,
 * the content column keeps its scroll position, and closing it returns focus to
 * whatever opened it.
 */
export function AppShell({ rail, children, panel, panelTitle, onPanelClose }: AppShellProps) {
  const opener = useRef<HTMLElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (panel) {
      opener.current = document.activeElement as HTMLElement | null;
      panelRef.current?.focus();
    } else if (opener.current) {
      // Focus must come back where it left, or a keyboard user is dropped at
      // the top of the document every time they check a source.
      opener.current.focus();
      opener.current = null;
    }
  }, [panel]);

  useEffect(() => {
    if (!panel || !onPanelClose) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onPanelClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [panel, onPanelClose]);

  return (
    <div className={`app-shell${panel ? " app-shell-panel-open" : ""}`}>
      {rail && <aside className="app-shell-rail">{rail}</aside>}
      <div className="app-shell-content">{children}</div>
      {panel && (
        <aside
          className="app-shell-panel"
          ref={panelRef}
          tabIndex={-1}
          role="complementary"
          aria-label={panelTitle ?? "Details"}
        >
          <div className="app-shell-panel-head">
            <h3>{panelTitle ?? "Details"}</h3>
            {onPanelClose && (
              <button type="button" className="app-shell-panel-close" onClick={onPanelClose}>
                Close
              </button>
            )}
          </div>
          <div className="app-shell-panel-body">{panel}</div>
        </aside>
      )}
    </div>
  );
}
