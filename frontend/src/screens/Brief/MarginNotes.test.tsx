import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { InspectorContext } from "../inspector/inspectorContext";
import { MarginNotes, placeObjections, targetSectionKey } from "./MarginNotes";
import type { ObjectionView } from "../../generated/case_view";

function objection(overrides: Partial<ObjectionView> = {}): ObjectionView {
  return {
    objection_id: "O-001",
    target_section: "key_reasons",
    claim: "The growth premium is not supported by the filings.",
    materiality: "high",
    resolution_status: "open",
    reasoning: "Two of the three cited sources are the same press release.",
    ...overrides,
  } as ObjectionView;
}

function renderNotes(objections: ObjectionView[], unplaced = false) {
  return render(
    <MemoryRouter>
      <InspectorContext.Provider value={{ open: () => {}, close: () => {}, openId: null }}>
        <MarginNotes objections={objections} unplaced={unplaced} />
      </InspectorContext.Provider>
    </MemoryRouter>,
  );
}

describe("placing an objection against what it attacks", () => {
  it("reads the section out of a path with an index", () => {
    expect(targetSectionKey("key_reasons[0]")).toBe("key_reasons");
    expect(targetSectionKey("premortem.failure_modes")).toBe("premortem");
    expect(targetSectionKey("executive_recommendation")).toBe("executive_recommendation");
    expect(targetSectionKey(undefined)).toBe("");
  });

  it("groups objections under the section they name", () => {
    const { bySection, unplaced } = placeObjections(
      [
        objection({ objection_id: "O-1", target_section: "key_reasons[0]" }),
        objection({ objection_id: "O-2", target_section: "key_reasons[2]" }),
        objection({ objection_id: "O-3", target_section: "premortem" }),
      ],
      ["key_reasons", "premortem"],
    );
    expect(bySection.get("key_reasons")?.map((o) => o.objection_id)).toEqual(["O-1", "O-2"]);
    expect(bySection.get("premortem")?.map((o) => o.objection_id)).toEqual(["O-3"]);
    expect(unplaced).toEqual([]);
  });

  it("never drops an objection whose target is missing or unknown", () => {
    // The worst possible handling of "the Challenger disagreed and we could not
    // work out where to put it" is to not show it.
    const { bySection, unplaced } = placeObjections(
      [
        objection({ objection_id: "O-1", target_section: "" }),
        objection({ objection_id: "O-2", target_section: "a_section_this_brief_lacks" }),
      ],
      ["key_reasons"],
    );
    expect(bySection.size).toBe(0);
    expect(unplaced.map((o) => o.objection_id)).toEqual(["O-1", "O-2"]);
  });
});

describe("the note itself", () => {
  it("attributes the objection to the Challenger by voice", () => {
    renderNotes([objection()]);
    expect(screen.getByText("The Challenger")).toBeInTheDocument();
  });

  it("distinguishes a live objection from a settled one", () => {
    const { container } = renderNotes([
      objection({ objection_id: "O-1", resolution_status: "open", materiality: "high" }),
      objection({ objection_id: "O-2", resolution_status: "resolved", materiality: "high" }),
      objection({ objection_id: "O-3", resolution_status: "open", materiality: "low" }),
    ]);
    // Live means open *and* high materiality: an open low-materiality note is
    // not a problem with the recommendation.
    expect(container.querySelectorAll(".margin-note-live")).toHaveLength(1);
    expect(container.querySelector(".margin-note-resolved")).not.toBeNull();
  });

  it("carries materiality and status as text, not only as colour", () => {
    renderNotes([objection()]);
    expect(screen.getByText(/high materiality/i)).toBeInTheDocument();
    expect(screen.getByText("Open")).toBeInTheDocument();
  });

  it("says why an unplaced objection is where it is", () => {
    renderNotes([objection({ target_section: "" })], true);
    expect(screen.getByText(/rather than dropped/i)).toBeInTheDocument();
  });

  it("renders nothing at all when there are no objections", () => {
    const { container } = renderNotes([]);
    expect(container).toBeEmptyDOMElement();
  });
});
