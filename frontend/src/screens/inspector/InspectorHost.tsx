import { type ReactNode, useCallback, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { InspectorContext } from "./inspectorContext";
import { RecordInspector } from "./RecordInspector";
import type { TranslatedEvent } from "../../api/sse";

interface InspectorHostProps {
  /** Live audit events, used to build the audit slice inside the inspector. */
  events: TranslatedEvent[];
  children: ReactNode;
}

/**
 * Provides an inspector context so any descendant can call `useInspector().open(id)`
 * to surface the record slide-over. Renders the slide-over when open.
 */
export function InspectorHost({ events, children }: InspectorHostProps) {
  const { caseId } = useParams<{ caseId: string }>();
  const [openId, setOpenId] = useState<string | null>(null);

  const open = useCallback((id: string) => setOpenId(id), []);
  const close = useCallback(() => setOpenId(null), []);

  const value = useMemo(() => ({ open, close, openId }), [open, close, openId]);

  return (
    <InspectorContext.Provider value={value}>
      {children}
      {openId && caseId && (
        <div className="inspector-overlay" onClick={close}>
          <div className="inspector-panel" onClick={(e) => e.stopPropagation()}>
            <RecordInspector
              caseId={caseId}
              artifactId={openId}
              events={events}
              onClose={close}
            />
          </div>
        </div>
      )}
    </InspectorContext.Provider>
  );
}
