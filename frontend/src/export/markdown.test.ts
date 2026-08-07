import { describe, it, expect } from "vitest";
import { exportMarkdown, exportFilename, citationIds, CANONICAL_SECTION_ORDER } from "./markdown";
import type { CaseView } from "../generated/case_view";

function view(overrides: Partial<CaseView> = {}): CaseView {
  return {
    case_id: "case-001-fixture-001",
    decision_question: "Should I invest $50k in Nvidia vs a semiconductor ETF?",
    phase: "complete",
    stage: "done",
    is_terminal: true,
    needs_you: "none",
    effort: { wall_clock_s: 5400, invocation_attempts: 17, total_tokens: 1_540_000 },
    brief_sections: [
      // Deliberately out of canonical order, to prove the exporter reorders.
      {
        key: "key_reasons",
        status: "final",
        blocks: [
          { provenance: "interpretation", text: "Valuation is above average.", citation_ids: ["E-001"] },
          { provenance: "interpretation", text: "Growth justifies it.", citation_ids: ["E-002", "E-001"] },
        ],
      },
      {
        key: "executive_recommendation",
        status: "final",
        blocks: [{ provenance: "recommendation", text: "Invest via staged entry.", citation_ids: [] }],
      },
      { key: "limitations", status: "not_assessed", blocks: [] },
      { key: "premortem", status: "pending", blocks: [] },
    ],
    ...overrides,
  } as CaseView;
}

describe("the exported document", () => {
  it("is byte-identical for the same case", () => {
    // Determinism is what makes an export citable. No clock, no locale, no
    // iteration over an unordered map.
    expect(exportMarkdown(view())).toBe(exportMarkdown(view()));
  });

  it("leads with the decision question, not the case id", () => {
    expect(exportMarkdown(view()).split("\n")[0]).toBe(
      "# Should I invest $50k in Nvidia vs a semiconductor ETF?",
    );
  });

  it("walks the projection in canonical order, whatever order the sections arrive in", () => {
    const md = exportMarkdown(view());
    const recommendation = md.indexOf("## Executive recommendation");
    const reasons = md.indexOf("## Key reasons");
    const premortem = md.indexOf("## Pre-mortem");
    expect(recommendation).toBeGreaterThan(-1);
    expect(recommendation).toBeLessThan(reasons);
    expect(reasons).toBeLessThan(premortem);
  });

  it("contains every citation id in the projection", () => {
    const v = view();
    const md = exportMarkdown(v);
    const ids = citationIds(v);
    expect(ids).toEqual(["E-001", "E-002"]);
    for (const id of ids) {
      expect(md, `citation ${id} missing from the export`).toContain(id);
    }
  });

  it("carries provenance as voices, not as raw enums", () => {
    const md = exportMarkdown(view());
    expect(md).toContain("**The recommendation.**");
    expect(md).toContain("**Read of the evidence.**");
    expect(md).not.toContain("interpretation.");
  });

  it("keeps a pending or not-assessed section rather than silently dropping it", () => {
    // An export that omits a section is worse than one that says the section
    // did not run: the reader cannot tell the difference from absence.
    const md = exportMarkdown(view());
    expect(md).toContain("## Pre-mortem");
    expect(md).toContain("_Not yet — this part of the case had not run._");
    expect(md).toContain("## What this could not assess");
    expect(md).toContain("_Not assessed for this case._");
  });

  it("keeps a section the canonical order has never heard of", () => {
    const md = exportMarkdown(
      view({
        brief_sections: [
          { key: "a_new_section", status: "final", blocks: [{ provenance: "interpretation", text: "New." }] },
          { key: "executive_recommendation", status: "final", blocks: [{ provenance: "recommendation", text: "Go." }] },
        ],
      } as Partial<CaseView>),
    );
    expect(md).toContain("a_new_section");
    // And it goes last rather than first.
    expect(md.indexOf("## Executive recommendation")).toBeLessThan(md.indexOf("a_new_section"));
  });

  it("says on its face when the case had not finished", () => {
    // Otherwise it reads as final in an inbox three weeks later.
    const md = exportMarkdown(view({ is_terminal: false, stage: "investigation" }));
    expect(md).toContain("**This case had not finished when this was exported.**");
    expect(exportMarkdown(view())).not.toContain("had not finished");
  });

  it("carries the dissent, so the document is no more confident than the case was", () => {
    const md = exportMarkdown(
      view({
        rooms: {
          challenges: {
            objections: [],
            track_divergence: {
              stage: "preliminary_recommendation",
              agreement: false,
              divergence_summary: "The tracks disagree on timing.",
              reconciled_alternative: null,
              positions: [
                { track_id: "director", preferred_alternative: "Enter now" },
                { track_id: "director_b", preferred_alternative: "Stage the entry" },
              ],
            },
          },
        },
      } as Partial<CaseView>),
    );
    expect(md).toContain("## The two Directors disagreed");
    expect(md).toContain("Enter now");
    expect(md).toContain("Stage the entry");
    expect(md).toContain("_These positions were not averaged._");
  });

  it("omits the dissent section when the tracks agreed", () => {
    const md = exportMarkdown(
      view({
        rooms: {
          challenges: {
            objections: [],
            track_divergence: {
              stage: "preliminary_recommendation",
              agreement: true,
              divergence_summary: "Both tracks agreed.",
              reconciled_alternative: null,
              positions: [],
            },
          },
        },
      } as Partial<CaseView>),
    );
    expect(md).not.toContain("disagreed");
  });

  it("records the effort the case actually cost", () => {
    const md = exportMarkdown(view());
    expect(md).toContain("1h 30m");
    expect(md).toContain("17 agent calls");
    expect(md).toContain("1540k tokens");
  });

  it("states what it is and is not", () => {
    expect(exportMarkdown(view())).toContain("analysis, not licensed advice");
  });

  it("names the file after the case, without a clock", () => {
    expect(exportFilename(view())).toBe("case-001-fixture-001.md");
    expect(exportFilename(view())).toBe(exportFilename(view()));
  });

  it("survives a case with no brief at all", () => {
    const md = exportMarkdown(view({ brief_sections: [] }));
    expect(md).toContain("# Should I invest");
    expect(citationIds(view({ brief_sections: [] }))).toEqual([]);
  });
});

describe("the canonical order", () => {
  it("leads with the recommendation and its confidence", () => {
    expect(CANONICAL_SECTION_ORDER.slice(0, 2)).toEqual([
      "executive_recommendation",
      "decision_confidence",
    ]);
  });

  it("has no duplicates, which would make the sort unstable", () => {
    expect(new Set(CANONICAL_SECTION_ORDER).size).toBe(CANONICAL_SECTION_ORDER.length);
  });
});
