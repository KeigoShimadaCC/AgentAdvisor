import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { ActionPlan } from "./ActionPlan";
import type { NextActionView } from "../../generated/case_view";

function action(overrides: Partial<NextActionView> = {}): NextActionView {
  return {
    action_id: "N-001",
    action: "Place the initial 30% allocation",
    owner: "user",
    by_date: "2026-08-15",
    first_step: "Block 30 minutes and open the brokerage app",
    why_now: "Carries the recommendation into execution",
    estimated_cost: null,
    depends_on: [],
    ...overrides,
  } as NextActionView;
}

describe("the typed action plan", () => {
  it("renders every typed field phase 8 computes", () => {
    // These were all computed and then flattened into one sentence.
    render(
      <ActionPlan
        actions={[action({ estimated_cost: "about 30 minutes" })]}
      />,
    );
    expect(screen.getByText("Place the initial 30% allocation")).toBeInTheDocument();
    expect(screen.getByText("Block 30 minutes and open the brokerage app")).toBeInTheDocument();
    expect(screen.getByText("user")).toBeInTheDocument();
    expect(screen.getByText("2026-08-15")).toBeInTheDocument();
    expect(screen.getByText("about 30 minutes")).toBeInTheDocument();
    expect(screen.getByText("Carries the recommendation into execution")).toBeInTheDocument();
  });

  it("names a dependency rather than printing its id", () => {
    // "After N-001" tells a reader nothing they can act on.
    render(
      <ActionPlan
        actions={[
          action({ action_id: "N-001", action: "Open the account" }),
          action({ action_id: "N-002", action: "Place the order", depends_on: ["N-001"] }),
        ]}
      />,
    );
    const second = screen.getByText("Place the order").closest("li")!;
    expect(within(second).getByText("Open the account")).toBeInTheDocument();
    expect(within(second).queryByText("N-001")).not.toBeInTheDocument();
  });

  it("falls back to the id when the dependency is not in this plan", () => {
    render(<ActionPlan actions={[action({ depends_on: ["N-099"] })]} />);
    expect(screen.getByText("N-099")).toBeInTheDocument();
  });

  it("omits a cost it does not have rather than printing an empty row", () => {
    render(<ActionPlan actions={[action()]} />);
    expect(screen.queryByText("Cost")).not.toBeInTheDocument();
  });

  it("renders nothing when there is no plan", () => {
    const { container } = render(<ActionPlan actions={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
