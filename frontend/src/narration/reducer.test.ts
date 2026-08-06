import { describe, expect, it } from "vitest";
import type { TranslatedEvent } from "../api/sse";
import {
  INITIAL_NARRATION,
  narrationLine,
  reduceAll,
  reduceNarration,
  voiceFor,
} from "./reducer";

/**
 * The fold, tested without a DOM (SPEC-047).
 *
 * "What is happening" is a projection over an event sequence, so its
 * correctness is a reducer question. Keeping it here means the narrator's
 * markup and the narrator's truth fail separately.
 */

let cursor = 0;
function ev(
  event_type: string,
  raw_payload: Record<string, unknown> = {},
  extra: Partial<TranslatedEvent> = {},
): TranslatedEvent {
  cursor += 1;
  return {
    event_type,
    message: `${event_type} message`,
    technical: false,
    raw_payload,
    line_cursor: cursor,
    ts: "2026-08-05T12:00:00Z",
    actor: null,
    ...extra,
  };
}

describe("reduceNarration", () => {
  it("reports who is working from the started event", () => {
    const state = reduceAll([
      ev("role_invocation_started", { task_id: "T-001", attempt: 1 }, { actor: "researcher" }),
    ]);
    expect(state.activity).toMatchObject({ kind: "working", role: "researcher", taskId: "T-001" });
    expect(narrationLine(state)).toBe("Research is working on T-001");
  });

  it("does not reset the start time on a heartbeat", () => {
    // If a heartbeat re-anchored `since`, the elapsed counter would never
    // advance past one interval — the timer would look frozen while the work
    // was in fact progressing.
    const started = ev(
      "role_invocation_started",
      { task_id: "T-002", attempt: 1 },
      { actor: "analyst", ts: "2026-08-05T12:00:00Z" },
    );
    const beat = ev(
      "role_invocation_progress",
      { task_id: "T-002", attempt: 1, elapsed_s: 20 },
      { actor: "analyst", ts: "2026-08-05T12:00:20Z" },
    );
    const state = reduceAll([started, beat]);
    expect(state.activity).toMatchObject({ kind: "working", since: "2026-08-05T12:00:00Z" });
  });

  it("treats a failed attempt as work continuing, not as work finished", () => {
    const state = reduceAll([
      ev("role_invocation_started", { task_id: "T-003", attempt: 1 }, { actor: "researcher" }),
      ev(
        "role_invocation_attempt",
        { task_id: "T-003", attempt: 1, status: "validation_failure" },
        { actor: "researcher" },
      ),
    ]);
    expect(state.activity).toMatchObject({ kind: "working", attempt: 2 });
  });

  it("marks the role finished on a successful attempt", () => {
    const state = reduceAll([
      ev("role_invocation_started", { task_id: "T-004", attempt: 1 }, { actor: "synthesizer" }),
      ev("role_invocation_attempt", { task_id: "T-004", attempt: 1, status: "ok" }, { actor: "synthesizer" }),
    ]);
    expect(state.activity.kind).toBe("finished");
  });

  it("counts evidence, assumptions and objections as they are unpacked", () => {
    const state = reduceAll([
      ev("evidence_batch_unpacked", { record_count: 6 }),
      ev("evidence_batch_unpacked", { record_count: 3 }),
      ev("assumption_batch_unpacked", { record_count: 4 }),
      ev("objection_batch_unpacked", { record_count: 2 }),
    ]);
    expect(state.evidenceCount).toBe(9);
    expect(state.assumptionCount).toBe(4);
    expect(state.objectionCount).toBe(2);
  });

  it("ignores an unknown event type without losing state", () => {
    // A stream that grows a new event must not blank the narrator.
    const before = reduceAll([
      ev("role_invocation_started", { task_id: "T-005" }, { actor: "planner" }),
    ]);
    const after = reduceNarration(before, ev("some_future_event_type", { anything: true }));
    expect(after.activity).toEqual(before.activity);
    expect(after.cursor).toBeGreaterThan(before.cursor);
  });

  it("never lets the cursor go backwards", () => {
    const state = reduceAll([
      { ...ev("stage_completed", { stage: "intake" }), line_cursor: 40 },
      { ...ev("stage_completed", { stage: "framing" }), line_cursor: 12 },
    ]);
    expect(state.cursor).toBe(40);
  });
});

describe("loop announcements", () => {
  it("announces a repair round with its number", () => {
    // The whole point: every backward edge is intra-phase, so nothing in a
    // six-step indicator moves. Without this the user sees a static block.
    const state = reduceAll([ev("stop_decision_evaluated", { outcome: "repair" })]);
    expect(state.loops.repair).toBe(1);
    expect(state.announcements).toHaveLength(1);
    expect(state.announcements[0].kind).toBe("loop");
    expect(state.announcements[0].text).toContain("repair round 1");
  });

  it("counts a second repair round distinctly from the first", () => {
    const state = reduceAll([
      ev("stop_decision_evaluated", { outcome: "repair" }),
      ev("stop_decision_evaluated", { outcome: "repair" }),
    ]);
    expect(state.loops.repair).toBe(2);
    expect(state.announcements[1].text).toContain("repair round 2");
    expect(state.announcements[0].text).not.toEqual(state.announcements[1].text);
  });

  it("does not announce a stop decision that proceeds to synthesis", () => {
    const state = reduceAll([ev("stop_decision_evaluated", { outcome: "synthesize" })]);
    expect(state.loops.repair).toBe(0);
    expect(state.announcements).toEqual([]);
  });

  it("announces a failed review as a re-synthesis, and an accepted one not at all", () => {
    const failed = reduceAll([ev("review_evaluated", { outcome: "reject" })]);
    expect(failed.loops.resynthesis).toBe(1);
    expect(failed.announcements[0].text).toContain("Rewriting the synthesis");

    const accepted = reduceAll([ev("review_evaluated", { outcome: "accept" })]);
    expect(accepted.loops.resynthesis).toBe(0);
    expect(accepted.announcements).toEqual([]);
  });

  it("announces scope revisions with their number", () => {
    const state = reduceAll([
      ev("framing_revision_requested", {}),
      ev("framing_revision_requested", {}),
    ]);
    expect(state.loops.rescope).toBe(2);
    expect(state.announcements[1].text).toContain("Scope revision 2");
  });

  it("surfaces refusals, because a run that did less must say so", () => {
    const state = reduceAll([
      ev("task_budget_refused", { task_id: "T-9" }),
      ev("task_marginal_value_refused", { task_id: "T-10" }),
    ]);
    expect(state.announcements.map((a) => a.kind)).toEqual(["refusal", "refusal"]);
  });
});

describe("narrationLine", () => {
  it("says nothing rather than inventing reassurance", () => {
    expect(narrationLine(INITIAL_NARRATION)).toBeNull();
  });

  it("reports completion once the case finalizes", () => {
    const state = reduceAll([ev("case_finalized", {})]);
    expect(state.terminal).toBe(true);
    expect(narrationLine(state)).toBe("This case is complete.");
  });

  it("shows the attempt number only when retrying", () => {
    const first = reduceAll([
      ev("role_invocation_started", { task_id: "T-1", attempt: 1 }, { actor: "auditor" }),
    ]);
    expect(narrationLine(first)).not.toContain("attempt");

    const retry = reduceNarration(
      first,
      ev("role_invocation_attempt", { task_id: "T-1", attempt: 1, status: "backend_failure" }, { actor: "auditor" }),
    );
    expect(narrationLine(retry)).toContain("attempt 2");
  });
});

describe("voiceFor", () => {
  it("names every role the pipeline can report, including phase 8's", () => {
    expect(voiceFor("challenger")).toBe("The Challenger");
    expect(voiceFor("ach")).toBe("Competing hypotheses");
    expect(voiceFor("independent_reviewer")).toBe("The independent reviewer");
  });

  it("degrades a new role to something readable rather than a raw enum", () => {
    expect(voiceFor("future_new_role")).toBe("future new role");
    expect(voiceFor(null)).toBe("The system");
  });
});
