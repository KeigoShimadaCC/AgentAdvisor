interface SkeletonProps {
  /** Which screen's shape to imitate. */
  shape?: "brief" | "list" | "sheet";
  label?: string;
}

/**
 * Content-shaped loading states (SPEC-048).
 *
 * Replaces `<p>Loading…</p>`, which was the loading state on every screen. The
 * screens here have strong, predictable shapes, so a skeleton that matches them
 * reads as speed rather than as a stall — and it stops the layout jumping when
 * the content lands.
 */
export function Skeleton({ shape = "brief", label = "Loading" }: SkeletonProps) {
  const rows = shape === "list" ? 5 : shape === "sheet" ? 4 : 6;
  return (
    <div className={`skeleton skeleton-${shape}`} role="status" aria-label={label}>
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton-block" aria-hidden="true">
          <div className="skeleton-line skeleton-line-title" />
          <div className="skeleton-line" />
          <div className="skeleton-line skeleton-line-short" />
        </div>
      ))}
    </div>
  );
}
