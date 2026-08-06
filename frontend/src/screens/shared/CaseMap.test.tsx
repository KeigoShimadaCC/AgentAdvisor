import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CaseMap, countersFromView, type LoopCounters } from "./CaseMap";
import type { CaseView } from "../../generated/case_view";

/**
 * The case map (SPEC-047).
 *
 * These tests exist because `MethodStrip` could not fail. It rendered six
 * phases by index comparison, and all four of the state machine's backward
 * edges are intra-phase, so a case going around the challenge cycle a second
 * time produced byte-identical DOM to a case going around it the first time —
 * and identical to a case that had hung. The last test here is that regression,
 * stated so it cannot come back.
 */

function makeView(over: Partial<CaseView> = {}): CaseView {
  return {
    case_id: "case-001-fixture",
    phase: "challenge",
    stage: "challenge",
    is_terminal: false,
    needs_you: "none",
    ...over,
  } as CaseView;
}

const NO_LOOPS: LoopCounters = {
  repairCycle: 0,
  repairCap: 2,
  synthesisRetries: 0,
  synthesisCap: 1,
  framingRevisions: 0,
  framingCap: 2,
  finalRevisions: 0,
  finalCap: 1,
};

describe("CaseMap", () => {
  it("draws every phase, so the shape of the engagement is visible up front", () => {
    const { container } = render(<CaseMap view={makeView()} counters={NO_LOOPS} />);
    // Scoped to the phase labels: "Complete" is also a stage label, so a bare
    // text query is ambiguous by design rather than by accident.
    const labels = [...container.querySelectorAll(".case-map-phase-label")].map((el) =>
      el.textContent?.trim(),
    );
    expect(labels).toEqual([
      "Intake",
      "Framing",
      "Investigation",
      "Challenge",
      "Synthesis",
      "Complete",
    ]);
  });

  it("draws all four cycles permanently, before any of them has run", () => {
    // A loop the user has been shown is a plan; a loop they discover mid-run is
    // a malfunction. All three cycle markers are present with zero rounds used.
    render(<CaseMap view={makeView()} counters={NO_LOOPS} />);
    expect(screen.getByTestId("cycle-rescope")).toHaveTextContent("can rescope up to 2×");
    expect(screen.getByTestId("cycle-repair")).toHaveTextContent("can repair up to 2×");
    expect(screen.getByTestId("cycle-re-review")).toHaveTextContent("can re-review up to 1×");
  });

  it("marks the current phase and the current stage", () => {
    const { container } = render(
      <CaseMap view={makeView({ phase: "synthesis", stage: "review" })} counters={NO_LOOPS} />,
    );
    expect(container.querySelector('[data-phase="synthesis"]')).toHaveClass("case-map-phase-current");
    expect(container.querySelector('[data-stage="review"]')).toHaveClass("case-map-stage-current");
  });

  it("names the two stages that wait for a human", () => {
    render(<CaseMap view={makeView({ phase: "framing", stage: "awaiting_framing_approval" })} counters={NO_LOOPS} />);
    const gates = screen.getAllByText(/needs you/);
    expect(gates).toHaveLength(2);
  });

  it("counts a repair round as 'round 2 of 3' once one has been consumed", () => {
    render(<CaseMap view={makeView()} counters={{ ...NO_LOOPS, repairCycle: 1 }} />);
    expect(screen.getByTestId("cycle-repair")).toHaveTextContent("repair — round 2 of 3");
  });

  it("shows a case at its cap as being at its cap", () => {
    render(<CaseMap view={makeView()} counters={{ ...NO_LOOPS, repairCycle: 2 }} />);
    expect(screen.getByTestId("cycle-repair")).toHaveTextContent("repair — round 3 of 3");
  });

  it("distinguishes a second challenge round from the first — the MethodStrip regression", () => {
    // This is the defect the phase strip structurally could not show. Both
    // cases are in the same phase and the same stage; only the counter differs,
    // and the rendered DOM must differ with it.
    const first = render(<CaseMap view={makeView()} counters={NO_LOOPS} />);
    const firstRound = first.container.innerHTML;
    first.unmount();

    const second = render(<CaseMap view={makeView()} counters={{ ...NO_LOOPS, repairCycle: 1 }} />);
    expect(second.container.innerHTML).not.toEqual(firstRound);
    expect(second.container.querySelector('[data-phase="challenge"]')).toHaveClass(
      "case-map-phase-looping",
    );
  });

  it("includes phase 8's competing-hypotheses stage", () => {
    const { container } = render(<CaseMap view={makeView({ phase: "investigation" })} counters={NO_LOOPS} />);
    expect(container.querySelector('[data-stage="competing_hypotheses"]')).toBeInTheDocument();
  });
});

describe("countersFromView", () => {
  it("reads the live counters out of the projection", () => {
    const counters = countersFromView(
      makeView({
        effort: {
          budget_counters: { repair_cycles: 2, synthesis_retries: 1, framing_revisions: 1 },
          budget_caps: { max_repair_cycles: 2 },
        },
      } as Partial<CaseView>),
    );
    expect(counters.repairCycle).toBe(2);
    expect(counters.synthesisRetries).toBe(1);
    expect(counters.framingRevisions).toBe(1);
    expect(counters.repairCap).toBe(2);
  });

  it("falls back to the engine's defaults when a case has no counters yet", () => {
    const counters = countersFromView(makeView());
    expect(counters.repairCycle).toBe(0);
    expect(counters.repairCap).toBe(2);
    expect(counters.framingCap).toBe(2);
    expect(counters.finalCap).toBe(1);
  });
});
