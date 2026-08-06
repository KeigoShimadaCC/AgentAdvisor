import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { MemoryRouter } from "react-router-dom";
import { CaseLibrary, groupCases, filterCases } from "./CaseLibrary";
import type { CaseSummary } from "../api/client";

const { mocks } = vi.hoisted(() => ({ mocks: { listCases: vi.fn() } }));

vi.mock("../api/client", () => ({ api: { listCases: mocks.listCases } }));

function summary(overrides: Partial<CaseSummary> = {}): CaseSummary {
  return {
    case_id: "case-001-a",
    stage: "investigation",
    title: "Should we move the warehouse?",
    updated: "2026-08-05T11:20:00Z",
    needs_you: "none",
    ...overrides,
  };
}

function renderLibrary(cases: CaseSummary[]) {
  mocks.listCases.mockResolvedValue(cases);
  return render(
    <MemoryRouter>
      <CaseLibrary />
    </MemoryRouter>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("the client no longer owns a copy of the server's rule", () => {
  it("has no stage-string derivation left in the file", () => {
    // Two implementations of one rule is one implementation and one future bug.
    // The projection already computes needs_you; SPEC-052 deletes the copy.
    // Comments are stripped: the doc comment names what was deleted on
    // purpose, and that record is worth more than a simpler assertion.
    const code = readFileSync(resolve(__dirname, "CaseLibrary.tsx"), "utf8")
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/^\s*\/\/.*$/gm, "");
    expect(code).not.toContain("needsYouFromStage");
    expect(code).not.toContain("awaiting_framing_approval");
    expect(code).not.toContain("awaiting_final_approval");
  });

  it("groups on the server's needs_you, not on the stage", () => {
    // A stage the client has never heard of, with needs_you set: grouping must
    // still be right, which it could not be under a stage-string derivation.
    const groups = groupCases([
      summary({ case_id: "a", stage: "a_brand_new_stage", needs_you: "scope_checkpoint" }),
      summary({ case_id: "b", stage: "investigation", needs_you: "none" }),
      summary({ case_id: "c", stage: "done", needs_you: "none" }),
    ]);
    expect(groups.map((g) => g.key)).toEqual(["waiting", "running", "done"]);
    expect(groups[0].cases.map((c) => c.case_id)).toEqual(["a"]);
    expect(groups[1].cases.map((c) => c.case_id)).toEqual(["b"]);
    expect(groups[2].cases.map((c) => c.case_id)).toEqual(["c"]);
  });

  it("omits a group with nothing in it rather than rendering an empty heading", () => {
    const groups = groupCases([summary({ needs_you: "none", stage: "done" })]);
    expect(groups.map((g) => g.key)).toEqual(["done"]);
  });

  it("counts a failed case as finished, not as running", () => {
    const groups = groupCases([summary({ stage: "failed", needs_you: "none" })]);
    expect(groups[0].key).toBe("done");
  });
});

describe("search", () => {
  const cases = [
    summary({ case_id: "case-001-a", title: "Should we move the warehouse?" }),
    summary({ case_id: "case-002-b", title: "Take the Series B term sheet?" }),
  ];

  it("matches the question, which is what a user would type", () => {
    expect(filterCases(cases, "warehouse").map((c) => c.case_id)).toEqual(["case-001-a"]);
  });

  it("ignores case and surrounding whitespace", () => {
    expect(filterCases(cases, "  SERIES b ").map((c) => c.case_id)).toEqual(["case-002-b"]);
  });

  it("also matches the case id, for someone pasting one from a link", () => {
    expect(filterCases(cases, "case-002").map((c) => c.case_id)).toEqual(["case-002-b"]);
  });

  it("returns everything for an empty query rather than nothing", () => {
    expect(filterCases(cases, "   ")).toHaveLength(2);
  });
});

describe("the library screen", () => {
  it("leads each card with the decision question", async () => {
    renderLibrary([summary()]);
    expect(await screen.findByText("Should we move the warehouse?")).toBeInTheDocument();
  });

  it("puts what a case needs, and its consequence, on the card", async () => {
    renderLibrary([summary({ needs_you: "scope_checkpoint", stage: "awaiting_framing_approval" })]);
    const waiting = await screen.findByLabelText("Waiting on you");
    expect(within(waiting).getByText("Needs your review")).toBeInTheDocument();
    // The consequence line is what tells a scanning user nothing moves without
    // them; it used to be a page away.
    expect(within(waiting).getByText(/will not proceed on its own/i)).toBeInTheDocument();
  });

  it("funnels a scope-gated case straight to the scope sheet", async () => {
    renderLibrary([summary({ needs_you: "scope_checkpoint" })]);
    expect(await screen.findByRole("link", { name: /warehouse/ })).toHaveAttribute(
      "href",
      "/cases/case-001-a/scope",
    );
  });

  it("funnels a delivery-gated case to delivery", async () => {
    renderLibrary([summary({ needs_you: "delivery_checkpoint" })]);
    expect(await screen.findByRole("link", { name: /warehouse/ })).toHaveAttribute(
      "href",
      "/cases/case-001-a/delivery",
    );
  });

  it("filters as you type, and says so when nothing matches", async () => {
    renderLibrary([
      summary({ case_id: "case-001-a", title: "Should we move the warehouse?" }),
      summary({ case_id: "case-002-b", title: "Take the Series B term sheet?" }),
    ]);
    await screen.findByText("Should we move the warehouse?");

    await userEvent.type(screen.getByLabelText("Search your decisions"), "warehouse");
    expect(screen.queryByText("Take the Series B term sheet?")).not.toBeInTheDocument();

    await userEvent.clear(screen.getByLabelText("Search your decisions"));
    await userEvent.type(screen.getByLabelText("Search your decisions"), "zzz");
    expect(screen.getByText(/No decision matches/)).toBeInTheDocument();
  });

  it("offers a way to start rather than an empty screen", async () => {
    renderLibrary([]);
    expect(await screen.findByRole("link", { name: "Start a new decision" })).toBeInTheDocument();
  });
});
