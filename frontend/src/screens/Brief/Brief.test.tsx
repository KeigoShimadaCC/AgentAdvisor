import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Brief } from "./Brief";
import type { CaseView } from "../../generated/case_view";
import type { TranslatedEvent } from "../../api/sse";

const { mocks, state } = vi.hoisted(() => ({
  mocks: {
    getCaseView: vi.fn(),
    getFinalRecommendation: vi.fn(),
  },
  state: { events: [] as TranslatedEvent[] },
}));

vi.mock("../../api/client", () => ({
  api: {
    getCaseView: mocks.getCaseView,
    getFinalRecommendation: mocks.getFinalRecommendation,
  },
}));

vi.mock("../../api/sse", () => ({
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

function makeView(): CaseView {
  return {
    case_id: "case-1",
    stage: "investigation",
    phase: "investigation",
    is_terminal: false,
    needs_you: "none",
    brief_sections: [
      { key: "executive_recommendation", status: "pending" },
      { key: "key_reasons", status: "pending" },
    ],
  } as CaseView;
}

function renderBrief(view: CaseView, events: TranslatedEvent[] = []) {
  state.events = events;
  mocks.getCaseView.mockResolvedValue(view);
  return render(
    <MemoryRouter initialEntries={["/cases/case-1/brief"]}>
      <Routes>
        <Route path="/cases/:caseId/brief" element={<Brief />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Brief", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.matchMedia = vi.fn().mockImplementation(() => ({
      matches: false,
      addEventListener: () => {},
      removeEventListener: () => {},
    }));
  });

  it("renders skeleton with pending sections", async () => {
    renderBrief(makeView());
    expect(await screen.findByText("Executive recommendation")).toBeInTheDocument();
    expect(screen.getByText("Key reasons")).toBeInTheDocument();
    expect(screen.getAllByText("Pending")).toHaveLength(2);
  });

  it("filters technical events from margin narration", async () => {
    const events: TranslatedEvent[] = [
      {
        event_type: "role_invocation_attempt",
        message: "researcher is running…",
        technical: true,
        raw_payload: {},
        line_cursor: 1,
      },
      {
        event_type: "stage_completed",
        message: "Completed stage: investigation",
        technical: false,
        raw_payload: {},
        line_cursor: 2,
      },
    ];
    renderBrief(makeView(), events);
    expect(await screen.findByText("Completed stage: investigation")).toBeInTheDocument();
    expect(screen.queryByText("researcher is running…")).not.toBeInTheDocument();
  });

  it("shows working view changes with NON-FINAL stamp", async () => {
    const view = makeView();
    view.history = {
      thesis_revisions: [
        {
          revision: 1,
          changed: true,
          preferred_alternative: "Switch",
          previous_alternative: "Stay",
          trigger: "evidence",
          recommendation_confidence: 0.6,
          evidence_confidence: 0.5,
          rationale_digest: ["new evidence found"],
        },
      ],
      approvals: [],
    };
    renderBrief(view);
    expect(await screen.findByText("Working view")).toBeInTheDocument();
    expect(screen.getByText(/NON-FINAL/)).toBeInTheDocument();
    expect(screen.getByText(/Switch/)).toBeInTheDocument();
  });
});
