import { Measure } from "./Measure";
import { encodeStability, type Scale } from "./language";
import type { AssessedStability, NotAssessed } from "../generated/uncertainty_view";

/**
 * Model stability, as countable marks (SPEC-054 rebuild).
 *
 * `runs_supporting` of `runs_total`, drawn as that many marks. Never a
 * percentage: "9 of 10 runs" is a fact about what was done, and "90%" is a
 * number that invites comparison with the other three measures — precisely the
 * collapse the four separate encodings exist to prevent.
 */
export function StabilityDots({
  stability,
  scale = "full",
}: {
  stability: AssessedStability | NotAssessed | null | undefined;
  scale?: Scale;
}) {
  return <Measure encoding={encodeStability(stability)} scale={scale} />;
}
