import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { CaseDetail } from "./CaseDetail";
import type { CaseView } from "../generated/case_view";
import type { TranslatedEvent } from "../api/sse";

const { mocks, state } = vi.hoisted(() => ({
  mocks: {
    getCaseView: vi.fn(),
    getFinalRecommendation: vi.fn(),
    getMonitoring: vi.fn(),
  },
  state: { events: [] as TranslatedEvent[] },
}));

vi.mock("../api/client", () => ({
  api: {
    getCaseView: mocks.getCaseView,
    getFinalRecommendation: mocks.getFinalRecommendation,
    getMonitoring: mocks.getMonitoring,
  },
}));

vi.mock("../api/sse", () => ({
  readStoredCursor: () => 0,
  hasStoredCursor: () => false,
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

function makeView(overrides: Partial<CaseView> = {}): CaseView {
  return {
    case_id: "case-014-should-i-take-the-ser",
    decision_question: "Should I take the Series B term sheet?",
    phase: "complete",
    stage: "done",
    is_terminal: true,
    needs_you: "none",
    brief_sections: [
      {
        key: "executive_recommendation",
        status: "final",
        blocks: [{ provenance: "recommendation", text: "Take the term sheet.", citation_ids: ["E-1"] }],
      },
      {
        key: "key_reasons",
        status: "final",
        blocks: [{ provenance: "interpretation", text: "Runway is the binding constraint." }],
      },
    ],
    ...overrides,
  } as CaseView;
}

function renderCase(view: CaseView, path = "/cases/case-1", events: TranslatedEvent[] = []) {
  state.events = events;
  mocks.getCaseView.mockResolvedValue(view);
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/cases/:caseId" element={<CaseDetail />} />
        <Route path="/cases/:caseId/brief" element={<CaseDetail />} />
        <Route path="/cases/:caseId/rooms/:room" element={<CaseDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  window.matchMedia = vi.fn().mockImplementation(() => ({
    matches: false,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
});

describe("the case surface heading", () => {
  it("is the decision question, not the case id", async () => {
    // The heading used to be `view.case_id`, so the user read a slug where
    // their own question belongs.
    renderCase(makeView());
    const heading = await screen.findByRole("heading", { level: 2 });
    expect(heading).toHaveTextContent("Should I take the Series B term sheet?");
    expect(heading.textContent).not.toMatch(/^case-\d+-/);
  });

  it("says the question is still being framed rather than falling back to the id", async () => {
    renderCase(makeView({ decision_question: "" }));
    const heading = await screen.findByRole("heading", { level: 2 });
    expect(heading).toHaveTextContent(/framing/i);
    expect(heading.textContent).not.toContain("case-014");
  });
});

describe("altitude", () => {
  it("shows only the answer-bearing sections at Answer altitude", async () => {
    renderCase(makeView());
    await screen.findByText("Take the term sheet.");
    await userEvent.click(screen.getByRole("button", { name: "Answer" }));

    expect(screen.getByText("Take the term sheet.")).toBeInTheDocument();
    expect(screen.queryByText("Runway is the binding constraint.")).not.toBeInTheDocument();
    // Provenance and the case map are apparatus, not answer.
    expect(screen.queryByText("Read of the evidence")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Where this case is")).not.toBeInTheDocument();
  });

  it("adds the full brief, provenance and the map at Reasoning altitude", async () => {
    renderCase(makeView());
    await screen.findByText("Take the term sheet.");
    await userEvent.click(screen.getByRole("button", { name: "Reasoning" }));

    expect(screen.getByText("Runway is the binding constraint.")).toBeInTheDocument();
    // Provenance renders as a voice, never as the enum (SPEC-049).
    expect(screen.getAllByText("Read of the evidence").length).toBeGreaterThan(0);
    expect(screen.queryByText("synthesizer")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Where this case is")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Rooms" })).not.toBeInTheDocument();
  });

  it("adds the rooms at Method altitude", async () => {
    renderCase(makeView());
    await screen.findByText("Take the term sheet.");
    await userEvent.click(screen.getByRole("button", { name: "Method" }));

    expect(screen.getByRole("navigation", { name: "Rooms" })).toBeInTheDocument();
  });

  it("persists the choice across cases, because it is a reader preference", async () => {
    const first = renderCase(makeView());
    await screen.findByText("Take the term sheet.");
    await userEvent.click(screen.getByRole("button", { name: "Answer" }));
    first.unmount();

    renderCase(makeView({ case_id: "case-2", decision_question: "A different question?" }));
    await screen.findByText("Take the term sheet.");
    expect(screen.getByRole("button", { name: "Answer" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText("Runway is the binding constraint.")).not.toBeInTheDocument();
  });
});

describe("rooms in the context panel", () => {
  it("opens the room beside the argument instead of replacing it", async () => {
    renderCase(makeView(), "/cases/case-1/rooms/sources");
    // The argument is still on screen — that is the whole point of the panel.
    expect(await screen.findByText("Take the term sheet.")).toBeInTheDocument();
    const panel = screen.getByRole("complementary", { name: "Sources" });
    expect(within(panel).getByRole("heading", { name: "Sources" })).toBeInTheDocument();
  });

  it("renders the case surface for the legacy /brief route", async () => {
    const { container } = renderCase(makeView(), "/cases/case-1/brief");
    expect(await screen.findByText("Take the term sheet.")).toBeInTheDocument();
    expect(container.querySelector(".app-shell-panel")).toBeNull();
  });

  it("opens no panel for an unknown room key", async () => {
    const { container } = renderCase(makeView(), "/cases/case-1/rooms/not-a-room");
    await screen.findByText("Take the term sheet.");
    expect(container.querySelector(".app-shell-panel")).toBeNull();
  });
});

describe("what the case needs from you", () => {
  it("is the one bordered card, and links to the checkpoint", async () => {
    renderCase(
      makeView({
        phase: "framing",
        stage: "awaiting_framing_approval",
        is_terminal: false,
        needs_you: "scope_checkpoint",
      }),
    );
    const card = await screen.findByLabelText("What this needs from you");
    expect(card).toHaveClass("action-card");
    expect(within(card).getByRole("link", { name: "Review the scope" })).toHaveAttribute(
      "href",
      "/cases/case-1/scope",
    );
  });

  it("offers no action for an interrupted case, because there is none to offer", async () => {
    renderCase(makeView({ needs_you: "interrupted", is_terminal: false }));
    const card = await screen.findByLabelText("What this needs from you");
    expect(within(card).queryByRole("link")).not.toBeInTheDocument();
  });

  it("shows no action card at all when nothing is waiting on the user", async () => {
    renderCase(makeView());
    await screen.findByText("Take the term sheet.");
    expect(screen.queryByLabelText("What this needs from you")).not.toBeInTheDocument();
  });
});

// Carried over from the deleted Brief screen, which this surface replaced.
describe("the living brief", () => {
  it("names pending sections rather than hiding them", async () => {
    renderCase(
      makeView({
        brief_sections: [
          { key: "executive_recommendation", status: "pending" },
          { key: "key_reasons", status: "pending" },
        ],
      } as Partial<CaseView>),
    );
    expect(await screen.findByText("Executive recommendation")).toBeInTheDocument();
    expect(screen.getByText("Key reasons")).toBeInTheDocument();
    expect(screen.getAllByText("Pending")).toHaveLength(2);
  });

  it("keeps technical events out of the transcript", async () => {
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
    renderCase(makeView(), "/cases/case-1", events);
    expect(await screen.findByText("Completed stage: investigation")).toBeInTheDocument();
    expect(screen.queryByText("researcher is running…")).not.toBeInTheDocument();
  });

  it("stamps a changed working view as non-final", async () => {
    renderCase(
      makeView({
        history: {
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
        },
      } as Partial<CaseView>),
    );
    expect(await screen.findByText("Working view")).toBeInTheDocument();
    expect(screen.getByText(/NON-FINAL/)).toBeInTheDocument();
    expect(screen.getByText(/Switch/)).toBeInTheDocument();
  });

  it("reports a finished case as complete rather than still running", async () => {
    // The old status row fell through to "In progress" once the work was done,
    // because `needs_you` is "none" for both. The map is the carrier now.
    renderCase(makeView());
    const map = await screen.findByLabelText("Where this case is");
    const current = within(map).getByText("Complete", { selector: ".case-map-phase-label" });
    expect(current.closest(".case-map-phase")).toHaveAttribute("data-phase", "complete");
  });
});

describe("navigation chrome", () => {
  it("carries no back link, because the chrome never goes away", async () => {
    const { container } = renderCase(makeView(), "/cases/case-1/rooms/sources");
    await screen.findByText("Take the term sheet.");
    expect(container.querySelectorAll(".back-link")).toHaveLength(0);
  });
});
