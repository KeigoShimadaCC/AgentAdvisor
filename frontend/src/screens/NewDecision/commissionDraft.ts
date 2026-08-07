import type { EffortKey } from "../../copy/terms";
import type { Altitude } from "../shell/altitude";
import { safeStorage } from "../../lib/safeStorage";

/**
 * What the user typed, kept across a reload (SPEC-050).
 *
 * Commissioning was a single in-memory `useState`, so a refresh, a crashed tab
 * or an accidental back-navigation lost everything the user had written. People
 * spend real effort on this prompt — it is the one place they describe a
 * decision that matters to them — and losing it is the kind of failure that
 * ends a session rather than costing a minute.
 */
export interface CommissionDraft {
  prompt: string;
  effort: EffortKey;
  /** What to hand back: a one-page answer, or the full brief. */
  shape: Altitude;
  /** Sit with the deliberation, or be pinged when it needs you. */
  presence: "watch" | "notify";
}

const STORAGE_KEY = "agentadvisor:commission-draft";

export const EMPTY_DRAFT: CommissionDraft = {
  prompt: "",
  effort: "standard",
  shape: "reasoning",
  presence: "watch",
};

export function readDraft(): CommissionDraft {
  const raw = safeStorage.get(STORAGE_KEY);
  if (!raw) return EMPTY_DRAFT;
  try {
    const parsed = JSON.parse(raw) as Partial<CommissionDraft>;
    return {
      prompt: typeof parsed.prompt === "string" ? parsed.prompt : "",
      effort: parsed.effort ?? EMPTY_DRAFT.effort,
      shape: parsed.shape === "answer" ? "answer" : "reasoning",
      presence: parsed.presence === "notify" ? "notify" : "watch",
    };
  } catch {
    // A corrupt or unavailable draft is an empty form, never a broken screen.
    return EMPTY_DRAFT;
  }
}

export function writeDraft(draft: CommissionDraft): void {
  safeStorage.set(STORAGE_KEY, JSON.stringify(draft));
}

/** Called once the case exists: the draft has served its purpose. */
export function clearDraft(): void {
  safeStorage.remove(STORAGE_KEY);
}
