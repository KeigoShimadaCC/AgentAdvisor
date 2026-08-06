import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { caseTitle } from "./title";
import { digestSince, digestLines, EMPTY_DIGEST } from "./digest";
import { AwayDigest } from "./AwayDigest";
import { noticeFor, notify, permissionState, requestPermissionOnRun, onFallbackNotice } from "./notify";
import { setPresence } from "../screens/shell/presence";
import type { CaseView } from "../generated/case_view";
import type { TranslatedEvent } from "../api/sse";

function view(overrides: Partial<CaseView> = {}): CaseView {
  return {
    case_id: "case-014-should-i-take-the-ser",
    decision_question: "Should I take the Series B term sheet?",
    phase: "investigation",
    stage: "investigation",
    is_terminal: false,
    needs_you: "none",
    ...overrides,
  } as CaseView;
}

let cursor = 0;
function event(type: string, payload: Record<string, unknown> = {}): TranslatedEvent {
  cursor += 1;
  return {
    event_type: type,
    message: type,
    technical: false,
    raw_payload: payload,
    line_cursor: cursor,
  };
}

beforeEach(() => {
  cursor = 0;
  window.localStorage.clear();
});

// ── The document title ───────────────────────────────────────────────────────

describe("the tab title", () => {
  it("says a case needs you, distinguishably, at a glance in a tab strip", () => {
    expect(caseTitle(view({ needs_you: "scope_checkpoint" }))).toBe(
      "● Needs you — Should I take the Series B term sheet?",
    );
  });

  it("names the phase while running", () => {
    expect(caseTitle(view())).toBe("Investigation — Should I take the Series B term sheet?");
  });

  it("marks a finished case done rather than leaving it looking live", () => {
    expect(caseTitle(view({ is_terminal: true, phase: "complete" }))).toBe(
      "✓ Should I take the Series B term sheet?",
    );
  });

  it("falls back to the case id only when there is no question yet", () => {
    expect(caseTitle(view({ decision_question: "" }))).toContain("case-014");
  });

  it("is the plain product name when there is no case", () => {
    expect(caseTitle(null)).toBe("AgentAdvisor");
  });

  it("prefers needs-you over terminal, because a gate is the actionable state", () => {
    expect(caseTitle(view({ is_terminal: true, needs_you: "delivery_checkpoint" }))).toContain(
      "Needs you",
    );
  });
});

// ── The away digest ──────────────────────────────────────────────────────────

describe("what happened while you were away", () => {
  const gap: TranslatedEvent[] = [
    event("evidence_batch_unpacked", { record_count: 9 }),
    event("assumption_batch_unpacked", { record_count: 2 }),
    event("objection_batch_unpacked", { record_count: 3 }),
    event("thesis_revision_recorded", { revision: 1, changed: true }),
    event("thesis_revision_recorded", { revision: 2, changed: false }),
    event("stage_completed", { stage: "investigation" }),
    event("gate_evaluated", { outcome: "pass" }),
    event("gate_evaluated", { outcome: "warn" }),
    event("stop_decision_evaluated", { outcome: "repair" }),
    event("review_evaluated", { outcome: "fail" }),
    event("framing_revision_requested", {}),
  ];

  it("counts the gap, and only the gap", () => {
    const digest = digestSince(gap, 0);
    expect(digest.evidence).toBe(9);
    expect(digest.assumptions).toBe(2);
    expect(digest.objections).toBe(3);
    expect(digest.gatesPassed).toBe(1);
    expect(digest.gatesFailed).toBe(1);
    expect(digest.repairRounds).toBe(1);
    expect(digest.resynthesisRounds).toBe(1);
    expect(digest.rescopes).toBe(1);
    expect(digest.stagesCompleted).toEqual(["investigation"]);
  });

  it("counts only a *changed* thesis, because reaffirming one is the case holding still", () => {
    expect(digestSince(gap, 0).thesisChanges).toBe(1);
  });

  it("treats the cursor as exclusive — the event you already saw is not news", () => {
    const digest = digestSince(gap, 1);
    expect(digest.evidence).toBe(0);
    expect(digest.assumptions).toBe(2);
  });

  it("is empty when the reader is already at the head", () => {
    expect(digestSince(gap, 99)).toEqual({ ...EMPTY_DIGEST, stagesCompleted: [] });
  });

  it("ignores an event type it has never seen rather than miscounting it", () => {
    const digest = digestSince([event("some_future_event", { record_count: 400 })], 0);
    expect(digest.events).toBe(1);
    expect(digest.evidence).toBe(0);
  });

  it("leads with what changes what the reader should believe", () => {
    const lines = digestLines(digestSince(gap, 0));
    // A thesis change and a failed check must not sit under "9 pieces of
    // evidence gathered" — the ordering is the design.
    expect(lines[0]).toMatch(/working view changed/i);
    expect(lines[1]).toMatch(/did not pass/i);
    expect(lines[lines.length - 1]).toMatch(/stage/i);
  });

  it("says nothing at all when nothing happened", () => {
    expect(digestLines(EMPTY_DIGEST)).toEqual([]);
  });
});

describe("the digest component", () => {
  it("renders nothing for an empty gap rather than 'no changes'", () => {
    const { container } = render(<AwayDigest events={[]} sinceCursor={0} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when there is no stored cursor to compare against", () => {
    const { container } = render(
      <AwayDigest events={[event("evidence_batch_unpacked", { record_count: 3 })]} sinceCursor={null} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("summarises a real gap and can be dismissed", async () => {
    render(
      <AwayDigest
        events={[
          event("evidence_batch_unpacked", { record_count: 4 }),
          event("thesis_revision_recorded", { changed: true }),
        ]}
        sinceCursor={0}
      />,
    );
    expect(screen.getByText(/working view changed once/i)).toBeInTheDocument();
    expect(screen.getByText(/4 pieces of evidence/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByText(/working view changed/i)).not.toBeInTheDocument();
  });
});

// ── Notifications ────────────────────────────────────────────────────────────

describe("what a case is worth notifying about", () => {
  it("routes a scope gate to the scope sheet and says it will not proceed", () => {
    const notice = noticeFor(view({ needs_you: "scope_checkpoint" }));
    expect(notice?.kind).toBe("needs_you");
    expect(notice?.href).toBe("/cases/case-014-should-i-take-the-ser/scope");
    expect(notice?.body).toMatch(/will not proceed/i);
  });

  it("routes a delivery gate to delivery", () => {
    expect(noticeFor(view({ needs_you: "delivery_checkpoint" }))?.href).toMatch(/\/delivery$/);
  });

  it("notifies about a failure even though it is not a gate", () => {
    expect(noticeFor(view({ stage: "failed" }))?.kind).toBe("failed");
  });

  it("has nothing to say about a case that is simply running", () => {
    expect(noticeFor(view())).toBeNull();
  });
});

describe("delivering a notice", () => {
  const original = (globalThis as { Notification?: unknown }).Notification;

  function stubNotification(permission: NotificationPermission) {
    const constructed: { title: string }[] = [];
    class FakeNotification {
      static permission: NotificationPermission = permission;
      static requestPermission = vi.fn(async () => permission);
      onclick: (() => void) | null = null;
      constructor(public title: string) {
        constructed.push({ title });
      }
    }
    (globalThis as { Notification?: unknown }).Notification = FakeNotification;
    return { constructed, FakeNotification };
  }

  afterEach(() => {
    (globalThis as { Notification?: unknown }).Notification = original;
  });

  it("sends nothing without granted permission, and falls back in-app instead", () => {
    stubNotification("denied");
    setPresence("notify");
    const seen: unknown[] = [];
    const off = onFallbackNotice((n) => seen.push(n));

    const result = notify({ kind: "ready", title: "t", body: "b", href: "/x" });
    expect(result).toBe("fallback");
    expect(seen).toHaveLength(1);
    off();
  });

  it("sends when permission is granted", () => {
    const { constructed } = stubNotification("granted");
    setPresence("notify");
    expect(notify({ kind: "ready", title: "Ready", body: "b", href: "/x" })).toBe("sent");
    expect(constructed).toEqual([{ title: "Ready" }]);
  });

  it("suppresses gate notices for a user who said they would watch", () => {
    // Notifying someone who is looking at the screen is telling them something
    // they can already see.
    const { constructed } = stubNotification("granted");
    setPresence("watch");
    expect(notify({ kind: "needs_you", title: "t", body: "b", href: "/x" })).toBe("suppressed");
    expect(constructed).toHaveLength(0);
  });

  it("still reports a failure to a watcher, because a stopped case is not visible progress", () => {
    const { constructed } = stubNotification("granted");
    setPresence("watch");
    expect(notify({ kind: "failed", title: "t", body: "b", href: "/x" })).toBe("sent");
    expect(constructed).toHaveLength(1);
  });

  it("asks for permission only when it has not been decided", async () => {
    const { FakeNotification } = stubNotification("default");
    await requestPermissionOnRun();
    expect(FakeNotification.requestPermission).toHaveBeenCalledTimes(1);

    const granted = stubNotification("granted");
    await requestPermissionOnRun();
    expect(granted.FakeNotification.requestPermission).not.toHaveBeenCalled();
  });

  it("reports an unsupported browser rather than throwing", async () => {
    (globalThis as { Notification?: unknown }).Notification = undefined;
    delete (window as unknown as Record<string, unknown>).Notification;
    expect(permissionState()).toBe("unsupported");
    await expect(requestPermissionOnRun()).resolves.toBe("unsupported");
  });
});
