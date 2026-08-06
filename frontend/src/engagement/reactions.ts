/**
 * Marking things as you read (SPEC-051).
 *
 * The problem this solves is passive time. A case runs for hours, the user
 * reads assumptions and objections as they land, forms a view — and has nowhere
 * to put it until the delivery gate, by which point the specific thing that
 * bothered them at minute forty is gone. Three hours of attention produce a
 * blank revision box.
 *
 * Deliberately client-side and terminal at the delivery gate. Writing these into
 * the case as they occur would hand the user a mid-run write path into a
 * directory the single-writer discipline reserves for the worker, and phase 8's
 * SPEC-043 already provides the sanctioned route for user input. Pre-filling the
 * revision note routes the same intent through the approval mechanism that
 * already exists.
 */

export type ReactionKind = "looks_wrong" | "matters";

export interface Reaction {
  /** The artifact this is about: an assumption id, an objection id. */
  targetId: string;
  /** What the target is, so the pre-filled note can name it. */
  targetKind: "assumption" | "objection";
  kind: ReactionKind;
  /** The claim text, captured so the note can quote it without a re-fetch. */
  label: string;
}

export const REACTION_LABELS: Record<ReactionKind, string> = {
  looks_wrong: "This looks wrong",
  matters: "This one matters",
};

function storageKey(caseId: string): string {
  return `agentadvisor:reactions:${caseId}`;
}

export function readReactions(caseId: string): Reaction[] {
  try {
    const raw = window.localStorage.getItem(storageKey(caseId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as Reaction[]) : [];
  } catch {
    // A corrupt store is no reactions, never a broken screen.
    return [];
  }
}

function write(caseId: string, reactions: Reaction[]): void {
  try {
    window.localStorage.setItem(storageKey(caseId), JSON.stringify(reactions));
  } catch {
    /* see readReactions */
  }
}

/** Toggle a reaction on a target. Returns the new list. */
export function toggleReaction(caseId: string, reaction: Reaction): Reaction[] {
  const current = readReactions(caseId);
  const existing = current.findIndex(
    (r) => r.targetId === reaction.targetId && r.kind === reaction.kind,
  );
  const next =
    existing >= 0
      ? current.filter((_, i) => i !== existing)
      : [...current.filter((r) => r.targetId !== reaction.targetId), reaction];
  write(caseId, next);
  return next;
}

export function hasReaction(reactions: Reaction[], targetId: string, kind: ReactionKind): boolean {
  return reactions.some((r) => r.targetId === targetId && r.kind === kind);
}

export function clearReactions(caseId: string): void {
  try {
    window.localStorage.removeItem(storageKey(caseId));
  } catch {
    /* see readReactions */
  }
}

/**
 * The revision note a reader's marks add up to.
 *
 * Written as the user's own words about specific records, not as a list of
 * ids — the note goes to a synthesizer that needs to know what to change, and
 * "A-003" is not that. Returns an empty string when nothing was marked, so the
 * box stays empty rather than being pre-filled with a heading and nothing else.
 */
export function revisionNoteFrom(reactions: Reaction[]): string {
  if (reactions.length === 0) return "";

  const wrong = reactions.filter((r) => r.kind === "looks_wrong");
  const matters = reactions.filter((r) => r.kind === "matters");
  const parts: string[] = [];

  if (wrong.length > 0) {
    parts.push(
      "These look wrong to me:\n" +
        wrong.map((r) => `- ${r.targetKind} ${r.targetId}: ${r.label}`).join("\n"),
    );
  }
  if (matters.length > 0) {
    parts.push(
      "These matter more than the brief gives them:\n" +
        matters.map((r) => `- ${r.targetKind} ${r.targetId}: ${r.label}`).join("\n"),
    );
  }
  return parts.join("\n\n");
}
