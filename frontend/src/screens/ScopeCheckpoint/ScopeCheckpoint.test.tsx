import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ScopeCheckpoint } from "./ScopeCheckpoint";
import type { CaseView } from "../../generated/case_view";
import type { IntakeRecord } from "../../generated/intake_record";
import type { DecisionSpec } from "../../generated/decision_spec";
import { SCOPE_COPY } from "../../copy/terms";

// vi.hoisted runs before vi.mock factories, so the fixtures and mock fns are
// available inside the hoisted factory.
const { mocks, fixtures } = vi.hoisted(() => {
  const mocks = {
    getCaseView: vi.fn(),
    getIntakeRecord: vi.fn(),
    getDecisionSpec: vi.fn(),
    submitScopeCheckpoint: vi.fn(),
  };
  const fixtures = {
    caseView: {
      case_id: "case-1",
      phase: "framing",
      stage: "awaiting_framing_approval",
      is_terminal: false,
      needs_you: "scope_checkpoint",
    } as CaseView,
    intake: {
      raw_prompt: "Should I switch jobs?",
      alternatives_mentioned: ["Stay", "Switch"],
    } as IntakeRecord,
    decisionSpec: {
      decision_id: "d-1",
      question: "Should I switch jobs now or stay another year?",
      alternatives: ["Stay", "Switch", "Negotiate"],
      objectives: ["Compare risk-adjusted compensation", "Evaluate learning velocity"],
      deadline: "this year",
      depth: "standard",
      owner: "user",
      reversibility: "partially_reversible",
      risk_tolerance: "moderate",
      schema_version: 1,
    } as DecisionSpec,
  };
  return { mocks, fixtures };
});

vi.mock("../../api/client", () => ({
  api: {
    getCaseView: mocks.getCaseView,
    getIntakeRecord: mocks.getIntakeRecord,
    getDecisionSpec: mocks.getDecisionSpec,
    submitScopeCheckpoint: mocks.submitScopeCheckpoint,
  },
}));

function renderScope() {
  return render(
    <MemoryRouter initialEntries={["/cases/case-1/scope"]}>
      <Routes>
        <Route path="/cases/:caseId/scope" element={<ScopeCheckpoint />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ScopeCheckpoint confirmation gating", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getCaseView.mockResolvedValue(fixtures.caseView);
    mocks.getIntakeRecord.mockResolvedValue({
      artifact_id: "intake_record",
      schema: "intake_record",
      data: fixtures.intake,
    });
    mocks.getDecisionSpec.mockResolvedValue({
      artifact_id: "decision_spec",
      schema: "decision_spec",
      data: fixtures.decisionSpec,
    });
    mocks.submitScopeCheckpoint.mockResolvedValue({ case_id: "case-1", stage: "structuring" });
  });

  it("renders the restatement and options", async () => {
    renderScope();
    // Wait for the decision spec to load.
    expect(await screen.findByText(SCOPE_COPY.restatementTitle)).toBeInTheDocument();
    expect(screen.getByDisplayValue(fixtures.decisionSpec.question)).toBeInTheDocument();
    expect(screen.getByText("Stay")).toBeInTheDocument();
    expect(screen.getByText("Switch")).toBeInTheDocument();
    expect(screen.getByText("Negotiate")).toBeInTheDocument();
  });

  it("disables Sign & begin until all ground rules are confirmed", async () => {
    renderScope();
    await screen.findByText(SCOPE_COPY.restatementTitle);

    const signButton = screen.getByRole("button", { name: SCOPE_COPY.signButton });
    expect(signButton).toBeDisabled();

    // Confirm each ground rule checkbox.
    const checkboxes = screen.getAllByRole("checkbox");
    const groundRuleBoxes = checkboxes.filter(
      (cb) => (cb.closest(".ground-rule-item") as HTMLElement | null) !== null,
    );
    expect(groundRuleBoxes).toHaveLength(3);
    for (const cb of groundRuleBoxes) {
      fireEvent.click(cb);
    }
    expect(signButton).not.toBeDisabled();
  });

  it("signs with approve when no edits are pending and all confirmed", async () => {
    renderScope();
    await screen.findByText(SCOPE_COPY.restatementTitle);

    // Confirm all ground rules.
    const groundRuleBoxes = screen
      .getAllByRole("checkbox")
      .filter((cb) => (cb.closest(".ground-rule-item") as HTMLElement | null) !== null);
    for (const cb of groundRuleBoxes) fireEvent.click(cb);

    fireEvent.click(screen.getByRole("button", { name: SCOPE_COPY.signButton }));

    // Wait for the submit call.
    await vi.waitFor(() => expect(mocks.submitScopeCheckpoint).toHaveBeenCalled());
    const payload = mocks.submitScopeCheckpoint.mock.calls[0][1];
    expect(payload.decision).toBe("approve");
    expect(payload.confirmations).toEqual(["deadline", "risk_tolerance", "reversibility"]);
    expect(payload.summary_hash).toMatch(/^[0-9a-f]{8}$/);
  });
});
