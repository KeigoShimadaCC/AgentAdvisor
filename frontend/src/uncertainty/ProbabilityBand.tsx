import { useState } from "react";
import { probabilityPhrase, probabilityRange } from "../copy/terms";
import { NotAssessedWidget } from "./NotAssessedWidget";
import type { ProbabilityView, NotAssessed } from "../generated/uncertainty_view";

interface ProbabilityBandProps {
  /** Outcome label shown next to the band. */
  label: string;
  probability: ProbabilityView | NotAssessed | null | undefined;
}

function isNotAssessed(value: ProbabilityView | NotAssessed): value is NotAssessed {
  return (value as NotAssessed).kind === "not_assessed";
}

/**
 * Probability encoding: qualitative phrase + bracketed range, with a
 * countable-dots popover for the underlying point/interval/method.
 */
export function ProbabilityBand({ label, probability }: ProbabilityBandProps) {
  const [open, setOpen] = useState(false);

  if (!probability || isNotAssessed(probability)) {
    return <NotAssessedWidget reason={probability?.reason ?? "Not estimated"} />;
  }

  const point = probability.point ?? null;
  const low = probability.interval_low ?? null;
  const high = probability.interval_high ?? null;
  const phrase = probabilityPhrase(point);
  const range = probabilityRange(low, high);
  const filled = point != null ? Math.max(0, Math.min(10, Math.round(point * 10))) : 0;

  return (
    <div className="probability-band">
      <div className="probability-band-header">
        <span className="probability-band-label">{label}</span>
        <button
          type="button"
          className="probability-band-toggle link-button"
          onClick={() => setOpen((s) => !s)}
          aria-expanded={open}
          aria-label="Show probability details"
        >
          <span className="probability-band-phrase">{phrase}</span>
          {range && <span className="probability-band-range">{range}</span>}
        </button>
      </div>
      {open && (
        <div className="probability-band-popover" role="dialog" aria-label="Probability details">
          <div className="countable-dots" aria-label={`${filled} out of 10 dots`}>
            {Array.from({ length: 10 }).map((_, i) => (
              <span
                key={i}
                className={`countable-dot ${i < filled ? "filled" : ""}`}
                aria-hidden="true"
              />
            ))}
          </div>
          <p className="probability-band-method">Method: {probability.method}</p>
          {probability.adjustments && probability.adjustments.length > 0 && (
            <ul className="probability-band-adjustments">
              {probability.adjustments.map((adj, i) => {
                const desc =
                  typeof (adj as { description?: unknown }).description === "string"
                    ? (adj as { description: string }).description
                    : String((adj as { description?: unknown }).description ?? "—");
                return <li key={i}>{desc}</li>;
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
