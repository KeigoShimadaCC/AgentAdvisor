import { safeStorage } from "../../lib/safeStorage";
/**
 * Watch or be pinged (SPEC-050).
 *
 * Captured at commissioning and stored per user, not per case, for the same
 * reason altitude is: this is a fact about how someone wants to work, not about
 * the decision. SPEC-051 consumes it to decide whether a case that reaches a
 * checkpoint notifies or waits quietly.
 *
 * Nothing is written into the case directory. A preference that changed the
 * record would mean two users could commission the same decision and get two
 * different artifacts.
 */
export type Presence = "watch" | "notify";

const STORAGE_KEY = "agentadvisor:presence";
const DEFAULT_PRESENCE: Presence = "watch";

export function getPresence(): Presence {
  return safeStorage.get(STORAGE_KEY) === "notify" ? "notify" : DEFAULT_PRESENCE;
}

export function setPresence(presence: Presence): void {
  safeStorage.set(STORAGE_KEY, presence);
}
