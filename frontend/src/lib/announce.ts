/**
 * What a screen reader is told, and what it is spared (SPEC-055).
 *
 * Phase 9 turns a page-load-and-poll interface into one where content rewrites
 * itself for hours. That is exactly the situation `aria-live` exists for and
 * exactly the situation it is most often got wrong, because the obvious
 * implementation puts a live region on the narrator line — which then announces
 * the elapsed timer every single second and makes the page unusable.
 *
 * The rule, once, applied everywhere content updates without user action:
 *
 *  - **Transitions are announced.** A role starting, a loop entered, a stage
 *    completed, an action's outcome, a gate reached. These are the things a
 *    sighted user would notice by glancing at the screen.
 *  - **Heartbeats are not.** An elapsed counter, a progress tick, a spend
 *    figure. They carry no new fact; the transition they belong to was already
 *    announced.
 *  - **Only a gate is assertive.** Assertive interrupts whatever the user is
 *    reading, which is justified exactly once: the case has stopped and will
 *    not continue without them. Everything else is polite.
 */

export type Politeness = "polite" | "assertive" | "off";

/** Every live region in the app, with its politeness and the reason for it. */
export const ANNOUNCEMENTS: Record<string, { politeness: Politeness; because: string }> = {
  "narrator.line": {
    politeness: "polite",
    because: "A transition — who is working, and on what.",
  },
  "narrator.elapsed": {
    politeness: "off",
    because: "A heartbeat. Announcing a per-second counter makes the page unusable.",
  },
  "narrator.counters": {
    politeness: "off",
    because: "Running totals restate what the line already said.",
  },
  "narrator.announcement": {
    politeness: "polite",
    because: "A loop entered or a review failed: new facts about the argument.",
  },
  "chrome.connection": {
    politeness: "polite",
    because: "The stream's health changed; the brief may no longer be current.",
  },
  "chrome.spend": {
    politeness: "off",
    because: "A heartbeat. Spend rises continuously and carries no transition.",
  },
  "toast": {
    politeness: "polite",
    because: "The outcome of something the user just did.",
  },
  "digest": {
    politeness: "polite",
    because: "What happened while they were away, shown once on arrival.",
  },
  "gate": {
    politeness: "assertive",
    because:
      "The case has stopped and will not continue without a human. This is the one interruption worth making.",
  },
};

export function politenessOf(region: keyof typeof ANNOUNCEMENTS | string): Politeness {
  return ANNOUNCEMENTS[region]?.politeness ?? "polite";
}

/**
 * The props a live region should carry. `off` means no live region at all.
 *
 * `withRole` is false for anything with a load-bearing implicit role — an
 * `<li>`, a `<td>`. `role="status"` on a list item replaces `listitem` and
 * breaks the list for a screen reader, which is a worse accessibility outcome
 * than the one the live region was added to achieve. `aria-live` alone is
 * enough: the role only adds an implicit `aria-live` that is being set anyway.
 */
export function liveRegionProps(
  region: string,
  { withRole = true }: { withRole?: boolean } = {},
): {
  "aria-live"?: Politeness;
  "aria-hidden"?: boolean;
  role?: string;
} {
  const politeness = politenessOf(region);
  if (politeness === "off") return { "aria-hidden": true };
  if (!withRole) return { "aria-live": politeness };
  return {
    "aria-live": politeness,
    role: politeness === "assertive" ? "alert" : "status",
  };
}
