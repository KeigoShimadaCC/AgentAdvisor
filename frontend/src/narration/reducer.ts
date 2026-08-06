import { voiceFor, roleVoice } from "../copy/voices";
import type { TranslatedEvent } from "../api/sse";

/**
 * The event → narration fold (SPEC-047).
 *
 * "What is happening right now" is a projection over an event sequence, not a
 * property of any single event, so it belongs in a pure reducer rather than
 * scattered across component state. That split is what lets the narrator be
 * unit-tested against recorded audit fixtures with no DOM, and it is what the
 * away digest (SPEC-051) reuses to summarise a cursor gap — one definition of
 * what an event means, consumed twice.
 *
 * Deliberately tolerant: an unknown event type advances the cursor and changes
 * nothing else. A stream that grows a new event type must not blank the
 * narrator.
 */

/** Whose turn it is, and how sure we are that it is still their turn. */
export type Activity =
  | { kind: "idle" }
  | { kind: "working"; role: string; taskId: string | null; attempt: number; since: string | null }
  | { kind: "finished"; role: string; taskId: string | null; outcome: string }
  | { kind: "blocked"; reason: string };

/** A cycle the case has entered, and how many times. */
export interface LoopState {
  /** Repair rounds consumed (`stop_decision → repair → challenge`). */
  repair: number;
  /** Synthesis re-runs after a failed review. */
  resynthesis: number;
  /** Scope revisions requested by the user. */
  rescope: number;
}

export interface NarrationState {
  activity: Activity;
  loops: LoopState;
  /** Most recent stage the engine reported completing. */
  lastStageCompleted: string | null;
  /** Evidence records gathered so far, for the "n of m" counter. */
  evidenceCount: number;
  /** Assumptions recorded so far. */
  assumptionCount: number;
  /** Objections raised so far. */
  objectionCount: number;
  /** Thesis revisions, newest last. */
  thesisRevisions: { revision: number; preferred: string }[];
  /** Announcements worth showing the user, newest last. */
  announcements: Announcement[];
  /** Highest cursor folded in, so a caller can resume from it. */
  cursor: number;
  /** True once the case has finalized or failed. */
  terminal: boolean;
}

export interface Announcement {
  /** Stable key so React can list these without index churn. */
  id: string;
  kind: "loop" | "gate" | "refusal" | "failure";
  text: string;
  cursor: number;
}

export const INITIAL_NARRATION: NarrationState = {
  activity: { kind: "idle" },
  loops: { repair: 0, resynthesis: 0, rescope: 0 },
  lastStageCompleted: null,
  evidenceCount: 0,
  assumptionCount: 0,
  objectionCount: 0,
  thesisRevisions: [],
  announcements: [],
  cursor: 0,
  terminal: false,
};

function num(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function str(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function announce(
  state: NarrationState,
  kind: Announcement["kind"],
  text: string,
  cursor: number,
): Announcement[] {
  return [...state.announcements, { id: `${kind}-${cursor}`, kind, text, cursor }];
}

/**
 * Fold one event into the narration state.
 *
 * Pure: same input, same output, no clock and no globals. The elapsed time a
 * narrator shows is derived from `activity.since` at render time rather than
 * stored here, so folding the same events twice cannot drift.
 */
/**
 * Append what an announcement is *about*, when the event says so (SPEC-049).
 *
 * "The review did not pass" tells a reader that something is wrong and nothing
 * about what. Where the payload names a target, saying it turns a status line
 * into a sentence about the argument.
 */
function contesting(line: string, target: string | null): string {
  return target ? `${line} At issue: ${target.replace(/_/g, " ")}.` : line;
}

export function reduceNarration(state: NarrationState, event: TranslatedEvent): NarrationState {
  const next: NarrationState = { ...state, cursor: Math.max(state.cursor, event.line_cursor) };
  const payload = event.raw_payload ?? {};
  const role = event.actor ?? "the system";
  const taskId = str(payload.task_id);

  switch (event.event_type) {
    case "role_invocation_started":
      return {
        ...next,
        activity: {
          kind: "working",
          role,
          taskId,
          attempt: num(payload.attempt, 1),
          since: event.ts ?? null,
        },
      };

    case "role_invocation_progress":
      // A heartbeat confirms the same work is still running; it must not reset
      // the start time, or the elapsed counter would never advance.
      return state.activity.kind === "working"
        ? next
        : {
            ...next,
            activity: {
              kind: "working",
              role,
              taskId,
              attempt: num(payload.attempt, 1),
              since: event.ts ?? null,
            },
          };

    case "role_invocation_attempt": {
      const status = str(payload.status) ?? "unknown";
      if (status === "ok") {
        return { ...next, activity: { kind: "finished", role, taskId, outcome: status } };
      }
      // A non-ok attempt means the ladder is retrying, so work continues.
      return {
        ...next,
        activity: {
          kind: "working",
          role,
          taskId,
          attempt: num(payload.attempt, 1) + 1,
          since: event.ts ?? null,
        },
      };
    }

    case "stage_completed":
      return { ...next, lastStageCompleted: str(payload.stage) };

    case "evidence_batch_unpacked":
      return { ...next, evidenceCount: next.evidenceCount + num(payload.record_count) };

    case "assumption_batch_unpacked":
      return { ...next, assumptionCount: next.assumptionCount + num(payload.record_count) };

    case "objection_batch_unpacked":
      return { ...next, objectionCount: next.objectionCount + num(payload.record_count, 1) };

    case "thesis_revision_recorded":
      return {
        ...next,
        thesisRevisions: [
          ...next.thesisRevisions,
          {
            revision: num(payload.revision),
            preferred: str(payload.preferred_alternative) ?? "unchanged",
          },
        ],
      };

    // ── The loops. These are the events the old phase strip could not show ──
    //
    // Every one of them is intra-phase, so nothing in a six-step indicator
    // moves when they fire. Announcing them in plain language is the whole
    // difference between "it is working" and "it has stalled".

    case "stop_decision_evaluated": {
      const outcome = str(payload.outcome);
      if (outcome !== "repair") return next;
      const repair = next.loops.repair + 1;
      return {
        ...next,
        loops: { ...next.loops, repair },
        announcements: announce(
          next,
          "loop",
          contesting(
            `${voiceFor("challenger")} found something worth fixing. Going back to research — repair round ${repair}.`,
            str(payload.target_section) ?? str(payload.reason),
          ),
          event.line_cursor,
        ),
      };
    }

    case "review_evaluated": {
      const outcome = str(payload.outcome);
      if (outcome === "accept" || outcome === "accepted") return next;
      const resynthesis = next.loops.resynthesis + 1;
      return {
        ...next,
        loops: { ...next.loops, resynthesis },
        announcements: announce(
          next,
          "loop",
          contesting(
            `${voiceFor("reviewer")} did not pass the brief. Rewriting the synthesis — attempt ${resynthesis + 1}.`,
            str(payload.defect_type) ?? str(payload.reason),
          ),
          event.line_cursor,
        ),
      };
    }

    case "framing_revision_requested": {
      const rescope = next.loops.rescope + 1;
      return {
        ...next,
        loops: { ...next.loops, rescope },
        announcements: announce(
          next,
          "loop",
          contesting(
            `Scope revision ${rescope} requested. ${voiceFor("director_framing")} is re-framing the decision.`,
            str(payload.reason),
          ),
          event.line_cursor,
        ),
      };
    }

    case "final_revision_requested":
      return {
        ...next,
        announcements: announce(
          next,
          "loop",
          "You sent the recommendation back. Rewriting the synthesis with your note.",
          event.line_cursor,
        ),
      };

    case "control_checkpoint_signed":
      return {
        ...next,
        announcements: announce(
          next,
          "gate",
          `Checkpoint signed: ${str(payload.gate) ?? "checkpoint"}.`,
          event.line_cursor,
        ),
      };

    // ── Refusals. A run that did less than it could have says so as it happens.

    case "task_budget_refused":
    case "task_marginal_value_refused":
    case "tasks_cancelled":
      return {
        ...next,
        announcements: announce(next, "refusal", event.message, event.line_cursor),
      };

    case "task_failed":
      return {
        ...next,
        announcements: announce(next, "failure", event.message, event.line_cursor),
      };

    case "case_finalized":
      return {
        ...next,
        terminal: true,
        activity: { kind: "idle" },
      };

    default:
      // Unknown types advance the cursor and nothing else. A stream that grows
      // a new event must never blank the narrator.
      return next;
  }
}

/** Fold a whole sequence, e.g. on first load or when replaying a cursor gap. */
export function reduceAll(
  events: TranslatedEvent[],
  from: NarrationState = INITIAL_NARRATION,
): NarrationState {
  return events.reduce(reduceNarration, from);
}

/**
 * The one present-tense line.
 *
 * Returns null when there is nothing truthful to say, so the caller renders
 * nothing rather than inventing reassurance.
 */
export function narrationLine(state: NarrationState): string | null {
  const { activity } = state;
  switch (activity.kind) {
    case "working": {
      const who = voiceFor(activity.role);
      const attempt = activity.attempt > 1 ? ` (attempt ${activity.attempt})` : "";
      return activity.taskId
        ? `${who} is working on ${activity.taskId}${attempt}`
        : `${who} is working${attempt}`;
    }
    case "finished":
      return `${voiceFor(activity.role)} finished`;
    case "blocked":
      return activity.reason;
    case "idle":
      return state.terminal ? "This case is complete." : null;
  }
}

/**
 * Re-exported so SPEC-047's callers keep one import while the table itself
 * lives in `copy/voices.ts`, where `voices.test.ts` checks it against the role
 * enum in the Python source.
 */
export { voiceFor, roleVoice };
