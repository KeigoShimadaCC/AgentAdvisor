import { safeStorage } from "../../lib/safeStorage";
/**
 * Whether the tour has been seen (SPEC-052).
 *
 * Stored rather than inferred from "has any case", because a user who deleted
 * their cases has still seen the tour and should not be shown it again.
 */
const STORAGE_KEY = "agentadvisor:onboarded";

export function hasOnboarded(): boolean {
  // Storage unavailable means we cannot remember, and showing the tour to
  // someone who has seen it is a smaller harm than never showing it.
  return safeStorage.get(STORAGE_KEY) === "yes";
}

export function markOnboarded(): void {
  safeStorage.set(STORAGE_KEY, "yes");
}

export function restartOnboarding(): void {
  safeStorage.remove(STORAGE_KEY);
}
