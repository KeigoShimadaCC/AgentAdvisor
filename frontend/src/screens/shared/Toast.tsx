import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export type ToastTone = "info" | "success" | "error";

interface Toast {
  id: number;
  tone: ToastTone;
  text: string;
}

interface ToastApi {
  show: (text: string, tone?: ToastTone) => void;
}

const ToastContext = createContext<ToastApi>({ show: () => {} });

export function useToast(): ToastApi {
  return useContext(ToastContext);
}

/**
 * Toasts for control actions (SPEC-048).
 *
 * Approve, pause, resume and send-back previously either swapped the screen
 * silently or rendered a red paragraph, so a user could not tell a completed
 * action from an ignored click. A control should say exactly what happened.
 *
 * Announcement policy: the region is `aria-live` polite and `role="status"`,
 * because a toast *is* a transition — unlike the narrator's elapsed timer,
 * which is a heartbeat and stays silent.
 */
export function ToastHost({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const show = useCallback((text: string, tone: ToastTone = "info") => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, tone, text }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 5000);
  }, []);

  const api = useMemo(() => ({ show }), [show]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-host" role="status" aria-live="polite">
        {toasts.map((t) => (
          <p key={t.id} className={`toast toast-${t.tone}`}>
            {t.text}
          </p>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
