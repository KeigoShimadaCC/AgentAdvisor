import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { CaseDetail } from "./CaseDetail";
import type { CaseView } from "../generated/case_view";

const { mocks } = vi.hoisted(() => ({
  mocks: { getCaseView: vi.fn() },
}));

vi.mock("../api/client", () => ({
  api: { getCaseView: mocks.getCaseView },
}));

vi.mock("../api/sse", () => ({
  SSEClient: class {
    connect() {}
    disconnect() {}
  },
}));

function makeView(overrides: Partial<CaseView> = {}): CaseView {
  return {
    case_id: "case-1",
    phase: "complete",
    stage: "done",
    is_terminal: true,
    needs_you: "none",
    ...overrides,
  } as CaseView;
}

function renderDetail(view: CaseView) {
  mocks.getCaseView.mockResolvedValue(view);
  return render(
    <MemoryRouter initialEntries={["/cases/case-1"]}>
      <Routes>
        <Route path="/cases/:caseId" element={<CaseDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

/** Read one <dd> by the text of the <dt> beside it. */
function metaValue(label: string): string {
  const dd = screen.getByText(label).nextElementSibling as HTMLElement | null;
  return dd?.textContent?.trim() ?? "";
}

describe("CaseDetail status line", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("reports a finished case as complete, not as still running", async () => {
    // `needs_you` is "none" for both a running case and a delivered one, so the
    // status used to fall through to "In progress" after the work was done.
    renderDetail(makeView());
    await screen.findByText("case-1");
    expect(metaValue("Status")).toBe("Complete");
  });

  it("still reports an unfinished case as in progress", async () => {
    renderDetail(makeView({ phase: "investigation", stage: "investigation", is_terminal: false }));
    await screen.findByText("case-1");
    expect(metaValue("Status")).toBe("In progress");
  });

  it("does not call a case complete when its review failed", async () => {
    renderDetail(
      makeView({ integrity: { review_accepted: false, review_outcome: "fail" } } as Partial<CaseView>),
    );
    await screen.findByText("case-1");
    expect(metaValue("Status")).toMatch(/review did not pass/i);
  });

  it("prefers the needs-you badge when the case is waiting on the user", async () => {
    renderDetail(
      makeView({ phase: "framing", stage: "awaiting_framing_approval", is_terminal: false, needs_you: "scope_checkpoint" }),
    );
    await screen.findByText("case-1");
    expect(metaValue("Status")).toBe("Needs your review");
  });

  it("shows the phase and the stage as distinct, humanized values", async () => {
    renderDetail(makeView({ phase: "investigation", stage: "evidence_critique", is_terminal: false }));
    await screen.findByText("case-1");
    expect(metaValue("Phase")).toBe("Investigating");
    expect(metaValue("Stage")).toBe("Critiquing the evidence");
  });

  it("renders brief sections with their provenance", async () => {
    renderDetail(
      makeView({
        brief_sections: [
          {
            key: "executive_recommendation",
            status: "final",
            blocks: [{ provenance: "synthesizer", text: "Buy the ETF.", citation_ids: ["E-1"] }],
          },
        ],
      }),
    );
    const section = await screen.findByText("Buy the ETF.");
    expect(within(section).getByText("synthesizer")).toBeInTheDocument();
  });
});
