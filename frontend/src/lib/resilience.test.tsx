import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { safeStorage, resetStorageDetection } from "./safeStorage";
import { ANNOUNCEMENTS, politenessOf, liveRegionProps } from "./announce";
import { Failure, classify } from "../screens/shared/Failure";
import { readAltitude, writeAltitude } from "../screens/shell/altitude";
import { readTheme, writeTheme } from "../theme";
import { getPresence, setPresence } from "../screens/shell/presence";
import { readDraft, writeDraft, EMPTY_DRAFT } from "../screens/NewDecision/commissionDraft";
import { readReactions, toggleReaction } from "../engagement/reactions";
import { hasOnboarded, markOnboarded } from "../screens/Onboarding/onboarding";
import { readStoredCursor, hasStoredCursor } from "../api/sse";
import type { ErrorResponse } from "../api/client";

// ── Storage that is not there ────────────────────────────────────────────────

describe("storage that throws on every call", () => {
  let spies: ReturnType<typeof vi.spyOn>[] = [];

  beforeEach(() => {
    resetStorageDetection();
    // Private mode, a policy, an exhausted quota — all of them look like this.
    spies = [
      vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
        throw new DOMException("denied", "SecurityError");
      }),
      vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
        throw new DOMException("denied", "SecurityError");
      }),
      vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
        throw new DOMException("denied", "SecurityError");
      }),
    ];
  });

  afterEach(() => {
    for (const spy of spies) spy.mockRestore();
    resetStorageDetection();
  });

  it("never throws, from any entry point", () => {
    expect(() => safeStorage.get("k")).not.toThrow();
    expect(() => safeStorage.set("k", "v")).not.toThrow();
    expect(() => safeStorage.remove("k")).not.toThrow();
    expect(safeStorage.isPersistent()).toBe(false);
  });

  it("still works for the session, in memory", () => {
    // A lost preference is a downgrade; a broken control is a failure.
    safeStorage.set("k", "v");
    expect(safeStorage.get("k")).toBe("v");
    safeStorage.remove("k");
    expect(safeStorage.get("k")).toBeNull();
  });

  it("keeps all seven consumers functional", () => {
    // Each of these is a lazy `useState` initialiser somewhere; a throw here
    // takes down the screen rather than losing a preference.
    writeAltitude("method");
    expect(readAltitude()).toBe("method");

    writeTheme("dark");
    expect(readTheme()).toBe("dark");

    setPresence("notify");
    expect(getPresence()).toBe("notify");

    writeDraft({ ...EMPTY_DRAFT, prompt: "a decision" });
    expect(readDraft().prompt).toBe("a decision");

    toggleReaction("case-1", {
      targetId: "A-1",
      targetKind: "assumption",
      kind: "looks_wrong",
      label: "claim",
    });
    expect(readReactions("case-1")).toHaveLength(1);

    markOnboarded();
    expect(hasOnboarded()).toBe(true);

    expect(readStoredCursor("case-1")).toBe(0);
    expect(hasStoredCursor("case-1")).toBe(false);
  });

  it("detects once rather than throwing on every keystroke", () => {
    const getItem = spies[0];
    safeStorage.get("a");
    const afterFirst = getItem.mock.calls.length;
    safeStorage.get("b");
    safeStorage.get("c");
    // The probe uses setItem; getItem is not called again once memory-backed.
    expect(getItem.mock.calls.length).toBe(afterFirst);
  });
});

describe("storage that works", () => {
  beforeEach(() => {
    resetStorageDetection();
    window.localStorage.clear();
  });

  it("persists, and says so", () => {
    safeStorage.set("agentadvisor:probe", "kept");
    expect(window.localStorage.getItem("agentadvisor:probe")).toBe("kept");
    expect(safeStorage.isPersistent()).toBe(true);
  });

  it("falls back for the rest of the session when a write fails mid-run", () => {
    // A quota exhausted by another origin's data is the common case.
    expect(safeStorage.isPersistent()).toBe(true);
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("quota", "QuotaExceededError");
    });
    safeStorage.set("k", "v");
    setItem.mockRestore();

    expect(safeStorage.get("k")).toBe("v");
    expect(safeStorage.isPersistent()).toBe(false);
  });
});

// ── The announcement policy ──────────────────────────────────────────────────

describe("what a screen reader is told", () => {
  it("announces transitions and stays silent on heartbeats", () => {
    // The trap this policy exists to avoid: a live region on the narrator line
    // that reads the elapsed timer aloud every second.
    expect(politenessOf("narrator.line")).toBe("polite");
    expect(politenessOf("narrator.elapsed")).toBe("off");
    expect(politenessOf("chrome.spend")).toBe("off");
    expect(politenessOf("narrator.announcement")).toBe("polite");
  });

  it("interrupts for a gate and nothing else", () => {
    // Assertive cuts across whatever the user is reading. That is justified
    // exactly once: the case has stopped and will not continue without them.
    const assertive = Object.entries(ANNOUNCEMENTS)
      .filter(([, value]) => value.politeness === "assertive")
      .map(([key]) => key);
    expect(assertive).toEqual(["gate"]);
  });

  it("gives every region a reason, so the policy cannot be extended thoughtlessly", () => {
    for (const [region, value] of Object.entries(ANNOUNCEMENTS)) {
      expect(value.because, `${region} has no stated reason`).not.toBe("");
    }
  });

  it("omits the role where an implicit one is load-bearing", () => {
    // `role="status"` on an <li> replaces `listitem` and breaks the list — a
    // worse accessibility outcome than the one the live region was added for.
    // Caught by axe on six routes at once; asserted here so it stays caught.
    expect(liveRegionProps("narrator.announcement", { withRole: false })).toEqual({
      "aria-live": "polite",
    });
    expect(liveRegionProps("gate", { withRole: false })).toEqual({ "aria-live": "assertive" });
  });

  it("turns 'off' into no live region at all, not a silent one", () => {
    expect(liveRegionProps("narrator.elapsed")).toEqual({ "aria-hidden": true });
    expect(liveRegionProps("narrator.line")).toEqual({ "aria-live": "polite", role: "status" });
    expect(liveRegionProps("gate")).toEqual({ "aria-live": "assertive", role: "alert" });
  });
});

// ── Failure taxonomy ─────────────────────────────────────────────────────────

describe("telling failures apart", () => {
  it.each([
    [{ error: "service_unavailable", detail: "", status: 0 }, "unavailable"],
    [{ error: "not_found", detail: "", status: 404 }, "not_found"],
    [{ error: "locked", detail: "", status: 409 }, "locked"],
    [{ error: "invalid", detail: "", status: 422 }, "invalid"],
    [{ error: "boom", detail: "", status: 500 }, "unknown"],
  ])("classifies %o", (error, expected) => {
    expect(classify(error as ErrorResponse)).toBe(expected);
  });

  function renderFailure(error: ErrorResponse, onRetry?: () => void) {
    return render(
      <MemoryRouter>
        <Failure error={error} onRetry={onRetry} />
      </MemoryRouter>,
    );
  }

  it("says the service is not running, and that nothing was lost", () => {
    // The reassurance is load-bearing: a user seeing a blank app assumes their
    // three-hour case is gone. Cases live on disk.
    renderFailure({ error: "service_unavailable", detail: "connection refused", status: 0 });
    expect(screen.getByText("The service is not running")).toBeInTheDocument();
    expect(screen.getByText(/Nothing was lost/)).toBeInTheDocument();
  });

  it("names the stage a locked case is in, so the wait is legible", () => {
    renderFailure({
      error: "locked",
      detail: "held by a writer",
      status: 409,
      case_stage: "investigation",
    });
    expect(screen.getByText(/Investigating/)).toBeInTheDocument();
  });

  it("keeps the service's own words for whoever has to help", () => {
    renderFailure({ error: "boom", detail: "IntegrityError at line 40", status: 500 });
    expect(screen.getByText("IntegrityError at line 40")).toBeInTheDocument();
  });

  it("offers retry without a reload when the caller can retry", () => {
    const retry = vi.fn();
    renderFailure({ error: "service_unavailable", detail: "", status: 0 }, retry);
    screen.getByRole("button", { name: "Try again" }).click();
    expect(retry).toHaveBeenCalled();
  });

  it("is an alert, because it replaced the whole screen", () => {
    renderFailure({ error: "not_found", detail: "", status: 404 });
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
