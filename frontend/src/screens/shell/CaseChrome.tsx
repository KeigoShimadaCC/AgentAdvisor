import { Link } from "react-router-dom";
import { ALTITUDES, useAltitude, type Altitude } from "./altitude";
import { NEEDS_YOU } from "../../copy/terms";
import type { ConnectionState } from "../../api/sse";
import type { CaseView } from "../../generated/case_view";
import { liveRegionProps } from "../../lib/announce";

interface CaseChromeProps {
  view: CaseView;
  connection?: ConnectionState;
  altitude: Altitude;
  onAltitudeChange: (a: Altitude) => void;
}

function formatElapsed(seconds: number | null | undefined): string | null {
  if (seconds == null) return null;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

/** Within a fifth of the cap: close enough that the run may stop for it. */
function nearCap(used: number, cap: number): boolean {
  return cap > 0 && used >= cap * 0.8;
}

const CONNECTION_COPY: Record<ConnectionState, string | null> = {
  connecting: null,
  connected: null,
  reconnecting: "Reconnecting…",
  // The dangerous one: the page still shows a plausible brief, and only this
  // says it may no longer be current.
  stale: "Not updating — this may be out of date",
};

/**
 * Persistent per-case chrome (SPEC-048).
 *
 * What it replaces: a page whose heading was `view.case_id`, so users read
 * `case-014-should-i-take-the-ser` where their decision belongs; ten `← back`
 * links doing the work chrome should do; and a second tab bar for rooms. The
 * frame now carries the case's identity, where it is, what it has spent, and
 * how much of it you want to read — and never goes away, so navigation stops
 * being a page-swap.
 */
export function CaseChrome({ view, connection, altitude, onAltitudeChange }: CaseChromeProps) {
  const needs = NEEDS_YOU[view.needs_you];
  const elapsed = formatElapsed(view.effort?.wall_clock_s);
  const invocations = view.effort?.invocation_attempts ?? 0;
  const tokens = view.effort?.total_tokens ?? 0;
  // SPEC-051: a count without its cap says nothing about whether a run is near
  // its limit. 31 invocations is unremarkable at a cap of 200 and alarming at
  // a cap of 35, and the user cannot tell which without the denominator.
  const invocationCap = view.effort?.budget_caps?.max_agent_invocations ?? 0;
  const connectionNote = connection ? CONNECTION_COPY[connection] : null;

  return (
    <header className="case-chrome">
      <div className="case-chrome-identity">
        <h2 className="case-chrome-question">
          {view.decision_question || "Framing this decision…"}
        </h2>
        <p className="case-chrome-meta">
          <Link to="/" className="case-chrome-back">
            All cases
          </Link>
          {needs.badge && (
            <span className={`case-chrome-needs pill-${view.needs_you}`}>{needs.badge}</span>
          )}
          {connectionNote && (
            <span
              className={`case-chrome-connection connection-${connection}`}
              {...liveRegionProps("chrome.connection")}
            >
              {connectionNote}
            </span>
          )}
        </p>
      </div>

      <div className="case-chrome-controls">
        {/* Spend, in the frame rather than buried in the Method room. A run can
            cost 1.5M tokens; that belongs where the user can see it. */}
        {/* A heartbeat: spend rises continuously and announcing it would be
            noise. Labelled for lookup, never announced (SPEC-055). */}
        <p className="case-chrome-spend" aria-label="Effort so far">
          {elapsed && <span>{elapsed}</span>}
          {invocations > 0 && (
            <span className={nearCap(invocations, invocationCap) ? "spend-near-cap" : undefined}>
              {invocationCap > 0 ? `${invocations}/${invocationCap} calls` : `${invocations} calls`}
            </span>
          )}
          {tokens > 0 && <span>{(tokens / 1000).toFixed(0)}k tokens</span>}
        </p>

        <div className="altitude-control" role="group" aria-label="How much detail to show">
          {ALTITUDES.map((a) => (
            <button
              key={a.key}
              type="button"
              className={`altitude-option${altitude === a.key ? " selected" : ""}`}
              aria-pressed={altitude === a.key}
              title={a.blurb}
              onClick={() => onAltitudeChange(a.key)}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}

/** The altitude hook, re-exported so screens take one import. */
export { useAltitude };
