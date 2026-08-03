interface CoverageBarProps {
  /** Fraction covered, 0–1. */
  fraction: number;
  /** Covered count, for the label. */
  covered: number;
  /** Total leaf count, for the label. */
  total: number;
  /** Accessible label. */
  label?: string;
}

/**
 * Coverage fraction bar with an explicit "X of Y questions" label.
 */
export function CoverageBar({ fraction, covered, total, label }: CoverageBarProps) {
  const pct = Math.max(0, Math.min(100, fraction * 100));
  const aria = label ?? `${covered} of ${total} questions answered`;

  return (
    <div className="coverage-bar" role="img" aria-label={`${aria}: ${Math.round(pct)}%`}>
      <div className="coverage-bar-track">
        <div className="coverage-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="coverage-bar-label">
        {covered} of {total} questions
      </span>
    </div>
  );
}
