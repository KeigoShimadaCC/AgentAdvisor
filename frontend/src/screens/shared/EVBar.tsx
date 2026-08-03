import { formatExpectedValue } from "../../copy/format";

interface EVBarProps {
  /** The expected value for this option. */
  value: number | null | undefined;
  /** The minimum EV across all options, for scaling. */
  min: number;
  /** The maximum EV across all options, for scaling. */
  max: number;
  /** Accessible label. */
  label: string;
}

/**
 * Expected-value bar.
 *
 * Renders a horizontal bar scaled between the option set's min and max EV so
 * relative magnitude is visible at a glance. Zero is anchored when the range
 * crosses it.
 */
export function EVBar({ value, min, max, label }: EVBarProps) {
  if (value == null || Number.isNaN(value)) {
    return <span className="ev-bar ev-bar-none">Not modeled</span>;
  }
  const span = max - min || 1;
  const crossesZero = min < 0 && max > 0;
  const pct = Math.max(0, Math.min(100, ((value - min) / span) * 100));
  const formatted = formatExpectedValue(value);

  return (
    <div className="ev-bar" role="img" aria-label={`${label}: expected value ${formatted}`}>
      <div className="ev-bar-track">
        {crossesZero && (
          <div
            className="ev-bar-zero"
            style={{ left: `${((-min) / span) * 100}%` }}
            aria-hidden="true"
          />
        )}
        <div
          className={value >= 0 ? "ev-bar-fill ev-bar-positive" : "ev-bar-fill ev-bar-negative"}
          style={{
            left: crossesZero ? `${((-min) / span) * 100}%` : "0%",
            width: `${Math.abs(pct - (crossesZero ? ((-min) / span) * 100 : 0))}%`,
          }}
        />
      </div>
      <span className="ev-bar-value">{formatted}</span>
    </div>
  );
}
