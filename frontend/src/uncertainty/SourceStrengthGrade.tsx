import { Measure } from "./Measure";
import { encodeEvidence, type Scale } from "./language";
import type { AssessedConfidence, NotAssessed } from "../generated/uncertainty_view";

/**
 * Evidence strength, as a grade (SPEC-054 rebuild).
 *
 * A letter rather than a number, because the judgement is ordinal: "B" does not
 * invite arithmetic against a confidence of 0.72 the way "0.8" does. The grade
 * now carries what it means, so the letter is not asked to do that alone.
 */
export function SourceStrengthGrade({
  source,
  scale = "full",
}: {
  source: AssessedConfidence | NotAssessed | null | undefined;
  scale?: Scale;
}) {
  return <Measure encoding={encodeEvidence(source)} scale={scale} />;
}
