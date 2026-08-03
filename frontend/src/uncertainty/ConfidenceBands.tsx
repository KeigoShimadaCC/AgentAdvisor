import { CONFIDENCE_BANDS, confidenceBand } from "../copy/terms";
import { NotAssessedWidget } from "./NotAssessedWidget";
import type { AssessedConfidence, NotAssessed } from "../generated/uncertainty_view";

interface ConfidenceBandsProps {
  confidence: AssessedConfidence | NotAssessed | null | undefined;
}

/**
 * Five-step labeled confidence bands with the basis text below.
 */
export function ConfidenceBands({ confidence }: ConfidenceBandsProps) {
  if (!confidence || confidence.kind === "not_assessed") {
    return <NotAssessedWidget reason={confidence?.reason ?? "Not assessed"} />;
  }

  const assessed = confidence as AssessedConfidence;
  const active = confidenceBand(assessed.value);

  return (
    <div className="confidence-bands">
      <div className="confidence-band-list" role="radiogroup" aria-label="Confidence level">
        {CONFIDENCE_BANDS.map((band) => {
          const isActive = band.label === active.label;
          return (
            <div
              key={band.key}
              className={`confidence-band ${isActive ? "active" : ""}`}
            >
              <span
                className="confidence-band-label"
                aria-current={isActive ? "true" : "false"}
              >
                {band.label}
              </span>
            </div>
          );
        })}
      </div>
      <p className="confidence-basis">{assessed.basis}</p>
    </div>
  );
}
