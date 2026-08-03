import {
  NEEDS_YOU,
  METHOD_STRIP_COPY,
  PHASE_ORDER,
  PHASE_LABELS,
  PHASE_TIME_RANGES,
} from "../../copy/terms";
import type { CaseView } from "../../generated/case_view";

interface MethodStripProps {
  view: CaseView;
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s.toString().padStart(2, "0")}s`;
}

/**
 * Phase timeline with states, elapsed time, coarse expected ranges, and the
 * leave-safely explainer.
 */
export function MethodStrip({ view }: MethodStripProps) {
  const currentIndex = PHASE_ORDER.indexOf(view.phase);
  const elapsed = view.effort?.wall_clock_s ?? null;
  const needsYou = NEEDS_YOU[view.needs_you];

  return (
    <section className="method-strip" aria-label="Method progress">
      <ol className="method-phase-list">
        {PHASE_ORDER.map((phase, i) => {
          const state =
            currentIndex === -1
              ? "pending"
              : i < currentIndex
                ? "completed"
                : i === currentIndex
                  ? "active"
                  : "pending";
          return (
            <li
              key={phase}
              className={`method-phase method-phase-${state}`}
              aria-current={state === "active" ? "step" : undefined}
            >
              <span className="method-phase-name">{PHASE_LABELS[phase]}</span>
              <span className="method-phase-range">{PHASE_TIME_RANGES[phase]}</span>
            </li>
          );
        })}
      </ol>
      <div className="method-strip-meta">
        {elapsed != null && (
          <span className="method-elapsed">Elapsed: {formatElapsed(elapsed)}</span>
        )}
        <span className="method-needs-you">
          {view.needs_you === "none"
            ? METHOD_STRIP_COPY.nothingNeedsYou
            : `${needsYou.badge} — ${needsYou.action}`}
        </span>
      </div>
      <p className="method-leave-safely">{METHOD_STRIP_COPY.leaveSafely}</p>
    </section>
  );
}
