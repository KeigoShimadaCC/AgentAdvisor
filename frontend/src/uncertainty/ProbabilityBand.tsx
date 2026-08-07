import { Measure } from "./Measure";
import { Why } from "./Why";
import { encodeProbability, type Scale } from "./language";
import type { ProbabilityView, NotAssessed } from "../generated/uncertainty_view";

/**
 * Outcome probability, as a range (SPEC-054 rebuild).
 *
 * A point renders visibly differently from an interval, because Section 9's
 * point-XOR-interval rule is a claim about what is known rather than a
 * formatting preference — an interval is the statement that the point is *not*
 * known, and collapsing it to a midpoint asserts the opposite.
 *
 * The old bespoke popover is replaced by `Why`, the same expand-in-place
 * gesture every other claim uses.
 */
export function ProbabilityBand({
  label,
  probability,
  scale = "full",
}: {
  label: string;
  probability: ProbabilityView | NotAssessed | null | undefined;
  scale?: Scale;
}) {
  const encoding = encodeProbability(probability);
  const adjustments =
    encoding.kind === "range" && probability
      ? (((probability as ProbabilityView).adjustments ?? []) as Record<string, unknown>[])
      : [];

  return (
    <div className="probability-band">
      <Measure encoding={encoding} scale={scale} label={label} />
      {scale === "full" && adjustments.length > 0 && (
        <Why subject={label} adjustments={adjustments} />
      )}
    </div>
  );
}
