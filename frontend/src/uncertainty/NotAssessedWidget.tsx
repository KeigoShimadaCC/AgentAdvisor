interface NotAssessedWidgetProps {
  reason: string;
}

/**
 * Shared sentinel state for any uncertainty measure that has not been assessed.
 * Never renders a number.
 */
export function NotAssessedWidget({ reason }: NotAssessedWidgetProps) {
  return (
    <div className="not-assessed-widget">
      <span className="not-assessed-stamp" aria-hidden="true">
        —
      </span>
      <span className="not-assessed-reason">{reason}</span>
    </div>
  );
}
