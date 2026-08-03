import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { MethodRoom } from "./MethodRoom";
import { makeMethodFixture, makeEventsFixture } from "../fixtures";
import type { CaseView } from "../../../generated/case_view";
import type { TranslatedEvent } from "../../../api/sse";

const { mocks, state } = vi.hoisted(() => ({
  mocks: {
    getCaseView: vi.fn(),
    getFile: vi.fn(),
  },
  state: { events: [] as TranslatedEvent[] },
}));

vi.mock("../../../api/client", () => ({
  api: { getCaseView: mocks.getCaseView, getFile: mocks.getFile },
}));

vi.mock("../../../api/sse", () => ({
  SSEClient: class {
    private opts: { onEvent: (e: TranslatedEvent) => void };
    constructor(_caseId: string, opts: { onEvent: (e: TranslatedEvent) => void }) {
      this.opts = opts;
    }
    connect() {
      for (const e of state.events) this.opts.onEvent(e);
    }
    disconnect() {}
  },
}));

function renderRoom(fixture: CaseView, events: TranslatedEvent[] = makeEventsFixture()) {
  state.events = events;
  mocks.getCaseView.mockResolvedValue(fixture);
  return render(
    <MemoryRouter initialEntries={["/cases/case-1/rooms/method"]}>
      <Routes>
        <Route path="/cases/:caseId/rooms/method" element={<MethodRoom />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Method room", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getFile.mockResolvedValue("raw content");
  });

  it("renders the per-role invocation counts and token sums", async () => {
    renderRoom(makeMethodFixture());
    expect(await screen.findByText("Researcher")).toBeInTheDocument();
    // Analyst row: 3 attempts, total tokens 12000 — scoped to the table body to
    // avoid colliding with the footer grand total.
    const analystRow = screen.getByRole("row", { name: /Analyst/ });
    expect(within(analystRow).getByText("12000")).toBeInTheDocument();
    // Footer grand total tokens (20000 appears once, in the footer).
    expect(screen.getByText("20000")).toBeInTheDocument();
  });

  it("filters the audit event log to progress-only (non-technical)", async () => {
    renderRoom(makeMethodFixture());
    // Initially all events show: a technical one ("researcher is running…") and a user one.
    await screen.findByText("researcher is running…");
    expect(screen.getByText(/evidence record\(s\) gathered/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Progress only" }));
    // Technical event hidden.
    expect(screen.queryByText("researcher is running…")).not.toBeInTheDocument();
    expect(screen.getByText(/evidence record\(s\) gathered/)).toBeInTheDocument();
  });
});
