import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { InspectorContext } from "../screens/inspector/inspectorContext";
import {
  encodeConfidence,
  encodeEvidence,
  encodeStability,
  encodeProbability,
  encodingClass,
  type Scale,
} from "./language";
import { Measure } from "./Measure";
import { Why } from "./Why";
import { ProbabilityBand } from "./ProbabilityBand";
import { StabilityDots } from "./StabilityDots";
import { PROBABILITY_PHRASES, CONFIDENCE_BANDS, SOURCE_GRADES } from "../copy/uncertainty";

const SCALES: Scale[] = ["inline", "summary", "full"];

function withRouter(node: React.ReactNode) {
  return render(
    <MemoryRouter>
      <InspectorContext.Provider value={{ open: () => {}, close: () => {}, openId: null }}>
        {node}
      </InspectorContext.Provider>
    </MemoryRouter>,
  );
}

// ── The rule the whole spec exists to hold ───────────────────────────────────

describe("no measure is ever combined with another", () => {
  it("gives each measure its own idiom, and no encoding takes two values", () => {
    // Four measures that disagree are the honest output. An encoding that could
    // accept two of them is the first step to a dial that averages them.
    const encodings = [
      encodeConfidence({ kind: "assessed", value: 0.72, basis: "x" }),
      encodeEvidence({ kind: "assessed", value: 0.55, basis: "y" }),
      encodeStability({ kind: "assessed", runs_supporting: 9, runs_total: 10, share: 0.9 }),
      encodeProbability({ method: "reference_class", point: 0.62 }),
    ];
    expect(encodings.map((e) => e.kind)).toEqual(["band", "grade", "countable", "range"]);
    // Four distinct kinds: no two measures share a rendering, so none can be
    // silently swapped for a combined one.
    expect(new Set(encodings.map((e) => e.kind)).size).toBe(4);
  });

  it("renders no combined score, average or overall number", () => {
    const { container } = withRouter(
      <>
        <Measure encoding={encodeConfidence({ kind: "assessed", value: 0.72, basis: "x" })} />
        <Measure encoding={encodeEvidence({ kind: "assessed", value: 0.55, basis: "y" })} />
        <Measure
          encoding={encodeStability({ kind: "assessed", runs_supporting: 9, runs_total: 10, share: 0.9 })}
        />
      </>,
    );
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/overall|combined|average|aggregate|composite|total confidence/i);
    // 0.72, 0.55 and 0.9 average to 0.72 — the number that must never appear as
    // a summary. Confidence renders as a band label, not as its value.
    expect(text).not.toContain("72%");
    expect(text).not.toContain("0.72");
  });
});

// ── Section 9's point-XOR-interval rule ──────────────────────────────────────

describe("a point and an interval are different claims", () => {
  it("renders a point estimate as a point", () => {
    const { container } = withRouter(
      <Measure encoding={encodeProbability({ method: "reference_class", point: 0.62 })} />,
    );
    expect(container.querySelector(".u-point")).not.toBeNull();
    expect(container.querySelector(".u-interval")).toBeNull();
    expect(container.textContent).toContain("62%");
  });

  it("renders an interval as an interval, never as its midpoint", () => {
    // An interval is the statement that the point is *not* known; collapsing it
    // to a midpoint asserts the opposite.
    const { container } = withRouter(
      <Measure
        encoding={encodeProbability({ method: "scenario_model", interval_low: 0.4, interval_high: 0.8 })}
      />,
    );
    expect(container.querySelector(".u-interval")).not.toBeNull();
    expect(container.querySelector(".u-point")).toBeNull();
    expect(container.textContent).toContain("40%");
    expect(container.textContent).toContain("80%");
    expect(container.textContent).not.toContain("60%");
  });

  it("produces distinguishable DOM for the two, which is the acceptance criterion", () => {
    const point = withRouter(
      <Measure encoding={encodeProbability({ method: "m", point: 0.6 })} />,
    ).container.innerHTML;
    const interval = withRouter(
      <Measure encoding={encodeProbability({ method: "m", interval_low: 0.4, interval_high: 0.8 })} />,
    ).container.innerHTML;
    expect(point).not.toBe(interval);
  });

  it("gives an interval no verbal phrase, because there is no single point to name", () => {
    const encoding = encodeProbability({ method: "m", interval_low: 0.4, interval_high: 0.8 });
    expect(encoding.kind === "range" && encoding.phrase).toBe("");
  });
});

// ── Countable marks ──────────────────────────────────────────────────────────

describe("stability is countable, not a percentage", () => {
  it.each([
    [9, 10],
    [2, 3],
    [1, 1],
    [0, 5],
  ])("draws %i filled of %i marks", (supporting, total) => {
    const { container } = withRouter(
      <StabilityDots
        stability={{ kind: "assessed", runs_supporting: supporting, runs_total: total, share: supporting / total }}
      />,
    );
    expect(container.querySelectorAll(".u-dot")).toHaveLength(total);
    expect(container.querySelectorAll(".u-dot.filled")).toHaveLength(supporting);
  });

  it("says the count in words for a screen reader rather than a share", () => {
    const { container } = withRouter(
      <StabilityDots stability={{ kind: "assessed", runs_supporting: 2, runs_total: 3, share: 0.667 }} />,
    );
    const dots = container.querySelector(".countable-dots");
    expect(dots).toHaveAttribute("aria-label", "held in 2 of 3 sensitivity runs");
    expect(container.textContent).not.toContain("67%");
  });
});

// ── The sentinel ─────────────────────────────────────────────────────────────

describe("not assessed is explicit", () => {
  it("stamps it, with its reason, and never a number", () => {
    const { container } = withRouter(
      <Measure encoding={encodeStability({ kind: "not_assessed", reason: "single run" })} />,
    );
    expect(screen.getByText(/Not assessed/)).toBeInTheDocument();
    expect(screen.getByText("single run")).toBeInTheDocument();
    expect(container.querySelectorAll(".u-dot")).toHaveLength(0);
    expect(container.textContent).not.toMatch(/\d+%/);
  });

  it("says something rather than nothing when no reason was given", () => {
    const encoding = encodeConfidence({ kind: "not_assessed", reason: "" });
    expect(encoding.kind === "not_assessed" && encoding.reason).toMatch(/not assessed/i);
  });

  it("treats a missing measure as not assessed, not as zero", () => {
    // Each encoder declares the absent case in its own signature; this asserts
    // they all *behave* the same way on it, which is what a screen depends on.
    expect(encodeConfidence(null).kind).toBe("not_assessed");
    expect(encodeConfidence(undefined).kind).toBe("not_assessed");
    expect(encodeEvidence(null).kind).toBe("not_assessed");
    expect(encodeEvidence(undefined).kind).toBe("not_assessed");
    expect(encodeStability(null).kind).toBe("not_assessed");
    expect(encodeStability(undefined).kind).toBe("not_assessed");
    expect(encodeProbability(null).kind).toBe("not_assessed");
    expect(encodeProbability(undefined).kind).toBe("not_assessed");
  });
});

// ── One idiom at every scale ─────────────────────────────────────────────────

describe("the same measure is the same idiom at every scale", () => {
  const cases = [
    { name: "confidence", encoding: encodeConfidence({ kind: "assessed", value: 0.72, basis: "b" }) },
    { name: "evidence", encoding: encodeEvidence({ kind: "assessed", value: 0.55, basis: "b" }) },
    {
      name: "stability",
      encoding: encodeStability({ kind: "assessed", runs_supporting: 9, runs_total: 10, share: 0.9 }),
    },
    { name: "probability", encoding: encodeProbability({ method: "m", point: 0.62 }) },
    { name: "not assessed", encoding: encodeConfidence({ kind: "not_assessed", reason: "r" }) },
  ];

  for (const { name, encoding } of cases) {
    it.each(SCALES)(`${name} keeps its kind at %s scale`, (scale) => {
      // The class carries the kind at every scale, which is what makes "a band
      // looks like a band everywhere" checkable rather than a review opinion.
      const { container } = withRouter(<Measure encoding={encoding} scale={scale} />);
      expect(container.firstElementChild).toHaveClass(`u-${encoding.kind}`);
      expect(container.firstElementChild).toHaveClass(`u-scale-${scale}`);
      expect(encodingClass(encoding, scale)).toContain(`u-${encoding.kind}`);
    });
  }

  it("shows less at inline scale without changing idiom", () => {
    const encoding = encodeEvidence({ kind: "assessed", value: 0.55, basis: "two primary sources" });
    const inline = withRouter(<Measure encoding={encoding} scale="inline" />);
    const full = withRouter(<Measure encoding={encoding} scale="full" />);
    // Same letter in both; the basis only at full.
    expect(within(inline.container).getByText("C")).toBeInTheDocument();
    expect(within(full.container).getByText("C")).toBeInTheDocument();
    expect(inline.container.textContent).not.toContain("two primary sources");
    expect(full.container.textContent).toContain("two primary sources");
  });
});

// ── The vocabulary ───────────────────────────────────────────────────────────

describe("the words come from the lexicon", () => {
  it("keeps the thresholds SPEC-035 shipped, so historical cases do not change meaning", () => {
    expect(PROBABILITY_PHRASES.map((b) => b.threshold)).toEqual([0.9, 0.7, 0.55, 0.45, 0.3, 0.1, 0]);
    expect(CONFIDENCE_BANDS.map((b) => b.threshold)).toEqual([0.85, 0.65, 0.45, 0.25, 0]);
    expect(SOURCE_GRADES.map((b) => b.label)).toEqual(["A", "B", "C", "D", "F"]);
  });

  it("orders every band high to low, which the lookup depends on", () => {
    for (const bands of [PROBABILITY_PHRASES, CONFIDENCE_BANDS, SOURCE_GRADES]) {
      const thresholds = bands.map((b) => b.threshold);
      expect([...thresholds].sort((a, b) => b - a)).toEqual(thresholds);
      expect(thresholds[thresholds.length - 1]).toBe(0);
    }
  });

  it("hardcodes no phrase in a component", () => {
    const encoding = encodeProbability({ method: "m", point: 0.95 });
    expect(encoding.kind === "range" && encoding.phrase).toBe("Very likely");
  });
});

// ── Expand in place ──────────────────────────────────────────────────────────

describe("Why", () => {
  it("reveals support inline and returns focus on collapse", async () => {
    // A reader who opens support for a mid-paragraph claim and is dropped at the
    // top of the document has lost the place this exists to keep.
    withRouter(<Why subject="this claim" citations={["E-001", "E-002"]} />);
    const toggle = screen.getByRole("button", { name: /Why\? for this claim/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(toggle);
    expect(screen.getByText("E-001")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Hide support/ })).toHaveAttribute(
      "aria-expanded",
      "true",
    );

    await userEvent.click(screen.getByRole("button", { name: /Hide support/ }));
    expect(screen.queryByText("E-001")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Why\?/ })).toHaveFocus();
  });

  it("shows how an estimate moved, which is otherwise invisible", async () => {
    withRouter(
      <Why
        subject="62%"
        adjustments={[{ reason: "base rate from 12 comparable cases", delta: 0.08 }]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /Why\?/ }));
    expect(screen.getByText(/base rate from 12 comparable cases/)).toBeInTheDocument();
    expect(screen.getByText(/\+8 points/)).toBeInTheDocument();
  });

  it("is no control at all when there is nothing to show", () => {
    // A disclosure that opens onto an empty body teaches people not to open it.
    const { container } = withRouter(<Why subject="nothing" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("appears on a probability that has adjustments", async () => {
    withRouter(
      <ProbabilityBand
        label="positive return"
        probability={{ method: "reference_class", point: 0.62, adjustments: [{ reason: "moved" }] }}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /Why\?/ }));
    expect(screen.getByText("moved")).toBeInTheDocument();
  });
});
