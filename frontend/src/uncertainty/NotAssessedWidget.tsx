import { Measure } from "./Measure";
import type { Scale } from "./language";

/**
 * The sentinel, explicit (SPEC-054 rebuild).
 *
 * "Not assessed" and "assessed as low" are different facts and a reader acts
 * differently on each, so this never degrades to a zero, an empty state or a
 * low value. It goes through the same grammar as every other measure, so it
 * cannot drift into looking like one of them.
 */
export function NotAssessedWidget({ reason, scale = "full" }: { reason: string; scale?: Scale }) {
  return <Measure encoding={{ kind: "not_assessed", reason }} scale={scale} />;
}
