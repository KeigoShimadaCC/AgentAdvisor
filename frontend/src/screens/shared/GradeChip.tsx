import { sourceTierLabel, levelLabel } from "../../copy/terms";

interface GradeChipProps {
  /** Source tier enum (primary/official/reputable/weak) or null. */
  sourceTier?: string | null;
  /** Reliability level (high/medium/low). */
  reliability: string;
  /** Directness level (high/medium/low). */
  directness: string;
}

/**
 * Two-part grade chip: source tier on one side, reliability × directness on
 * the other. Used wherever a source appears so grades are learned once.
 */
export function GradeChip({ sourceTier, reliability, directness }: GradeChipProps) {
  const tier = sourceTierLabel(sourceTier);
  return (
    <span className="grade-chip" aria-label={`Grade: ${tier}, reliability ${levelLabel(reliability)}, directness ${levelLabel(directness)}`}>
      <span className="grade-chip-tier">{tier}</span>
      <span className="grade-chip-sep" aria-hidden="true">×</span>
      <span className="grade-chip-reliability">{levelLabel(reliability)} reliability</span>
      <span className="grade-chip-sep" aria-hidden="true">·</span>
      <span className="grade-chip-directness">{levelLabel(directness)} directness</span>
    </span>
  );
}
