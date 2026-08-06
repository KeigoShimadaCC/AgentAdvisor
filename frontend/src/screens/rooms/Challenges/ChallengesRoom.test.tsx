import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ChallengesRoom } from "./ChallengesRoom";
import { makeChallengesFixture, makeTrackBAbsentFixture } from "../fixtures";
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
    <MemoryRouter initialEntries={["/cases/case-1/rooms/challenges"]}>
      <Routes>
        <Route path="/cases/:caseId/rooms/challenges" element={<ChallengesRoom />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Challenges room", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders all open objections above resolved ones", async () => {
    renderRoom(makeChallengesFixture());
    expect(await screen.findByText("Cost estimates omit tax drag.")).toBeInTheDocument();
    const items = screen.getAllByRole("listitem").filter((li) => li.classList.contains("objection-row"));
    expect(items.length).toBeGreaterThanOrEqual(2);
    // The open objection (O-1) appears before the resolved one (O-2).
    const openText = "Cost estimates omit tax drag.";
    const resolvedText = "The ETF ignores company-specific upside.";
    const openIdx = items.findIndex((li) => li.textContent?.includes(openText));
    const resolvedIdx = items.findIndex((li) => li.textContent?.includes(resolvedText));
    expect(openIdx).toBeGreaterThanOrEqual(0);
    expect(resolvedIdx).toBeGreaterThanOrEqual(0);
    expect(openIdx).toBeLessThan(resolvedIdx);
  });

  it("renders the divergence with two positions side by side and the word Disagree", async () => {
    renderRoom(makeChallengesFixture());
    expect(await screen.findByText("Disagree")).toBeInTheDocument();
    expect(screen.getByText("track-a")).toBeInTheDocument();
    expect(screen.getByText("track-b")).toBeInTheDocument();
    // never-averaged footer (scoped to avoid matching multiple ancestor elements).
    const footer = screen.getByText((_, el) => el?.classList.contains("never-averaged-footer") ?? false);
    expect(within(footer).getByText(/never averaged/i)).toBeInTheDocument();
  });

  it("renders the stated-absence line when track B did not run", async () => {
    renderRoom(makeTrackBAbsentFixture());
    expect(await screen.findByText(/second reasoning track was not run/i)).toBeInTheDocument();
  });
});
