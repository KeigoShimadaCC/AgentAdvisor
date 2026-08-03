import { describe, it, expect } from "vitest";
import {
  buildEdits,
  buildApprovePayload,
  buildRevisionPayload,
  needsRevision,
  allGroundRulesConfirmed,
  confirmedKeys,
  canonicalSheetContent,
  computeSummaryHash,
  type SheetState,
} from "./sheetPayload";

const baseState: SheetState = {
  restatement: "Should I take the offer?",
  options: ["Stay", "Switch", "Negotiate"],
  originalOptions: ["Stay", "Switch", "Negotiate"],
  excludedQuestions: [],
  confirmations: { deadline: false, risk_tolerance: false, reversibility: false },
  groundRuleKeys: ["deadline", "risk_tolerance", "reversibility"],
  clarificationAnswers: {},
};

describe("buildEdits", () => {
  it("includes question always, alternatives only when changed, excluded_questions when present", () => {
    const edits = buildEdits(baseState);
    expect(edits.question).toBe("Should I take the offer?");
    expect(edits.alternatives).toBeUndefined();
    expect(edits.excluded_questions).toBeUndefined();
  });

  it("includes alternatives when an option is removed", () => {
    const state = { ...baseState, options: ["Stay", "Switch"] };
    const edits = buildEdits(state);
    expect(edits.alternatives).toEqual(["Stay", "Switch"]);
  });

  it("includes excluded_questions when a question is struck", () => {
    const state = { ...baseState, excludedQuestions: ["Compare TCO"] };
    const edits = buildEdits(state);
    expect(edits.excluded_questions).toEqual(["Compare TCO"]);
  });
});

describe("allGroundRulesConfirmed / confirmedKeys", () => {
  it("is false when nothing is confirmed", () => {
    expect(allGroundRulesConfirmed(baseState)).toBe(false);
    expect(confirmedKeys(baseState)).toEqual([]);
  });

  it("is false when some but not all are confirmed", () => {
    const state = { ...baseState, confirmations: { deadline: true, risk_tolerance: false, reversibility: false } };
    expect(allGroundRulesConfirmed(state)).toBe(false);
    expect(confirmedKeys(state)).toEqual(["deadline"]);
  });

  it("is true when all are confirmed", () => {
    const state = {
      ...baseState,
      confirmations: { deadline: true, risk_tolerance: true, reversibility: true },
    };
    expect(allGroundRulesConfirmed(state)).toBe(true);
    expect(confirmedKeys(state)).toEqual(["deadline", "risk_tolerance", "reversibility"]);
  });
});

describe("buildApprovePayload", () => {
  it("serializes confirmations and summary_hash with decision approve", () => {
    const state = {
      ...baseState,
      confirmations: { deadline: true, risk_tolerance: true, reversibility: true },
    };
    const payload = buildApprovePayload(state, "deadbeef");
    expect(payload.decision).toBe("approve");
    expect(payload.confirmations).toEqual(["deadline", "risk_tolerance", "reversibility"]);
    expect(payload.summary_hash).toBe("deadbeef");
    expect(payload.approved_by).toBe("user");
    // approve must not carry edits or clarification_answers
    expect(payload.edits).toBeUndefined();
    expect(payload.clarification_answers).toBeUndefined();
  });
});

describe("buildRevisionPayload", () => {
  it("uses decision edit when alternatives changed", () => {
    const state = { ...baseState, options: ["Stay"] };
    const payload = buildRevisionPayload(state);
    expect(payload.decision).toBe("edit");
    expect(payload.edits).toBeDefined();
    expect((payload.edits as Record<string, unknown>).alternatives).toEqual(["Stay"]);
  });

  it("uses decision answer_clarifications when only answers are present", () => {
    const state = { ...baseState, clarificationAnswers: { risk_tolerance: "high" } };
    const payload = buildRevisionPayload(state);
    expect(payload.decision).toBe("answer_clarifications");
    expect(payload.clarification_answers).toEqual({ risk_tolerance: "high" });
  });

  it("edit takes precedence when both edits and answers are present", () => {
    const state = {
      ...baseState,
      options: ["Stay"],
      clarificationAnswers: { risk_tolerance: "high" },
    };
    const payload = buildRevisionPayload(state);
    expect(payload.decision).toBe("edit");
  });
});

describe("needsRevision", () => {
  it("is false when nothing changed", () => {
    expect(needsRevision(baseState, "Should I take the offer?")).toBe(false);
  });

  it("is true when restatement changed", () => {
    expect(needsRevision({ ...baseState, restatement: "New wording" }, "Should I take the offer?")).toBe(true);
  });

  it("is true when a question is struck", () => {
    expect(needsRevision({ ...baseState, excludedQuestions: ["X"] }, "Should I take the offer?")).toBe(true);
  });

  it("is true when options changed", () => {
    expect(needsRevision({ ...baseState, options: ["Stay"] }, "Should I take the offer?")).toBe(true);
  });
});

describe("canonicalSheetContent / computeSummaryHash", () => {
  it("is deterministic for the same input", () => {
    const a = canonicalSheetContent(baseState);
    const b = canonicalSheetContent(baseState);
    expect(a).toBe(b);
    expect(computeSummaryHash(a)).toBe(computeSummaryHash(b));
  });

  it("changes when a confirmation flips", () => {
    const confirmed = {
      ...baseState,
      confirmations: { deadline: true, risk_tolerance: true, reversibility: true },
    };
    expect(computeSummaryHash(canonicalSheetContent(confirmed))).not.toBe(
      computeSummaryHash(canonicalSheetContent(baseState)),
    );
  });

  it("returns an 8-char hex string", () => {
    const h = computeSummaryHash(canonicalSheetContent(baseState));
    expect(h).toMatch(/^[0-9a-f]{8}$/);
  });
});
