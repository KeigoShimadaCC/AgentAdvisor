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

  it("credits the user with an option that framing only reworded", async () => {
    // Framing is specified to restate and broaden intake's alternatives, so an
    // exact-match origin check would tell the user the system invented the
    // option they themselves proposed — on the sheet they are about to sign.
    mocks.getIntakeRecord.mockResolvedValue({
      artifact_id: "intake_record",
      schema: "intake_record",
      data: { ...fixtures.intake, alternatives_mentioned: ["Switch jobs", "Stay put"] },
    });
    mocks.getDecisionSpec.mockResolvedValue({
      artifact_id: "decision_spec",
      schema: "decision_spec",
      data: {
        ...fixtures.decisionSpec,
        alternatives: ["Switch jobs now", "Stay put another year", "Negotiate a raise"],
      },
    });

    renderScope();
    await screen.findByText(SCOPE_COPY.restatementTitle);

    const originOf = (text: string) =>
      screen
        .getByText(text)
        .closest(".option-row")
        ?.querySelector(".option-origin")
        ?.getAttribute("aria-label");

    expect(originOf("Switch jobs now")).toBe("Your option");
    expect(originOf("Stay put another year")).toBe("Your option");
    // Genuinely new alternatives are still attributed to the analysis.
    expect(originOf("Negotiate a raise")).toBe("Added by analysis");
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

describe("ScopeCheckpoint objective weights (SPEC-038)", () => {
  const OBJECTIVES = ["Compare risk-adjusted compensation", "Evaluate learning velocity"];

  function specWithWeights(weights: Record<string, number> | undefined) {
    return {
      ...fixtures.decisionSpec,
      objectives: OBJECTIVES,
      ...(weights ? { objective_weights: weights } : {}),
    } as DecisionSpec;
  }

  function mockSpec(weights: Record<string, number> | undefined) {
    mocks.getDecisionSpec.mockResolvedValue({
      artifact_id: "decision_spec",
      schema: "decision_spec",
      data: specWithWeights(weights),
    });
  }

  function confirmGroundRules() {
    const boxes = screen
      .getAllByRole("checkbox")
      .filter((cb) => (cb.closest(".ground-rule-item") as HTMLElement | null) !== null);
    for (const cb of boxes) fireEvent.click(cb);
  }

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getCaseView.mockResolvedValue(fixtures.caseView);
    mocks.getIntakeRecord.mockResolvedValue({
      artifact_id: "intake_record",
      schema: "intake_record",
      data: fixtures.intake,
    });
    mocks.submitScopeCheckpoint.mockResolvedValue({ case_id: "case-1", stage: "structuring" });
  });

  it("renders no allocation section when framing proposed no weights", async () => {
    mockSpec(undefined);
    renderScope();
    await screen.findByText(SCOPE_COPY.restatementTitle);
    expect(screen.queryByText(SCOPE_COPY.weightsTitle)).not.toBeInTheDocument();
  });

  it("seeds the allocation from the framing proposal, rescaled to 100 points", async () => {
    // 40/60 of a 20-point proposal must present as 40/60 of 100.
    mockSpec({ [OBJECTIVES[0]]: 8, [OBJECTIVES[1]]: 12 });
    renderScope();
    await screen.findByText(SCOPE_COPY.weightsTitle);
    const inputs = screen.getAllByRole("spinbutton") as HTMLInputElement[];
    expect(inputs.map((i) => i.value)).toEqual(["40", "60"]);
    expect(screen.getByRole("status")).toHaveTextContent("100 / 100 points allocated");
  });

  it("blocks signing while the points do not add up to 100", async () => {
    mockSpec({ [OBJECTIVES[0]]: 50, [OBJECTIVES[1]]: 50 });
    renderScope();
    await screen.findByText(SCOPE_COPY.weightsTitle);
    confirmGroundRules();

    const signButton = screen.getByRole("button", { name: SCOPE_COPY.signButton });
    expect(signButton).not.toBeDisabled();

    const inputs = screen.getAllByRole("spinbutton") as HTMLInputElement[];
    fireEvent.change(inputs[0], { target: { value: "20" } });

    expect(screen.getByRole("status")).toHaveTextContent("70 / 100 points allocated");
    expect(screen.getByRole("status")).toHaveTextContent(SCOPE_COPY.weightsInvalid);
    expect(signButton).toBeDisabled();
  });

  it("submits a redistributed allocation through the revision path", async () => {
    mockSpec({ [OBJECTIVES[0]]: 50, [OBJECTIVES[1]]: 50 });
    renderScope();
    await screen.findByText(SCOPE_COPY.weightsTitle);
    confirmGroundRules();

    const inputs = screen.getAllByRole("spinbutton") as HTMLInputElement[];
    fireEvent.change(inputs[0], { target: { value: "70" } });
    fireEvent.change(inputs[1], { target: { value: "30" } });

    fireEvent.click(screen.getByRole("button", { name: SCOPE_COPY.signButton }));
    await vi.waitFor(() => expect(mocks.submitScopeCheckpoint).toHaveBeenCalled());

    const payload = mocks.submitScopeCheckpoint.mock.calls[0][1];
    expect(payload.decision).toBe("edit");
    expect(payload.edits.objective_weights).toEqual({
      [OBJECTIVES[0]]: 70,
      [OBJECTIVES[1]]: 30,
    });
  });

  it("signs cleanly when the proposed allocation is accepted unchanged", async () => {
    mockSpec({ [OBJECTIVES[0]]: 40, [OBJECTIVES[1]]: 60 });
    renderScope();
    await screen.findByText(SCOPE_COPY.weightsTitle);
    confirmGroundRules();

    fireEvent.click(screen.getByRole("button", { name: SCOPE_COPY.signButton }));
    await vi.waitFor(() => expect(mocks.submitScopeCheckpoint).toHaveBeenCalled());
    expect(mocks.submitScopeCheckpoint.mock.calls[0][1].decision).toBe("approve");
  });
});
