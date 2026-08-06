import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Delivery } from "./Delivery";
import type { CaseView } from "../../generated/case_view";
import type { FinalRecommendation } from "../../generated/final_recommendation";
import type { TranslatedEvent } from "../../api/sse";

const { mocks, state } = vi.hoisted(() => ({
  mocks: {
    getCaseView: vi.fn(),
    getFinalRecommendation: vi.fn(),
    approveDelivery: vi.fn(),
    requestFinalRevision: vi.fn(),
    getMonitoring: vi.fn(),
  },
  state: { events: [] as TranslatedEvent[] },
}));

vi.mock("../../api/client", () => ({
  api: {
    getCaseView: mocks.getCaseView,
    getFinalRecommendation: mocks.getFinalRecommendation,
    approveDelivery: mocks.approveDelivery,
    requestFinalRevision: mocks.requestFinalRevision,
    getMonitoring: mocks.getMonitoring,
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
    stage: "awaiting_final_approval",
    phase: "synthesis",
    is_terminal: false,
    needs_you: "delivery_checkpoint",
    brief_sections: [
      {
        key: "executive_recommendation",
        status: "final",
        blocks: [
          { provenance: "recommendation", text: "Recommended action: Switch" },
          { provenance: "recommendation", text: "Timing: Now" },
        ],
      },
      { key: "key_reasons", status: "final", blocks: [{ provenance: "interpretation", text: "Reason one" }] },
      {
        key: "next_actions",
        status: "final",
        blocks: [
          {
            provenance: "recommendation",
            text: "Talk to manager — user, by 2026-08-15. First step: Send a calendar invite for a 30-minute conversation",
          },
        ],
      },
    ],
    uncertainty: {
      recommendation_confidence: { kind: "assessed", value: 0.75, basis: "consistent evidence" },
      evidence_confidence: { kind: "assessed", value: 0.65, basis: "mixed sources" },
      model_stability: { kind: "assessed", runs_supporting: 7, runs_total: 10, share: 0.7 },
      outcome_probabilities: {
        "Switch succeeds": {
          method: "scenario_model",
          point: 0.75,
          interval_low: 0.6,
          interval_high: 0.85,
        },
      },
    },
    integrity: { review_accepted: true, review_defects: [], review_outcome: "pass" },
  } as CaseView;
}

function makeFinal(): FinalRecommendation {
  return {
    recommended_action: "Switch jobs",
    timing: "Now",
    decision_confidence_summary: "Confident",
    alternatives_considered: [{ alternative: "Switch", rank: 1, rationale: "Better" }],
    key_reasons: ["Reason one", "Reason two"],
    scenario_analysis: [
      {
        scenario_name: "Base",
        summary: "Good",
        probability: { method: "scenario_model", point: 0.7 },
      },
    ],
    model_stability: {
      runs_supporting: 7,
      runs_total: 10,
      share_of_sensitivity_runs_supporting_recommendation: 0.7,
    },
    recommendation_confidence: { value: 0.75, basis: "consistent" },
    evidence_confidence: { value: 0.65, basis: "mixed" },
    outcome_probabilities: { "Switch succeeds": { method: "scenario_model", point: 0.75 } },
    next_actions: [
      {
        action_id: "N-001",
        action: "Talk to manager",
        owner: "user",
        by_date: "2026-08-15",
        first_step: "Send a calendar invite for a 30-minute conversation",
        why_now: "The offer deadline lands in three weeks",
        depends_on: [],
        estimated_cost: null,
      },
    ],
  } as FinalRecommendation;
}

function renderDelivery(view: CaseView, events: TranslatedEvent[] = []) {
  state.events = events;
  mocks.getCaseView.mockResolvedValue(view);
  mocks.getFinalRecommendation.mockResolvedValue({
    artifact_id: "final_recommendation",
    schema: "final_recommendation",
    data: makeFinal(),
  });
  mocks.approveDelivery.mockResolvedValue({ case_id: "case-1", stage: "done" });
  mocks.requestFinalRevision.mockResolvedValue({ case_id: "case-1", stage: "synthesis" });
  // A case with no monitoring plan is the normal case for an in-flight
  // decision, and the panel renders nothing for it.
  mocks.getMonitoring.mockResolvedValue({ plan: null, due: [] });
  return render(
    <MemoryRouter initialEntries={["/cases/case-1/delivery"]}>
      <Routes>
        <Route path="/cases/:caseId/delivery" element={<Delivery />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Delivery", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.matchMedia = vi.fn().mockImplementation(() => ({
      matches: false,
      addEventListener: () => {},
      removeEventListener: () => {},
    }));
  });

  it("renders answer card and all four uncertainty measures", async () => {
    renderDelivery(makeView());
    expect(await screen.findByText("Switch jobs")).toBeInTheDocument();
    // SPEC-050 moved the four encodings one click down; they are unchanged in
    // substance and still all four.
    fireEvent.click(screen.getByText("How sure is this?"));
    expect(screen.getByText("Probability")).toBeInTheDocument();
    expect(screen.getByText("Confidence in this recommendation")).toBeInTheDocument();
    expect(screen.getByText("Source strength")).toBeInTheDocument();
    expect(screen.getByText("Stability")).toBeInTheDocument();
  });

  it("shows owner and due date for each next action", async () => {
    renderDelivery(makeView());
    expect(await screen.findByText("Switch jobs")).toBeInTheDocument();
    const action = screen.getByText(/Talk to manager/);
    expect(action).toHaveTextContent("user");
    expect(action).toHaveTextContent("2026-08-15");
    expect(action).toHaveTextContent("First step:");
  });

  it("renders NotAssessed widgets without numbers", async () => {
    const view = makeView();
    view.uncertainty = {
      recommendation_confidence: { kind: "not_assessed", reason: "No sensitivity runs" },
      evidence_confidence: { kind: "not_assessed", reason: "No evidence gathered" },
      model_stability: { kind: "not_assessed", reason: "No sensitivity runs" },
      outcome_probabilities: {},
    };
    renderDelivery(view);
    expect(await screen.findByText("Switch jobs")).toBeInTheDocument();
    fireEvent.click(screen.getByText("How sure is this?"));
    expect(screen.getAllByText("Not assessed").length).toBeGreaterThan(0);
    expect(screen.queryByText(/0\.0%/)).not.toBeInTheDocument();
    expect(screen.queryByText(/0%/)).not.toBeInTheDocument();
  });

  it("enables Accept when stage is awaiting_final_approval", async () => {
    renderDelivery(makeView());
    expect(await screen.findByRole("button", { name: /Accept this recommendation/ })).toBeEnabled();
  });

  it("routes send back through requestFinalRevision", async () => {
    renderDelivery(makeView());
    const note = await screen.findByLabelText(/Send back with a note/);
    fireEvent.change(note, { target: { value: "Need more evidence" } });
    // SPEC-050: send-back is now two steps, because it spends the only
    // revision the case has.
    fireEvent.click(screen.getByRole("button", { name: "Send back" }));
    expect(screen.getByText(/only send-back this case has/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Send it back" }));
    await vi.waitFor(() => expect(mocks.requestFinalRevision).toHaveBeenCalled());
    expect(mocks.requestFinalRevision).toHaveBeenCalledWith("case-1", "Need more evidence");
  });

  it("renders integrity slip with review verdict and defects", async () => {
    const view = makeView();
    view.integrity = {
      review_accepted: false,
      review_outcome: "fail",
      review_defects: [
        { defect_type: "missing_evidence", target_id: "E-1", explanation: "Missing source" },
      ],
    };
    renderDelivery(view);
    expect(await screen.findByText(/Rejected/)).toBeInTheDocument();
    expect(screen.getByText(/Missing source/)).toBeInTheDocument();
  });
});

describe("a blocking reviewer dissent (SPEC-049)", () => {
  const dissent = {
    verdict: "dissent",
    reasoning: "The evidence supports a smaller position.",
    divergent_conclusion: "Take a half position and revisit after earnings.",
  };

  it("takes the signature away rather than rendering the dissent beside a live button", () => {
    // SPEC-039 says a dissent blocks delivery. Showing the dissent while
    // leaving Accept clickable would make the block advisory.
    const view = makeView();
    (view as unknown as { integrity: Record<string, unknown> }).integrity = {
      gates: [],
      independent_review: dissent,
    };
    renderDelivery(view);
    return screen.findByText("Signature blocked").then(() => {
      expect(
        screen.queryByRole("button", { name: "Accept this recommendation" }),
      ).not.toBeInTheDocument();
      expect(screen.getByText(/Signing is blocked/i)).toBeInTheDocument();
      // The conclusion the reviewer would reach instead is on screen, so the
      // block is actionable rather than merely obstructive.
      expect(
        screen.getByText("Take a half position and revisit after earnings."),
      ).toBeInTheDocument();
    });
  });

  it("leaves the signature alone when the reviewer concurs", async () => {
    const view = makeView();
    (view as unknown as { integrity: Record<string, unknown> }).integrity = {
      gates: [],
      independent_review: { verdict: "concur", reasoning: "Agreed." },
    };
    renderDelivery(view);
    expect(
      await screen.findByRole("button", { name: "Accept this recommendation" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Signature blocked")).not.toBeInTheDocument();
  });
});
