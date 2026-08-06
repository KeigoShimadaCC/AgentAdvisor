import type { TranslatedEvent } from "../api/sse";

/**
 * What happened while you were away (SPEC-051).
 *
 * Computed, not stored. SPEC-047 already persists a line cursor and the stream
 * replays from it, so the gap between "where I was" and "where the case is" is
 * a fold over events the client has in hand. That keeps one source of truth for
 * what an event means, and makes the digest a pure function of a cursor range —
 * which is the only reason it is testable at all.
 */

export interface Digest {
  /** Events in the gap. Zero means there is nothing to say. */
  events: number;
  evidence: number;
  assumptions: number;
  objections: number;
  thesisChanges: number;
  gatesPassed: number;
  gatesFailed: number;
  repairRounds: number;
  resynthesisRounds: number;
  rescopes: number;
  stagesCompleted: string[];
  /** True when the case parked at a gate during the gap. */
  reachedGate: boolean;
}

export const EMPTY_DIGEST: Digest = {
  events: 0,
  evidence: 0,
  assumptions: 0,
  objections: 0,
  thesisChanges: 0,
  gatesPassed: 0,
  gatesFailed: 0,
  repairRounds: 0,
  resynthesisRounds: 0,
  rescopes: 0,
  stagesCompleted: [],
  reachedGate: false,
};

function num(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function str(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

/**
 * Fold the events in `(sinceCursor, head]` into a digest.
 *
 * `sinceCursor` is exclusive: it is the last cursor the user had seen, so the
 * event at that cursor is not news.
 */
export function digestSince(events: TranslatedEvent[], sinceCursor: number): Digest {
  const gap = events.filter((e) => e.line_cursor > sinceCursor);
  const digest: Digest = { ...EMPTY_DIGEST, stagesCompleted: [] };

  for (const event of gap) {
    digest.events += 1;
    const payload = event.raw_payload ?? {};

    switch (event.event_type) {
      case "evidence_batch_unpacked":
        digest.evidence += num(payload.record_count);
        break;
      case "assumption_batch_unpacked":
        digest.assumptions += num(payload.record_count);
        break;
      case "objection_batch_unpacked":
        digest.objections += num(payload.record_count, 1);
        break;
      case "thesis_revision_recorded":
        // Only a *changed* thesis is news; a revision that reaffirmed the same
        // alternative is the case holding still, which is not worth a line.
        if (payload.changed !== false) digest.thesisChanges += 1;
        break;
      case "stage_completed": {
        const stage = str(payload.stage);
        if (stage) digest.stagesCompleted.push(stage);
        break;
      }
      case "gate_evaluated": {
        const outcome = str(payload.outcome) ?? str(payload.status);
        if (outcome === "pass") digest.gatesPassed += 1;
        else if (outcome != null) digest.gatesFailed += 1;
        break;
      }
      case "stop_decision_evaluated":
        if (str(payload.outcome) === "repair") digest.repairRounds += 1;
        break;
      case "review_evaluated": {
        const outcome = str(payload.outcome);
        if (outcome !== null && outcome !== "accept" && outcome !== "accepted") {
          digest.resynthesisRounds += 1;
        }
        break;
      }
      case "framing_revision_requested":
        digest.rescopes += 1;
        break;
      case "control_checkpoint_reached":
      case "case_parked":
        digest.reachedGate = true;
        break;
      default:
        break;
    }
  }

  return digest;
}

/**
 * The digest as sentences, most consequential first.
 *
 * Ordering is the whole design: a thesis change and a failed gate are things
 * that alter what the reader should believe, and they must not be buried under
 * "gathered 14 pieces of evidence". Returns an empty array when there is
 * nothing worth saying, so the caller renders nothing rather than "0 changes".
 */
export function digestLines(digest: Digest): string[] {
  const lines: string[] = [];

  if (digest.thesisChanges > 0) {
    lines.push(
      digest.thesisChanges === 1
        ? "The working view changed once."
        : `The working view changed ${digest.thesisChanges} times.`,
    );
  }
  if (digest.gatesFailed > 0) {
    lines.push(
      `${digest.gatesFailed} ${digest.gatesFailed === 1 ? "check" : "checks"} did not pass.`,
    );
  }
  if (digest.repairRounds > 0) {
    lines.push(
      `The challenge round sent work back for repair ${digest.repairRounds === 1 ? "once" : `${digest.repairRounds} times`}.`,
    );
  }
  if (digest.resynthesisRounds > 0) {
    lines.push(
      `The brief was rewritten ${digest.resynthesisRounds === 1 ? "once" : `${digest.resynthesisRounds} times`} after review.`,
    );
  }
  if (digest.rescopes > 0) {
    lines.push(`The decision was re-framed ${digest.rescopes === 1 ? "once" : `${digest.rescopes} times`}.`);
  }
  if (digest.objections > 0) {
    lines.push(
      `${digest.objections} ${digest.objections === 1 ? "objection was" : "objections were"} raised.`,
    );
  }
  if (digest.evidence > 0) {
    lines.push(`${digest.evidence} ${digest.evidence === 1 ? "piece" : "pieces"} of evidence gathered.`);
  }
  if (digest.assumptions > 0) {
    lines.push(
      `${digest.assumptions} ${digest.assumptions === 1 ? "assumption was" : "assumptions were"} recorded.`,
    );
  }
  if (digest.stagesCompleted.length > 0) {
    lines.push(
      `${digest.stagesCompleted.length} ${digest.stagesCompleted.length === 1 ? "stage" : "stages"} completed.`,
    );
  }

  return lines;
}
