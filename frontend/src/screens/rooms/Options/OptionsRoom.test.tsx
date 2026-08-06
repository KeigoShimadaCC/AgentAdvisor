import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { OptionsRoom } from "./OptionsRoom";
import { makeOptionsACHFixture, makeOptionsFixture } from "../fixtures";
import type { CaseView } from "../../../generated/case_view";

const { mocks } = vi.hoisted(() => ({
  mocks: {
    getCaseView: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
  },
}));

vi.mock("../../../api/client", () => ({
  api: { getCaseView: mocks.getCaseView },
}));

vi.mock("../../../api/sse", () => ({
  SSEClient: class {
    connect() { mocks.connect(); }
    disconnect() { mocks.disconnect(); }
  },
}));

function renderRoom(fixture: CaseView) {
  mocks.getCaseView.mockResolvedValue(fixture);
  return render(
    <MemoryRouter initialEntries={["/cases/case-1/rooms/options"]}>
      <Routes>
        <Route path="/cases/:caseId/rooms/options" element={<OptionsRoom />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Options room", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("groups duplicate ranks as equal", async () => {
    renderRoom(makeOptionsFixture());
    expect(await screen.findByText("Buy the ETF")).toBeInTheDocument();
    // Two options share rank 2 -> "Equal rank" marker.
    expect(screen.getByText("Equal rank")).toBeInTheDocument();
  });

  it("anchors the recommended row at rank 1", async () => {
    renderRoom(makeOptionsFixture());
    expect(await screen.findByText("Buy the ETF")).toBeInTheDocument();
    expect(screen.getByText("Recommended")).toBeInTheDocument();
  });

  it("renders the eliminated-option coda with its reason", async () => {
    renderRoom(makeOptionsFixture());
    expect(await screen.findByText("Eliminated options")).toBeInTheDocument();
    const coda = screen.getByText("Eliminated options").closest(".eliminated-coda") as HTMLElement;
    expect(within(coda).getByText(/does not meet the semiconductor-exposure objective/)).toBeInTheDocument();
  });

  it("shows EV bars where expected values exist", async () => {
    renderRoom(makeOptionsFixture());
    expect(await screen.findByText("Buy the ETF")).toBeInTheDocument();
    // The modeled badge appears for options with an expected value.
    expect(screen.getAllByText("modeled").length).toBeGreaterThan(0);
  });

  it("keeps an eliminated option out of the ranked list", async () => {
    renderRoom(makeOptionsFixture());
    expect(await screen.findByText("Buy the ETF")).toBeInTheDocument();

    const ranked = screen.getByLabelText("Ranked options");
    expect(within(ranked).queryByText("Do nothing")).not.toBeInTheDocument();
    // It is still reported, once, in the coda.
    expect(screen.getAllByText("Do nothing")).toHaveLength(1);
  });

  it("trusts the projection flag rather than the wording of the rationale", async () => {
    // A rationale that never says "eliminated" but is flagged must still be
    // treated as eliminated, and one that merely mentions the word must not.
    const fixture = makeOptionsFixture();
    const options = fixture.rooms!.options!.options!;
    options[3].rationale = "Ruled out: the capital is committed elsewhere.";
    options[1].rationale = "We did not eliminate this; it stays under consideration.";

    renderRoom(fixture);
    expect(await screen.findByText("Buy the ETF")).toBeInTheDocument();

    const coda = screen.getByText("Eliminated options").closest(".eliminated-coda") as HTMLElement;
    expect(within(coda).getByText(/capital is committed elsewhere/)).toBeInTheDocument();

    const ranked = screen.getByLabelText("Ranked options");
    expect(within(ranked).getByText("Buy the single stock")).toBeInTheDocument();
  });

  it("renders the empty state without evaluating ranking data", async () => {
    // A live run opens this room before any ranking exists. Every hook is
    // declared above this return so the later populated render keeps the same
    // hook count; see the comment in OptionsBody.
    const empty = makeOptionsFixture();
    empty.rooms!.options = { options: [], ev_table: {} };

    renderRoom(empty);
    expect(await screen.findByText(/not yet/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Ranked options")).not.toBeInTheDocument();
    expect(screen.queryByText("Eliminated options")).not.toBeInTheDocument();
  });

  it("renders the competing-hypotheses exhibit, least disconfirmed first", async () => {
    renderRoom(makeOptionsACHFixture());

    const exhibit = await screen.findByLabelText("Competing hypotheses");
    const rows = within(exhibit).getAllByRole("row");
    // Header + three scored options; the eliminated one has no standing.
    expect(rows).toHaveLength(4);
    expect(within(rows[1]).getByText("Buy the ETF")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Wait for earnings")).toBeInTheDocument();
    expect(within(rows[3]).getByText("Buy the single stock")).toBeInTheDocument();
    expect(within(rows[1]).getByText("0.15")).toBeInTheDocument();
    // Records against are inspectable citations, not bare text.
    expect(
      within(rows[3]).getByRole("button", { name: "Inspect record E-2" }),
    ).toBeInTheDocument();
  });

  it("badges the least-disconfirmed option without disturbing the director's ranking", async () => {
    renderRoom(makeOptionsACHFixture());
    const ranked = await screen.findByLabelText("Ranked options");
    await within(ranked).findByText("Buy the ETF");

    // The ETF is both the director's pick and the least disconfirmed here;
    // the two readings sit side by side on the same row.
    const row = within(ranked).getByText("Buy the ETF").closest(".option-row") as HTMLElement;
    expect(within(row).getByText("least disconfirmed")).toBeInTheDocument();
    expect(screen.getByText("Recommended")).toBeInTheDocument();
    // Exactly one option can hold the badge.
    expect(screen.getAllByText("least disconfirmed")).toHaveLength(1);
  });

  it("names the evidence that could not have changed the reading", async () => {
    renderRoom(makeOptionsACHFixture());
    const exhibit = await screen.findByLabelText("Competing hypotheses");
    expect(
      within(exhibit).getByText(/could not have changed this reading/),
    ).toBeInTheDocument();
    expect(
      within(exhibit).getByRole("button", { name: "Inspect record E-3" }),
    ).toBeInTheDocument();
  });

  it("omits the exhibit when no matrix was built", async () => {
    const fixture = makeOptionsFixture();
    const room = fixture.rooms!.options!;
    room.ach_scored = false;
    room.ach_uninformative_evidence_ids = [];
    for (const o of room.options!) {
      delete o.disconfirmation_rank;
      delete o.disconfirming_weight;
      delete o.disconfirming_evidence_ids;
    }

    renderRoom(fixture);
    expect(await screen.findByText("Buy the ETF")).toBeInTheDocument();
    expect(screen.queryByLabelText("Competing hypotheses")).not.toBeInTheDocument();
    expect(screen.queryByText("least disconfirmed")).not.toBeInTheDocument();
  });
});
