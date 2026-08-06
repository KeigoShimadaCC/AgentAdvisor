import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AssumptionsRoom } from "./AssumptionsRoom";
import { makeAssumptionsFixture } from "../fixtures";
import type { CaseView } from "../../../generated/case_view";

const { mocks } = vi.hoisted(() => ({
  mocks: {
    getCaseView: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
  },
}));

vi.mock("../../../api/client", () => ({
  api: { getCaseView: mocks.getCaseView },
}));

vi.mock("../../../api/sse", () => ({
  readStoredCursor: () => 0,
  SSEClient: class {
    connect() { mocks.connect(); }
    disconnect() { mocks.disconnect(); }
  },
}));

function renderRoom(fixture: CaseView) {
  mocks.getCaseView.mockResolvedValue(fixture);
  return render(
    <MemoryRouter initialEntries={["/cases/case-1/rooms/assumptions"]}>
      <Routes>
        <Route path="/cases/:caseId/rooms/assumptions" element={<AssumptionsRoom />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Assumptions room", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the for/against split bar with both counts (never netted)", async () => {
    renderRoom(makeAssumptionsFixture());
    // A-1 has 1 for, 2 against.
    expect(await screen.findByText("Interest rates stay flat over the next year.")).toBeInTheDocument();
    const a1Row = screen.getByText("Interest rates stay flat over the next year.").closest(".assumption-row")!;
    expect(a1Row).toHaveTextContent("1 for");
    expect(a1Row).toHaveTextContent("2 against");
  });

  it("renders the load-bearing callout for high-materiality low-confidence assumptions", async () => {
    renderRoom(makeAssumptionsFixture());
    expect(await screen.findByText("Load-bearing assumption")).toBeInTheDocument();
    const callout = screen.getByText("Load-bearing assumption").closest(".load-bearing-callout") as HTMLElement;
    expect(within(callout).getByText("A-1")).toBeInTheDocument();
  });

  it("renders the probability phrase for an estimated assumption", async () => {
    renderRoom(makeAssumptionsFixture());
    await screen.findByText("Interest rates stay flat over the next year.");
    // A-1 estimate 0.4 -> "Unlikely" phrase + 40%.
    expect(screen.getByText("Unlikely")).toBeInTheDocument();
    expect(screen.getByText("40%")).toBeInTheDocument();
  });

  it("labels a skipped question (no evidence for or against, unresolved)", async () => {
    renderRoom(makeAssumptionsFixture());
    await screen.findByText("Interest rates stay flat over the next year.");
    expect(screen.getByText(/Skipped question/)).toBeInTheDocument();
  });
});
