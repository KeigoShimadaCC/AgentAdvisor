interface SplitBarProps {
  /** Count of items supporting the claim. */
  forCount: number;
  /** Count of items against the claim. */
  againstCount: number;
  /** Optional accessible label describing what is split. */
  label?: string;
}

/**
 * For/against split bar that never nets out.
 *
 * The two sides are rendered proportionally but both always have a visible
 * presence when their count is non-zero. The numbers are shown explicitly so
 * evidence on both sides stays legible rather than collapsing into a net.
 */
export function SplitBar({ forCount, againstCount, label }: SplitBarProps) {
  const total = forCount + againstCount;
  const forPct = total > 0 ? (forCount / total) * 100 : 0;
  const againstPct = total > 0 ? (againstCount / total) * 100 : 0;
  const aria = label ?? "Evidence for and against";

  return (
    <div className="split-bar" role="img" aria-label={`${aria}: ${forCount} for, ${againstCount} against`}>
      <div className="split-bar-track">
        {forCount > 0 && (
          <div
            className="split-bar-for"
            style={{ width: `${Math.max(forPct, forCount > 0 ? 8 : 0)}%` }}
          />
        )}
        {againstCount > 0 && (
          <div
            className="split-bar-against"
            style={{ width: `${Math.max(againstPct, againstCount > 0 ? 8 : 0)}%` }}
          />
        )}
      </div>
      <div className="split-bar-labels">
        <span className="split-bar-for-count">{forCount} for</span>
        <span className="split-bar-against-count">{againstCount} against</span>
      </div>
    </div>
  );
}
