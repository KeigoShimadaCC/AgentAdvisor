import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  readReactions,
  toggleReaction,
  hasReaction,
  clearReactions,
  revisionNoteFrom,
  type Reaction,
} from "./reactions";
import { ReactionControls } from "./ReactionControls";

const wrongAssumption: Reaction = {
  targetId: "A-003",
  targetKind: "assumption",
  kind: "looks_wrong",
  label: "Demand grows 20% a year",
};

const objectionMatters: Reaction = {
  targetId: "O-001",
  targetKind: "objection",
  kind: "matters",
  label: "Staged entry may miss the upside",
};

beforeEach(() => {
  window.localStorage.clear();
});

describe("marking as you read", () => {
  it("survives a reload and is scoped to its case", () => {
    toggleReaction("case-1", wrongAssumption);
    expect(readReactions("case-1")).toHaveLength(1);
    // Another case's marks are another case's.
    expect(readReactions("case-2")).toHaveLength(0);
  });

  it("toggles off when the same mark is clicked again", () => {
    toggleReaction("case-1", wrongAssumption);
    const after = toggleReaction("case-1", wrongAssumption);
    expect(after).toHaveLength(0);
  });

  it("keeps one mark per target, so a record cannot be both wrong and important", () => {
    toggleReaction("case-1", wrongAssumption);
    const after = toggleReaction("case-1", { ...wrongAssumption, kind: "matters" });
    expect(after).toHaveLength(1);
    expect(hasReaction(after, "A-003", "matters")).toBe(true);
    expect(hasReaction(after, "A-003", "looks_wrong")).toBe(false);
  });

  it("returns nothing rather than throwing on a corrupt store", () => {
    window.localStorage.setItem("agentadvisor:reactions:case-1", "{not json");
    expect(readReactions("case-1")).toEqual([]);
  });

  it("clears, which is what spending them at the gate does", () => {
    toggleReaction("case-1", wrongAssumption);
    clearReactions("case-1");
    expect(readReactions("case-1")).toEqual([]);
  });
});

describe("what the marks add up to", () => {
  it("is an empty note when nothing was marked", () => {
    // An empty box, not a heading with nothing under it.
    expect(revisionNoteFrom([])).toBe("");
  });

  it("quotes the claim rather than listing ids, because a synthesizer needs the text", () => {
    const note = revisionNoteFrom([wrongAssumption, objectionMatters]);
    expect(note).toContain("Demand grows 20% a year");
    expect(note).toContain("Staged entry may miss the upside");
  });

  it("separates what looks wrong from what is under-weighted", () => {
    const note = revisionNoteFrom([wrongAssumption, objectionMatters]);
    expect(note).toMatch(/These look wrong to me:[\s\S]*A-003/);
    expect(note).toMatch(/These matter more than the brief gives them:[\s\S]*O-001/);
  });

  it("omits a section it has nothing for", () => {
    const note = revisionNoteFrom([objectionMatters]);
    expect(note).not.toMatch(/look wrong/);
    expect(note).toMatch(/matter more/);
  });
});

describe("the controls", () => {
  it("offers both marks on an assumption and reflects the pressed state", async () => {
    render(
      <ReactionControls
        caseId="case-1"
        targetId="A-003"
        targetKind="assumption"
        label="Demand grows 20% a year"
      />,
    );
    const wrong = screen.getByRole("button", { name: "This looks wrong" });
    expect(wrong).toHaveAttribute("aria-pressed", "false");

    await userEvent.click(wrong);
    expect(wrong).toHaveAttribute("aria-pressed", "true");
    expect(hasReaction(readReactions("case-1"), "A-003", "looks_wrong")).toBe(true);
  });

  it("offers only 'this matters' on an objection", () => {
    render(
      <ReactionControls
        caseId="case-1"
        targetId="O-001"
        targetKind="objection"
        label="An objection"
        kinds={["matters"]}
      />,
    );
    expect(screen.getByRole("button", { name: "This one matters" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "This looks wrong" })).not.toBeInTheDocument();
  });

  it("reads an existing mark on mount rather than starting blank", () => {
    toggleReaction("case-1", wrongAssumption);
    render(
      <ReactionControls
        caseId="case-1"
        targetId="A-003"
        targetKind="assumption"
        label="Demand grows 20% a year"
      />,
    );
    expect(screen.getByRole("button", { name: "This looks wrong" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });
});
