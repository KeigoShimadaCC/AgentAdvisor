import { NotAssessedWidget } from "./NotAssessedWidget";
import type { AssessedStability, NotAssessed } from "../generated/uncertainty_view";

interface StabilityDotsProps {
  stability: AssessedStability | NotAssessed | null | undefined;
}

/**
 * Stability encoding: k-of-n filled dots.
 */
export function StabilityDots({ stability }: StabilityDotsProps) {
  if (!stability || stability.kind === "not_assessed") {
    return <NotAssessedWidget reason={stability?.reason ?? "Not assessed"} />;
  }

  const assessed = stability as AssessedStability;
  const total = Math.max(1, Math.min(assessed.runs_total, 12));
  const supporting = Math.min(assessed.runs_supporting, total);

  return (
    <div className="stability-dots">
      <span className="stability-dots-caption">
        {supporting} of {assessed.runs_total} sensitivity runs
      </span>
      <div
        className="stability-dots-row"
        aria-label={`Stability: ${supporting} out of ${assessed.runs_total} runs`}
      >
        {Array.from({ length: total }).map((_, i) => (
          <span
            key={i}
            className={`stability-dot ${i < supporting ? "filled" : ""}`}
            aria-hidden="true"
          />
        ))}
      </div>
    </div>
  );
}
