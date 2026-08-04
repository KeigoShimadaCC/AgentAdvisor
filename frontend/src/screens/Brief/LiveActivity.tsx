import { useEffect, useMemo, useState } from "react";
import type { TranslatedEvent } from "../../api/sse";

interface LiveActivityProps {
  events: TranslatedEvent[];
}

/** A human label for the raw attempt status. */
function statusLabel(status: string | undefined): string | null {
  if (!status) return null;
  switch (status) {
    case "ok":
      return "completed";
    case "validation_failure":
      return "validation failed — retrying";
    case "backend_failure":
      return "backend error — retrying";
    case "isolation_failure":
      return "workspace issue — retrying";
    default:
      return status;
  }
}

/** Role name → display label. */
const ROLE_LABELS: Record<string, string> = {
  intake: "Intake",
  director_framing: "Framing",
  structurer: "Structuring",
  director: "Director",
  planner: "Planning",
  researcher: "Research",
  analyst: "Analysis",
  assumption_analyst: "Assumptions",
  premortem: "Pre-mortem",
  challenger: "Challenge",
  synthesizer: "Synthesis",
  reviewer: "Review",
  auditor: "Audit",
};

function roleLabel(actor: string | null | undefined): string {
  if (!actor) return "Agent";
  return ROLE_LABELS[actor] ?? actor;
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

/**
 * A persistent live-activity card that shows what the system is doing right now.
 *
 * Derives its state from the SSE event stream: the most recent
 * ``role_invocation_attempt`` event tells us which agent ran, which attempt,
 * and the outcome. If the latest attempt was not ``ok``, an agent is likely
 * still running (retrying) — we show a pulsing indicator with elapsed time.
 *
 * When the case is terminal (failed/done), the card settles to a final state.
 */
export function LiveActivity({ events }: LiveActivityProps) {
  const [now, setNow] = useState(() => Date.now());

  // Tick every second so the elapsed timer updates.
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  // Find the most recent role_invocation_attempt event.
  const latestAttempt = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i--) {
      const e = events[i];
      if (e.event_type === "role_invocation_attempt") {
        return e;
      }
    }
    return null;
  }, [events]);

  // Find the most recent stage_completed or case_finalized event to know if
  // the pipeline has moved past the current agent.
  const latestStageCompleted = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i--) {
      const e = events[i];
      if (e.event_type === "stage_completed" || e.event_type === "case_finalized") {
        return e;
      }
    }
    return null;
  }, [events]);

  // Determine if the latest attempt is after the latest stage completion
  // (meaning the agent is currently running or just finished).
  const attemptActive = useMemo(() => {
    if (!latestAttempt) return false;
    if (!latestStageCompleted) return true;
    return latestAttempt.line_cursor > latestStageCompleted.line_cursor;
  }, [latestAttempt, latestStageCompleted]);

  // Elapsed time from the attempt event's timestamp.
  // Computed unconditionally (before the early return) to satisfy the
  // Rules of Hooks — React requires every hook to run on every render.
  const elapsedS = useMemo(() => {
    if (!latestAttempt?.ts) return 0;
    const start = new Date(latestAttempt.ts).getTime();
    if (Number.isNaN(start)) return 0;
    return Math.max(0, (now - start) / 1000);
  }, [latestAttempt?.ts, now]);

  if (!latestAttempt) return null;

  const status = statusLabel(latestAttempt.raw_payload.status as string | undefined);
  const attempt = latestAttempt.raw_payload.attempt as number | undefined;
  const isRunning = attemptActive && status !== "completed";
  const isDone = attemptActive && status === "completed";

  return (
    <section className="live-activity" aria-label="Live agent activity">
      <div className={`live-activity-card ${isRunning ? "running" : isDone ? "done" : "idle"}`}>
        <span className={`live-activity-dot ${isRunning ? "pulsing" : ""}`} aria-hidden="true" />
        <div className="live-activity-content">
          <span className="live-activity-role">
            {roleLabel(latestAttempt.actor)}
          </span>
          {attempt != null && (
            <span className="live-activity-attempt">attempt {attempt}</span>
          )}
          {status && (
            <span className={`live-activity-status status-${isRunning ? "running" : isDone ? "ok" : "idle"}`}>
              {isRunning ? "running…" : status}
            </span>
          )}
          {isRunning && elapsedS > 0 && (
            <span className="live-activity-elapsed">{formatElapsed(elapsedS)}</span>
          )}
        </div>
      </div>
    </section>
  );
}
