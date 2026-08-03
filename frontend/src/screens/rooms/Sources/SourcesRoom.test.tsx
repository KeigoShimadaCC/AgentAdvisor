import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { SourcesRoom } from "./SourcesRoom";
import { makeSourcesFixture } from "../fixtures";
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
  SSEClient: class {
    connect() { mocks.connect(); }
    disconnect() { mocks.disconnect(); }
  },
}));

function renderRoom(fixture: CaseView) {
  mocks.getCaseView.mockResolvedValue(fixture);
  return render(
    <MemoryRouter initialEntries={["/cases/case-1/rooms/sources"]}>
      <Routes>
        <Route path="/cases/:caseId/rooms/sources" element={<SourcesRoom />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Sources room", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the corpus header values from the fixture", async () => {
    renderRoom(makeSourcesFixture());
    // authority words for 0.62 -> "Solid, a mix of primary and reputable sources"
    expect(await screen.findByText(/Solid, a mix/)).toBeInTheDocument();
    // origins count
    expect(screen.getByText("4")).toBeInTheDocument();
    // concentration warning (55% > 40%)
    expect(screen.getByText(/55% of the corpus/)).toBeInTheDocument();
  });

  it("renders an honest-empty state when there are no sources", async () => {
    const empty = makeSourcesFixture();
    empty.rooms!.sources!.sources = [];
    renderRoom(empty);
    expect(await screen.findByText(/not yet — evidence has not been gathered/)).toBeInTheDocument();
  });

  it("shows a source card with its limitation line unexpanded for a flagged record", async () => {
    renderRoom(makeSourcesFixture());
    expect(await screen.findByText("Analyst note predicts margin pressure.")).toBeInTheDocument();
    // The flagged record E-2 has the incentive_conflict flag rendered.
    expect(screen.getByText("Incentive conflict")).toBeInTheDocument();
  });

  it("filters sources by reliability", async () => {
    renderRoom(makeSourcesFixture());
    await screen.findByText("Revenue grew 12% YoY in Q2.");
    // Three cards initially.
    expect(screen.getByText("Revenue grew 12% YoY in Q2.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "High reliability" }));
    // Only the high-reliability claim remains.
    expect(screen.getByText("Revenue grew 12% YoY in Q2.")).toBeInTheDocument();
    expect(screen.queryByText("Analyst note predicts margin pressure.")).not.toBeInTheDocument();
  });
});
