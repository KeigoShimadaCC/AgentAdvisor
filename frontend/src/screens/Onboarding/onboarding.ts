/**
 * Whether the tour has been seen (SPEC-052).
 *
 * Stored rather than inferred from "has any case", because a user who deleted
 * their cases has still seen the tour and should not be shown it again.
 */
const STORAGE_KEY = "agentadvisor:onboarded";

export function hasOnboarded(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "yes";
  } catch {
    // Storage unavailable means we cannot remember, and showing the tour to
    // someone who has seen it is a smaller harm than never showing it.
    return false;
  }
}

export function markOnboarded(): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, "yes");
  } catch {
    /* see hasOnboarded */
  }
}

export function restartOnboarding(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* see hasOnboarded */
  }
}
