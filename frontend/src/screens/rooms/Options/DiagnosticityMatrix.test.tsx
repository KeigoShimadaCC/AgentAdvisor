import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { InspectorContext } from "../../inspector/inspectorContext";
import { DiagnosticityMatrix } from "./DiagnosticityMatrix";
import type { OptionsRoom } from "../../../generated/case_view";

function room(overrides: Partial<OptionsRoom> = {}): OptionsRoom {
  return {
    ach_scored: true,
    ach_uninformative_evidence_ids: [],
    ev_table: {},
    options: [
      {
        alternative: "staged_entry",
        rationale: "",
        disconfirmation_rank: 1,
        disconfirming_weight: 0,
        disconfirming_evidence_ids: [],
        eliminated: false,
      },
      {
        alternative: "invest_nvda_now",
        rationale: "",
        disconfirmation_rank: 2,
        disconfirming_weight: 0.25,
        disconfirming_evidence_ids: ["E-001"],
        eliminated: false,
      },
      {
        alternative: "etf_diversified",
        rationale: "",
        disconfirmation_rank: 3,
        disconfirming_weight: 0.75,
        disconfirming_evidence_ids: ["E-002"],
        eliminated: true,
      },
    ],
    ...overrides,
  } as OptionsRoom;
}

function renderMatrix(r: OptionsRoom) {
  return render(
    <MemoryRouter>
      <InspectorContext.Provider value={{ open: () => {}, close: () => {}, openId: null }}>
        <DiagnosticityMatrix room={r} />
      </InspectorContext.Provider>
    </MemoryRouter>,
  );
}

describe("the diagnosticity matrix", () => {
  it("says what rank 1 means, because 'rank 1' alone inverts it", () => {
    // Strong means little disconfirms it, not that much supports it. Without
    // the gloss a reader takes rank 1 as "most supported".
    const { container } = renderMatrix(room());
    expect(screen.getByText(/argued against least successfully/i)).toBeInTheDocument();
    // The emphasis on "disconfirming" splits the sentence across elements, so
    // match the rendered text rather than a single node.
    expect(container.textContent).toMatch(/disconfirming[\s\S]*not by support/i);
  });

  it("orders by disconfirmation rank, lowest weight first", () => {
    const { container } = renderMatrix(room());
    const rows = [...container.querySelectorAll("tbody tr")].map((r) => r.textContent ?? "");
    expect(rows[0]).toContain("staged_entry");
    expect(rows[2]).toContain("etf_diversified");
  });

  it("marks an alternative the evidence ruled out", () => {
    const { container } = renderMatrix(room());
    const eliminated = container.querySelector(".ach-row-eliminated");
    expect(eliminated).not.toBeNull();
    expect(within(eliminated as HTMLElement).getByText(/ruled out/)).toBeInTheDocument();
  });

  it("names the evidence that changed nothing, which a reader could never derive", () => {
    renderMatrix(room({ ach_uninformative_evidence_ids: ["E-003"] }));
    expect(screen.getByText(/could not have moved the ranking/i)).toBeInTheDocument();
    expect(screen.getByText("E-003")).toBeInTheDocument();
  });

  it("says so plainly when every piece of evidence discriminated", () => {
    renderMatrix(room());
    expect(screen.getByText(/discriminated between at least two/i)).toBeInTheDocument();
  });

  it("renders nothing when no matrix was built", () => {
    const { container } = renderMatrix(room({ ach_scored: false }));
    expect(container).toBeEmptyDOMElement();
  });
});
