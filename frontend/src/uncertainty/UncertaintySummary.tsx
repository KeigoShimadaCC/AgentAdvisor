import { ProbabilityBand } from "./ProbabilityBand";
import { ConfidenceBands } from "./ConfidenceBands";
import { SourceStrengthGrade } from "./SourceStrengthGrade";
import { StabilityDots } from "./StabilityDots";
import type { UncertaintyView } from "../generated/uncertainty_view";
import type { Scale } from "./language";

/**
 * The four measures together, at one scale (SPEC-054).
 *
 * Together, and never combined. They are laid out side by side because they are
 * four separate answers to four separate questions — how likely, how sure of the
 * recommendation, how strong the evidence, how stable across runs — and a reader
 * needs to see that they can disagree.
 *
 * There is deliberately no fifth element. A combined score would be the most
 * requested feature and the one that destroys the property the whole data model
 * protects; `uncertainty.spec.ts` asserts no such number renders anywhere.
 */
export function UncertaintySummary({
  uncertainty,
  scale = "summary",
}: {
  uncertainty: UncertaintyView | null | undefined;
  scale?: Scale;
}) {
  if (!uncertainty) return null;
  const probabilities = Object.entries(uncertainty.outcome_probabilities ?? {});
  const [primaryLabel, primary] = probabilities[0] ?? [];

  return (
    <section className={`uncertainty-summary u-scale-${scale}`} aria-label="How sure this is">
      {primary && <ProbabilityBand label={primaryLabel ?? "Outcome"} probability={primary} scale={scale} />}
      <div className="uncertainty-measure">
        <span className="u-label">Confidence</span>
        <ConfidenceBands confidence={uncertainty.recommendation_confidence} scale={scale} />
      </div>
      <div className="uncertainty-measure">
        <span className="u-label">Evidence</span>
        <SourceStrengthGrade source={uncertainty.evidence_confidence} scale={scale} />
      </div>
      <div className="uncertainty-measure">
        <span className="u-label">Stability</span>
        <StabilityDots stability={uncertainty.model_stability} scale={scale} />
      </div>
    </section>
  );
}
