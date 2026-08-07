import { Measure } from "./Measure";
import { encodeConfidence, type Scale } from "./language";
import type { AssessedConfidence, NotAssessed } from "../generated/uncertainty_view";

/**
 * Recommendation confidence, as a band (SPEC-054 rebuild).
 *
 * Semantics unchanged from SPEC-035: the same five steps, the same thresholds,
 * the same basis text. What changed is that the rendering comes from the shared
 * grammar, so this measure looks the same here, on the answer, and beside a
 * claim.
 */
export function ConfidenceBands({
  confidence,
  scale = "full",
}: {
  confidence: AssessedConfidence | NotAssessed | null | undefined;
  scale?: Scale;
}) {
  return <Measure encoding={encodeConfidence(confidence)} scale={scale} />;
}
