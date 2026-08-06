import { getPresence } from "../screens/shell/presence";

/**
 * Telling the user to come back (SPEC-051).
 *
 * SPEC-035 scoped the Notification API and never built it, so a case that
 * parked at a gate waited silently for as long as the user happened to be away.
 *
 * Three rules, all of them about not being a nuisance:
 *
 *  1. **Permission is requested when the first case starts running**, never on
 *     load. An unexplained permission dialog on first visit is the most common
 *     way this feature gets refused permanently, and a refusal is not
 *     recoverable from inside the page.
 *  2. **The watch preference suppresses gate notifications.** Someone who said
 *     "I'll watch" is looking at the screen; notifying them is telling them
 *     something they can already see.
 *  3. **A denied permission falls back in-app** rather than failing silently.
 */

export type NotificationClass = "needs_you" | "ready" | "failed";

export interface PendingNotice {
  kind: NotificationClass;
  title: string;
  body: string;
  href: string;
}

type Listener = (notice: PendingNotice) => void;

const listeners = new Set<Listener>();

/** In-app fallback subscribers — the banner SPEC-051 renders. */
export function onFallbackNotice(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function supported(): boolean {
  return typeof window !== "undefined" && "Notification" in window;
}

export function permissionState(): NotificationPermission | "unsupported" {
  if (!supported()) return "unsupported";
  return Notification.permission;
}

/**
 * Ask, once, at the moment a case starts running.
 *
 * Returns the resulting permission so a caller can decide what to render. Never
 * throws: a browser that rejects the call is a browser without notifications,
 * which is a supported configuration.
 */
export async function requestPermissionOnRun(): Promise<NotificationPermission | "unsupported"> {
  if (!supported()) return "unsupported";
  if (Notification.permission !== "default") return Notification.permission;
  try {
    return await Notification.requestPermission();
  } catch {
    return "denied";
  }
}

/**
 * Deliver a notice, or fall back in-app.
 *
 * Returns what actually happened, so tests assert on the decision rather than
 * on a side effect that may not have fired.
 */
export function notify(notice: PendingNotice): "sent" | "suppressed" | "fallback" {
  // Rule 2: a watcher is already looking.
  if (notice.kind !== "failed" && getPresence() === "watch") return "suppressed";

  if (supported() && Notification.permission === "granted") {
    try {
      const n = new Notification(notice.title, { body: notice.body, tag: notice.href });
      n.onclick = () => {
        window.focus();
        window.location.assign(notice.href);
      };
      return "sent";
    } catch {
      // A browser that accepts the permission and then throws on construction
      // still owes the user the message.
    }
  }

  for (const listener of listeners) listener(notice);
  return "fallback";
}

/** The notice for a case's current state, or null when there is nothing to say. */
export function noticeFor(
  view: { case_id: string; decision_question?: string; needs_you: string; stage: string },
): PendingNotice | null {
  const subject = view.decision_question || view.case_id;
  if (view.stage === "failed") {
    return {
      kind: "failed",
      title: "A case stopped before finishing",
      body: subject,
      href: `/cases/${view.case_id}`,
    };
  }
  if (view.needs_you === "scope_checkpoint") {
    return {
      kind: "needs_you",
      title: "Your scope review is needed",
      body: `${subject} — it will not proceed until you sign.`,
      href: `/cases/${view.case_id}/scope`,
    };
  }
  if (view.needs_you === "delivery_checkpoint") {
    return {
      kind: "ready",
      title: "A recommendation is ready",
      body: subject,
      href: `/cases/${view.case_id}/delivery`,
    };
  }
  return null;
}
