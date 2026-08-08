import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  stopReasonLabel,
  budgetDimensionLabel,
  STOP_REASON_LABELS,
  BUDGET_KIND_LABELS,
} from "./terms";

/**
 * Why a case stopped, in words (SPEC-056 follow-up).
 *
 * For the whole of phase 9 these enum values reached users verbatim: the
 * Delivery sheet and the early-stop path rendered "Stop reasons:
 * no_critical_evidence_gaps_remain, recommendation_stable_across_plausible_..."
 * — the exact failure the terminology lexicon exists to prevent, on the one
 * screen where a reader is deciding whether to trust the recommendation.
 *
 * The enum is read out of the Python rather than copied, so adding a stop
 * reason fails this test until someone decides what it says to a human. A
 * hardcoded list here would drift silently, which is how the leak survived.
 */
const REPO = resolve(__dirname, "../../..");

/** Every string literal in a StrEnum body, whatever the line layout. */
function enumValues(file: string, enumName: string): string[] {
  const source = readFileSync(resolve(REPO, file), "utf8");
  const start = source.indexOf(`class ${enumName}(StrEnum):`);
  expect(start, `${enumName} not found in ${file}`).toBeGreaterThan(-1);
  const rest = source.slice(start + 1);
  const end = rest.search(/\nclass /);
  const body = end === -1 ? rest : rest.slice(0, end);
  // Deliberately not anchored per line: StopReason wraps its longer values in
  // parentheses, and a line-anchored pattern silently skips exactly those.
  return [...body.matchAll(/"([a-z_0-9]+)"/g)].map((m) => m[1]);
}

describe("every stop reason says something a person can read", () => {
  const reasons = enumValues("orchestrator/artifacts/disclosure.py", "StopReason");

  it("finds the enum, including its wrapped values", () => {
    // Six today. If this drops, the extractor regressed and the coverage test
    // below would pass vacuously.
    expect(reasons.length).toBeGreaterThanOrEqual(6);
    expect(reasons).toContain("recommendation_stable_across_plausible_sensitivity_ranges");
  });

  it.each(reasons.map((r) => [r]))("has a written label for %s", (reason) => {
    // Asserted against the map, not against the rendered string. The fallback
    // de-underscores, so `stopReasonLabel` returns something underscore-free
    // for a reason nobody has written copy for — an earlier version of this
    // test checked the output and passed happily with a label deleted.
    expect(
      Object.prototype.hasOwnProperty.call(STOP_REASON_LABELS, reason),
      `${reason} has no written label; the fallback would ship "${stopReasonLabel(reason)}"`,
    ).toBe(true);
    expect(STOP_REASON_LABELS[reason]).not.toMatch(/_/);
  });

  it("keeps 'the question is answered' distinct from 'the budget ran out'", () => {
    // The distinction the enum draws and a reader needs: a recommendation that
    // stopped because nothing more would change it is a different claim from
    // one that stopped because the money ran out.
    expect(stopReasonLabel("no_critical_evidence_gaps_remain")).toMatch(/gap/i);
    expect(stopReasonLabel("investigation_budget_exhausted")).toMatch(/budget|ran out/i);
    expect(stopReasonLabel("no_critical_evidence_gaps_remain")).not.toEqual(
      stopReasonLabel("investigation_budget_exhausted"),
    );
  });

  it("degrades to readable text for a reason it has never seen", () => {
    // A new enum value must not reach a user as snake_case while this test is
    // being fixed.
    expect(stopReasonLabel("some_future_reason")).toBe("some future reason");
  });
});

describe("every budget kind says what ran out", () => {
  const dimensions = enumValues("orchestrator/budget.py", "BudgetKind");

  it("finds the enum", () => {
    expect(dimensions.length).toBeGreaterThanOrEqual(6);
  });

  it.each(dimensions.map((d) => [d]))("has a written label for %s", (dimension) => {
    expect(
      Object.prototype.hasOwnProperty.call(BUDGET_KIND_LABELS, dimension),
      `${dimension} has no written label`,
    ).toBe(true);
    expect(BUDGET_KIND_LABELS[dimension]).not.toMatch(/_/);
  });

  it("degrades to readable text for an unknown dimension", () => {
    expect(budgetDimensionLabel("some_future_dimension")).toBe("some future dimension");
  });
});

describe("the frontend and the server say the same thing", () => {
  /**
   * Two copies of this vocabulary exist by necessity: the projection composes
   * the brief's sentence server-side, and the case surface and delivery sheet
   * render `integrity.disclosure` directly. Two copies drift, so this pins them
   * to each other — and to the lowercase, clause-shaped form both need, because
   * they are joined after "Why it stopped:" rather than standing alone.
   */
  const pythonPhrases = (() => {
    const source = readFileSync(
      resolve(REPO, "orchestrator/artifacts/disclosure.py"),
      "utf8",
    );
    const start = source.indexOf("_STOP_REASON_PHRASES");
    expect(start, "_STOP_REASON_PHRASES not found").toBeGreaterThan(-1);
    const body = source.slice(start, source.indexOf("_BUDGET_KIND_PHRASES"));
    return [...body.matchAll(/"([a-z][a-z ,'-]+)"/g)].map((m) => m[1]);
  })();

  it("uses the same wording on both sides", () => {
    for (const [reason, label] of Object.entries(STOP_REASON_LABELS)) {
      expect(
        pythonPhrases,
        `"${label}" (for ${reason}) does not match any server-side phrase`,
      ).toContain(label);
    }
  });

  it("keeps every phrase clause-shaped, not sentence-shaped", () => {
    // "Why it stopped: The budget ran out; The recommendation held" reads as a
    // run-on; lowercase clauses read as the list they are.
    for (const label of Object.values(STOP_REASON_LABELS)) {
      expect(label[0], `"${label}" starts with a capital`).toBe(label[0].toLowerCase());
    }
  });
});
