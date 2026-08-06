import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { useState } from "react";
import { AppShell } from "./AppShell";
import { CaseChrome } from "./CaseChrome";
import { CaseCrumb } from "./CaseCrumb";
import { Skeleton } from "../shared/Skeleton";
import { ToastHost, useToast } from "../shared/Toast";
import { readAltitude, writeAltitude, showsAt, type Altitude } from "./altitude";
import type { CaseView } from "../../generated/case_view";

function view(overrides: Partial<CaseView> = {}): CaseView {
  return {
    case_id: "case-1",
    decision_question: "Should we move the warehouse?",
    phase: "investigation",
    stage: "investigation",
    is_terminal: false,
    needs_you: "none",
    ...overrides,
  } as CaseView;
}

beforeEach(() => {
  window.localStorage.clear();
});

describe("altitude storage", () => {
  it("defaults to reasoning, the altitude that shows the argument", () => {
    expect(readAltitude()).toBe("reasoning");
  });

  it("ignores a stored value that is not an altitude", () => {
    window.localStorage.setItem("agentadvisor:altitude", "wherever");
    expect(readAltitude()).toBe("reasoning");
  });

  it("round-trips a real altitude", () => {
    writeAltitude("method");
    expect(readAltitude()).toBe("method");
  });

  it("falls back rather than throwing when storage is unavailable", () => {
    const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    expect(readAltitude()).toBe("reasoning");
    getItem.mockRestore();
  });

  it("nests the altitudes: answer ⊂ reasoning ⊂ method", () => {
    const pairs: [Altitude, Altitude, boolean][] = [
      ["answer", "answer", true],
      ["answer", "reasoning", false],
      ["answer", "method", false],
      ["reasoning", "answer", true],
      ["reasoning", "reasoning", true],
      ["reasoning", "method", false],
      ["method", "method", true],
      ["method", "answer", true],
    ];
    for (const [at, needed, expected] of pairs) {
      expect(showsAt(at, needed)).toBe(expected);
    }
  });
});

describe("case chrome", () => {
  function renderChrome(v: CaseView, connection?: "connected" | "reconnecting" | "stale") {
    const onChange = vi.fn();
    render(
      <MemoryRouter>
        <CaseChrome view={v} connection={connection} altitude="reasoning" onAltitudeChange={onChange} />
      </MemoryRouter>,
    );
    return onChange;
  }

  it("says the stream is stale, because a plausible brief that stopped updating is the dangerous case", () => {
    renderChrome(view(), "stale");
    expect(screen.getByText(/may be out of date/i)).toBeInTheDocument();
  });

  it("stays quiet while connected — a healthy stream is not news", () => {
    renderChrome(view(), "connected");
    expect(screen.queryByText(/out of date/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Reconnecting/i)).not.toBeInTheDocument();
  });

  it("puts spend in the frame rather than inside the Method room", () => {
    renderChrome(
      view({ effort: { wall_clock_s: 5400, invocation_attempts: 31, total_tokens: 1_540_000 } } as Partial<CaseView>),
    );
    const spend = screen.getByLabelText("Effort so far");
    expect(spend).toHaveTextContent("1h 30m");
    expect(spend).toHaveTextContent("31 calls");
    expect(spend).toHaveTextContent("1540k tokens");
  });

  it("omits spend measures it does not have instead of printing zeroes", () => {
    renderChrome(view());
    expect(screen.getByLabelText("Effort so far")).toBeEmptyDOMElement();
  });

  it("reports the altitude the user picked", async () => {
    const onChange = renderChrome(view());
    await userEvent.click(screen.getByRole("button", { name: "Method" }));
    expect(onChange).toHaveBeenCalledWith("method");
  });

  it("marks the current altitude pressed, not merely styled", () => {
    renderChrome(view());
    expect(screen.getByRole("button", { name: "Reasoning" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Answer" })).toHaveAttribute("aria-pressed", "false");
  });
});

describe("the shell's panel", () => {
  function Harness() {
    const [open, setOpen] = useState(false);
    return (
      <AppShell
        panel={open ? <p>Panel body</p> : undefined}
        panelTitle="Sources"
        onPanelClose={() => setOpen(false)}
      >
        <button type="button" onClick={() => setOpen(true)}>
          Open
        </button>
      </AppShell>
    );
  }

  it("returns focus to whatever opened it, so a keyboard user is not dropped at the top", async () => {
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "Open" });
    opener.focus();
    await userEvent.click(opener);
    expect(screen.getByRole("complementary", { name: "Sources" })).toHaveFocus();

    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(opener).toHaveFocus();
  });

  it("closes on Escape", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(screen.getByText("Panel body")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByText("Panel body")).not.toBeInTheDocument();
  });

  it("keeps the content column mounted while the panel is open", async () => {
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "Open" });
    await userEvent.click(opener);
    // Same node, not a re-render of a replaced page — this is what preserves
    // the reader's scroll position.
    expect(screen.getByRole("button", { name: "Open" })).toBe(opener);
  });
});

describe("skeletons", () => {
  it("announces itself and imitates the shape of what is coming", () => {
    const { container } = render(<Skeleton shape="list" label="Loading your cases" />);
    expect(screen.getByRole("status", { name: "Loading your cases" })).toBeInTheDocument();
    expect(container.querySelector(".skeleton-list")).not.toBeNull();
    expect(container.querySelectorAll(".skeleton-block")).toHaveLength(5);
  });

  it("hides its decorative blocks from the screen reader", () => {
    const { container } = render(<Skeleton />);
    for (const block of container.querySelectorAll(".skeleton-block")) {
      expect(block).toHaveAttribute("aria-hidden", "true");
    }
  });
});

describe("toasts", () => {
  function Harness() {
    const toast = useToast();
    return (
      <button type="button" onClick={() => toast.show("Scope signed.", "success")}>
        Sign
      </button>
    );
  }

  it("names what happened, in a polite live region", async () => {
    render(
      <ToastHost>
        <Harness />
      </ToastHost>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Sign" }));
    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveTextContent("Scope signed.");
  });

  it("clears itself so the surface does not accumulate history", () => {
    vi.useFakeTimers();
    try {
      render(
        <ToastHost>
          <Harness />
        </ToastHost>,
      );
      // fireEvent, not userEvent: userEvent's own timers deadlock against the
      // fake clock this test needs to advance.
      fireEvent.click(screen.getByRole("button", { name: "Sign" }));
      expect(screen.getByText("Scope signed.")).toBeInTheDocument();
      act(() => {
        vi.advanceTimersByTime(5100);
      });
      expect(screen.queryByText("Scope signed.")).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("breadcrumb chrome", () => {
  it("offers the way out at the top, where a user looks for it", () => {
    render(
      <MemoryRouter>
        <CaseCrumb caseId="case-7" />
      </MemoryRouter>,
    );
    const crumb = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(crumb).toContainElement(screen.getByRole("link", { name: "All cases" }));
    expect(screen.getByRole("link", { name: "Back to the case" })).toHaveAttribute(
      "href",
      "/cases/case-7",
    );
  });

  it("drops the case link when there is no case to go back to", () => {
    render(
      <MemoryRouter>
        <CaseCrumb />
      </MemoryRouter>,
    );
    expect(screen.getAllByRole("link")).toHaveLength(1);
  });
});
