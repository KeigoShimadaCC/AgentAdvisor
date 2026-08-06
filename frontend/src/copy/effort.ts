/**
 * How long this actually takes (SPEC-050).
 *
 * The effort chips promised "roughly 10–20 minutes" for a standard case. The
 * first verified real case took 191 minutes and 1.58 million tokens. A product
 * whose whole pitch is epistemic honesty cannot open with an estimate off by an
 * order of magnitude — and the repair is not a better guess, it is to stop
 * guessing and report what runs took.
 *
 * `GET /api/effort-history` returns p50 and p90 per budget profile, computed
 * from completed cases on disk, with the sample count. With no history there is
 * no number, and the fallback says so rather than inventing one. "We don't know
 * yet" is a true statement; "roughly 10–20 minutes" was not.
 */

export interface EffortProfileHistory {
  samples: number;
  p50_s: number;
  p90_s: number;
}

export interface EffortHistory {
  profiles: Record<string, EffortProfileHistory>;
}

/**
 * Below this, one slow run moves the range more than the method does, so the
 * number would describe an accident rather than the work.
 */
export const MIN_SAMPLES_TO_QUOTE = 3;

export function formatDuration(seconds: number): string {
  // Compared on seconds, not on rounded minutes: 30s rounds to 1 and would
  // read as "1 min", which is a longer claim than the measurement supports.
  if (seconds < 60) return "under a minute";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours}h` : `${hours}h ${rest}m`;
}

/**
 * The line under an effort chip.
 *
 * Three states, and each says which one it is:
 *  - enough history → a measured range, labelled as measured;
 *  - one or two runs → the range, labelled as too few to generalise from;
 *  - nothing → no number at all.
 */
export function effortTimeRange(history: EffortHistory | null, backendValue: string): string {
  const profile = history?.profiles?.[backendValue];
  if (!profile || profile.samples === 0) {
    return "not measured yet";
  }
  const low = formatDuration(profile.p50_s);
  const high = formatDuration(profile.p90_s);
  const range = low === high ? low : `${low}–${high}`;
  if (profile.samples < MIN_SAMPLES_TO_QUOTE) {
    return `${range} (${profile.samples} run${profile.samples === 1 ? "" : "s"} so far)`;
  }
  return `${range} (measured, ${profile.samples} runs)`;
}

/** The explanatory line beneath the whole selector. */
export function effortHistoryNote(history: EffortHistory | null): string {
  const total = Object.values(history?.profiles ?? {}).reduce((sum, p) => sum + p.samples, 0);
  if (total === 0) {
    return "No runs have finished here yet, so there is nothing honest to promise about timing. These times will appear once there are runs to measure.";
  }
  if (total < MIN_SAMPLES_TO_QUOTE) {
    return `Times are from ${total} finished run${total === 1 ? "" : "s"} — too few to generalise from, and shown anyway rather than replaced with a guess.`;
  }
  return `Times are the median and 90th percentile of ${total} finished runs, not an estimate. They move as more cases complete.`;
}
