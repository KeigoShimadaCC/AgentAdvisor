/**
 * Storage that cannot break a render (SPEC-055).
 *
 * The app had zero `localStorage` usage before this phase and now has seven
 * consumers: the stream cursor, reading altitude, the commission draft, the
 * watch-or-notify preference, reactions, theme, and whether the tour has been
 * seen. Every one of them wrote its own try/catch, which is six chances to get
 * it wrong and no shared answer to the question that actually matters — what
 * should happen when storage is not there at all.
 *
 * Three properties, in order of importance:
 *
 *  1. **It never throws into a render path.** `localStorage` throws in Safari
 *     private mode, when a policy disables it, and when the quota is exhausted —
 *     and a throw inside a lazy `useState` initialiser takes down the screen.
 *  2. **It degrades to memory for the session**, so a feature keeps working
 *     within the tab even when nothing can be persisted. A lost preference is a
 *     downgrade; a broken altitude control is a failure.
 *  3. **Availability is detected once**, not per call. A try/catch per keystroke
 *     on the commission draft is both slow and pointless: storage does not come
 *     back mid-session.
 */

type Backing = "local" | "memory";

const memory = new Map<string, string>();
let backing: Backing | null = null;

/** Feature-detect by round-tripping, because presence of the object is not enough. */
function detect(): Backing {
  try {
    const probe = "agentadvisor:__probe__";
    window.localStorage.setItem(probe, "1");
    window.localStorage.removeItem(probe);
    return "local";
  } catch {
    // Private mode, a policy, or an exhausted quota. All the same to us.
    return "memory";
  }
}

function resolve(): Backing {
  if (backing === null) backing = detect();
  return backing;
}

export const safeStorage = {
  get(key: string): string | null {
    if (resolve() === "memory") return memory.get(key) ?? null;
    try {
      return window.localStorage.getItem(key);
    } catch {
      // Storage was available at detection and failed now: fall back for the
      // rest of the session rather than failing every subsequent read.
      backing = "memory";
      return memory.get(key) ?? null;
    }
  },

  set(key: string, value: string): void {
    if (resolve() === "local") {
      try {
        window.localStorage.setItem(key, value);
        return;
      } catch {
        // Most often a quota exhausted mid-session by another origin's data.
        backing = "memory";
      }
    }
    memory.set(key, value);
  },

  remove(key: string): void {
    memory.delete(key);
    if (resolve() === "local") {
      try {
        window.localStorage.removeItem(key);
      } catch {
        backing = "memory";
      }
    }
  },

  /** Whether anything written will survive a reload. Surfaced in Settings. */
  isPersistent(): boolean {
    return resolve() === "local";
  },
};

/** Test seam: forget the detection so a test can stub storage and re-detect. */
export function resetStorageDetection(): void {
  backing = null;
  memory.clear();
}
