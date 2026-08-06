import { describe, it, expect } from "vitest";
import { honestSentence } from "./honestSentence";
import type { UncertaintyView } from "../generated/uncertainty_view";

function measures(overrides: Partial<UncertaintyView> = {}): UncertaintyView {
  return {
    recommendation_confidence: { kind: "assessed", value: 0.72, basis: "mixed evidence" },
    evidence_confidence: { kind: "assessed", value: 0.55, basis: "two primary sources" },
    model_stability: { kind: "assessed", runs_supporting: 9, runs_total: 10, share: 0.9 },
    ...overrides,
  } as UncertaintyView;
}

describe("the honest sentence", () => {
  it("reads as one claim about how sure this is", () => {
    const { text } = honestSentence(measures());
    expect(text).toBe(
      "This is a recommendation made with moderate confidence and thin evidence, and it held across every sensitivity run.",
    );
  });

  it("invents no number the encodings do not carry", () => {
    // Averaging a source grade with a stability share produces a figure with no
    // referent — the exact false precision the four separate encodings exist to
    // avoid. The sentence is therefore words only.
    const { text } = honestSentence(measures());
    expect(text).not.toMatch(/\d/);
    expect(text).not.toMatch(/%/);
    expect(text).not.toMatch(/score|combined|overall confidence of/i);
  });

  it("names a measure that was not assessed rather than quietly dropping it", () => {
    const { text, notAssessed } = honestSentence(
      measures({ model_stability: { kind: "not_assessed", reason: "single run" } }),
    );
    expect(notAssessed).toEqual(["stability"]);
    expect(text).toMatch(/Stability was not assessed\./);
    // And it does not claim stability held.
    expect(text).not.toMatch(/held across/);
  });

  it("names several gaps together", () => {
    const { text, notAssessed } = honestSentence(
      measures({
        evidence_confidence: { kind: "not_assessed", reason: "no critique run" },
        model_stability: { kind: "not_assessed", reason: "single run" },
      }),
    );
    expect(notAssessed).toEqual(["evidence strength", "stability"]);
    expect(text).toMatch(/Evidence strength and stability were not assessed\./);
  });

  it("says plainly that it cannot tell you, when nothing was assessed", () => {
    const { text } = honestSentence({
      recommendation_confidence: { kind: "not_assessed", reason: "n/a" },
      evidence_confidence: { kind: "not_assessed", reason: "n/a" },
      model_stability: { kind: "not_assessed", reason: "n/a" },
    } as UncertaintyView);
    expect(text).toMatch(/nothing here to tell you how sure this is/i);
  });

  it("handles a case with no uncertainty view at all", () => {
    const { text, notAssessed } = honestSentence(null);
    expect(text).toMatch(/nothing here to tell you/i);
    expect(notAssessed).toHaveLength(4);
  });

  it("uses coarse words, because the underlying values are not precise", () => {
    const words = [0.95, 0.72, 0.45, 0.1].map(
      (value) =>
        honestSentence(
          measures({ recommendation_confidence: { kind: "assessed", value, basis: "x" } }),
        ).text,
    );
    expect(words[0]).toContain("high confidence");
    expect(words[1]).toContain("moderate confidence");
    expect(words[2]).toContain("limited confidence");
    expect(words[3]).toContain("low confidence");
  });

  it("does not claim stability when it held in only half the runs", () => {
    const { text } = honestSentence(
      measures({
        model_stability: { kind: "assessed", runs_supporting: 5, runs_total: 10, share: 0.5 },
      }),
    );
    expect(text).toMatch(/only about half/);
  });
});
