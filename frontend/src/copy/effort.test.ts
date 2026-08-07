import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  effortTimeRange,
  effortHistoryNote,
  formatDuration,
  MIN_SAMPLES_TO_QUOTE,
  type EffortHistory,
} from "./effort";

function history(profiles: EffortHistory["profiles"]): EffortHistory {
  return { profiles };
}

describe("no authored minute range survives", () => {
  it("has none left in copy/", () => {
    // The promise was "roughly 10–20 minutes"; the first verified real case
    // took 191. This test is what stops one being written back in.
    const dir = resolve(__dirname);
    for (const file of ["terms.ts", "effort.ts", "voices.ts", "honestSentence.ts"]) {
      const source = readFileSync(resolve(dir, file), "utf8");
      // Strip comments: the prose above explains the old promise on purpose.
      const code = source
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .replace(/^\s*\/\/.*$/gm, "");
      const offenders = [...code.matchAll(/["'`][^"'`]*\d+\s*[–-]\s*\d+\s*(minutes|min|hours)/g)];
      expect(offenders.map((m) => m[0]), `${file} carries an authored time range`).toEqual([]);
    }
  });
});

describe("what the chip says", () => {
  it("says a measured range once there is enough history to generalise from", () => {
    const text = effortTimeRange(
      history({ default: { samples: 12, p50_s: 3_600, p90_s: 11_460 } }),
      "default",
    );
    expect(text).toContain("1h");
    expect(text).toContain("3h 11m");
    expect(text).toContain("measured");
    expect(text).toContain("12 runs");
  });

  it("shows one or two runs but says how few they are", () => {
    // Hiding a two-run range would be as dishonest as quoting it as typical.
    const text = effortTimeRange(history({ deep: { samples: 2, p50_s: 600, p90_s: 900 } }), "deep");
    expect(text).toContain("2 runs so far");
    expect(text).not.toContain("measured,");
    expect(MIN_SAMPLES_TO_QUOTE).toBe(3);
  });

  it("says nothing has been measured rather than inventing a number", () => {
    expect(effortTimeRange(null, "default")).toBe("not measured yet");
    expect(effortTimeRange(history({}), "default")).toBe("not measured yet");
    expect(effortTimeRange(history({ light: { samples: 0, p50_s: 0, p90_s: 0 } }), "light")).toBe(
      "not measured yet",
    );
  });

  it("collapses a range whose ends are the same rather than printing '5 min–5 min'", () => {
    const text = effortTimeRange(history({ light: { samples: 4, p50_s: 300, p90_s: 320 } }), "light");
    expect(text).toContain("5 min (measured");
    expect(text).not.toContain("–");
  });
});

describe("the note under the selector", () => {
  it("is honest about an empty history instead of silent", () => {
    expect(effortHistoryNote(null)).toMatch(/nothing honest to promise/i);
    expect(effortHistoryNote(history({}))).toMatch(/nothing honest to promise/i);
  });

  it("names the sample size when it is small", () => {
    expect(effortHistoryNote(history({ default: { samples: 2, p50_s: 60, p90_s: 90 } }))).toMatch(
      /too few to generalise/i,
    );
  });

  it("says these are measurements, not estimates", () => {
    const note = effortHistoryNote(
      history({
        default: { samples: 5, p50_s: 60, p90_s: 90 },
        deep: { samples: 4, p50_s: 600, p90_s: 900 },
      }),
    );
    expect(note).toContain("9 finished runs");
    expect(note).toMatch(/not an estimate/i);
  });
});

describe("formatting a duration", () => {
  it.each([
    [30, "under a minute"],
    [60, "1 min"],
    [3_600, "1h"],
    [5_400, "1h 30m"],
    [11_460, "3h 11m"],
  ])("%is → %s", (seconds, expected) => {
    expect(formatDuration(seconds)).toBe(expected);
  });
});
