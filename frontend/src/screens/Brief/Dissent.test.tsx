import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { Dissent, isBlockingDissent, independentReviewFrom, type IndependentReviewView } from "./Dissent";
import type { CaseView, TrackDivergenceView } from "../../generated/case_view";

function divergence(overrides: Partial<TrackDivergenceView> = {}): TrackDivergenceView {
  return {
    stage: "preliminary_recommendation",
    agreement: false,
    divergence_summary: "The tracks disagree on whether to enter now or stage the entry.",
    reconciled_alternative: null,
    positions: [
      {
        track_id: "director",
        preferred_alternative: "Enter now at full size",
        top_reason: "The entry price is the binding constraint",
        recommendation_confidence: 0.71,
      },
      {
        track_id: "director_b",
        preferred_alternative: "Stage the entry over 90 days",
        top_reason: "Earnings risk is not priced in",
        recommendation_confidence: 0.64,
      },
    ],
    ...overrides,
  } as TrackDivergenceView;
}

const dissent: IndependentReviewView = {
  verdict: "dissent",
  reasoning: "The evidence supports a smaller position, not this one.",
  divergent_conclusion: "Take a half position and revisit after earnings.",
  unsupported_claims: ["Revenue growth of 120% justifies premium pricing"],
};

describe("a Director split", () => {
  it("shows both positions with their own alternatives", () => {
    render(<Dissent divergence={divergence()} />);
    expect(screen.getByText("Enter now at full size")).toBeInTheDocument();
    expect(screen.getByText("Stage the entry over 90 days")).toBeInTheDocument();
  });

  it("names each track by its voice rather than by its id", () => {
    render(<Dissent divergence={divergence()} />);
    expect(screen.getByText("The second Director")).toBeInTheDocument();
    expect(screen.queryByText("director_b")).not.toBeInTheDocument();
  });

  it("NEVER AVERAGES: no midpoint, blended confidence or merged position appears", () => {
    // This is the invariant the dual-track design exists to produce. A single
    // "combined confidence" bar is a plausible thing for a well-meaning
    // component to render, and it would silently destroy the property.
    const { container } = render(<Dissent divergence={divergence()} />);
    const text = container.textContent ?? "";

    // Each track's own confidence stands; the mean (67.5% → "68%") must not.
    expect(text).toContain("71%");
    expect(text).toContain("64%");
    expect(text).not.toContain("68%");
    expect(text).not.toContain("67%");

    // Nor any language that implies one merged answer.
    expect(text).not.toMatch(/combined|averaged into|merged|midpoint|on balance the tracks/i);
    expect(text).toMatch(/not averaged/i);

    // Exactly two positions — never a synthesised third.
    expect(container.querySelectorAll(".dissent-position")).toHaveLength(2);
  });

  it("renders nothing when the tracks agree", () => {
    const { container } = render(<Dissent divergence={divergence({ agreement: true })} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when no second track ran", () => {
    const { container } = render(<Dissent />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("a blocking reviewer dissent", () => {
  it("reads as a blocked signature, not as a caveat", () => {
    render(<Dissent independentReview={dissent} />);
    const alert = screen.getByRole("alert");
    expect(within(alert).getByText("Signature blocked")).toBeInTheDocument();
    expect(within(alert).getByText(/cannot be signed off/i)).toBeInTheDocument();
  });

  it("names the conclusion that reviewer would reach instead", () => {
    // A dissent that cannot name an alternative is a reservation; the artifact
    // enforces that, so the UI can always show it.
    render(<Dissent independentReview={dissent} />);
    expect(screen.getByText("Take a half position and revisit after earnings.")).toBeInTheDocument();
  });

  it("lists the claims the evidence does not carry", () => {
    render(<Dissent independentReview={dissent} />);
    expect(
      screen.getByText("Revenue growth of 120% justifies premium pricing"),
    ).toBeInTheDocument();
  });

  it("is visually distinct from a Director split", () => {
    const { container } = render(
      <Dissent divergence={divergence()} independentReview={dissent} />,
    );
    const blocking = container.querySelector(".dissent-blocking");
    const split = container.querySelector(".dissent-split");
    expect(blocking).not.toBeNull();
    expect(split).not.toBeNull();
    // The blocking one is an alert; a split is not.
    expect(blocking).toHaveAttribute("role", "alert");
    expect(split).not.toHaveAttribute("role", "alert");
  });

  it("renders nothing for a concurring reviewer", () => {
    const { container } = render(
      <Dissent independentReview={{ verdict: "concur", reasoning: "Agreed." }} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe("reading the reviewer off the case", () => {
  it("is null until SPEC-053 projects it, rather than throwing", () => {
    const view = { case_id: "case-1", integrity: { gates: [] } } as unknown as CaseView;
    expect(independentReviewFrom(view)).toBeNull();
  });

  it("reads the projected field once it exists", () => {
    const view = {
      case_id: "case-1",
      integrity: { gates: [], independent_review: dissent },
    } as unknown as CaseView;
    expect(independentReviewFrom(view)?.verdict).toBe("dissent");
  });

  it("blocks only on dissent", () => {
    expect(isBlockingDissent(dissent)).toBe(true);
    expect(isBlockingDissent({ verdict: "concur", reasoning: "ok" })).toBe(false);
    expect(isBlockingDissent(null)).toBe(false);
  });
});
