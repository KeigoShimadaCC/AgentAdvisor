import { BRIEF_SECTION_TITLES } from "../copy/terms";
import { provenanceVoice } from "../copy/voices";
import type { CaseView, BriefSection } from "../generated/case_view";

/**
 * The brief as an object that can leave the tool (SPEC-052).
 *
 * North star Section 16 defines the recommendation as a package a person
 * receives. A package that cannot be sent to a boss, a co-founder or a board is
 * not one, and until this the only way to receive it was to keep a browser tab
 * open.
 *
 * **Walks the projection, never the DOM.** Two consequences, both load-bearing:
 * the export is byte-identical for the same `CaseView` regardless of what was
 * rendered, altitude or otherwise; and it is testable without a browser. A
 * DOM-scraping exporter would silently omit whatever the current altitude had
 * filtered out — which is the failure mode that makes an export untrustworthy.
 */

/** Sections in the order the brief is read, not the order they were produced. */
export const CANONICAL_SECTION_ORDER: string[] = [
  "executive_recommendation",
  "decision_confidence",
  "key_reasons",
  "alternatives_considered",
  "scenario_analysis",
  "quantitative_findings",
  "strongest_counterarguments",
  "premortem",
  "critical_assumptions",
  "recommendation_change_triggers",
  "independent_review",
  "limitations",
  "next_actions",
  "user_supplied_inputs",
  "budget_depth_stop_disclosure",
  "evidence_and_citations",
];

function orderSections(sections: BriefSection[]): BriefSection[] {
  const rank = new Map(CANONICAL_SECTION_ORDER.map((key, i) => [key, i]));
  // Sections the order does not know about go last, in their own order, rather
  // than being dropped — an export that silently omits a section is worse than
  // one with a section in an unexpected place.
  return [...sections].sort((a, b) => {
    const ra = rank.get(a.key) ?? CANONICAL_SECTION_ORDER.length;
    const rb = rank.get(b.key) ?? CANONICAL_SECTION_ORDER.length;
    return ra - rb;
  });
}

/** Every citation id the projection carries, in first-appearance order. */
export function citationIds(view: CaseView): string[] {
  const seen = new Set<string>();
  const ordered: string[] = [];
  for (const section of orderSections(view.brief_sections ?? [])) {
    for (const block of section.blocks ?? []) {
      for (const id of block.citation_ids ?? []) {
        if (!seen.has(id)) {
          seen.add(id);
          ordered.push(id);
        }
      }
    }
  }
  return ordered;
}

function formatElapsed(seconds: number | null | undefined): string | null {
  if (seconds == null) return null;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

/**
 * Render one case as Markdown.
 *
 * Deterministic: no clock, no locale formatting, no iteration over an unordered
 * map. Two calls with the same view produce the same bytes.
 */
export function exportMarkdown(view: CaseView): string {
  const lines: string[] = [];
  const question = view.decision_question || view.case_id;

  lines.push(`# ${question}`, "");

  // Provenance of the document itself, before its contents: a reader who did
  // not run the case needs to know what produced this and how sure it is.
  lines.push("> Produced by AgentAdvisor. This is analysis, not licensed advice.");
  lines.push(`> Case \`${view.case_id}\` — ${view.is_terminal ? "complete" : "in progress"}.`);
  const elapsed = formatElapsed(view.effort?.wall_clock_s);
  const tokens = view.effort?.total_tokens;
  if (elapsed || tokens) {
    const spend = [
      elapsed,
      view.effort?.invocation_attempts ? `${view.effort.invocation_attempts} agent calls` : null,
      tokens ? `${Math.round(tokens / 1000)}k tokens` : null,
    ]
      .filter(Boolean)
      .join(", ");
    lines.push(`> Effort: ${spend}.`);
  }
  if (!view.is_terminal) {
    // A brief exported mid-run must say so on its face, or it will be read as
    // final in an inbox three weeks later.
    lines.push("> **This case had not finished when this was exported.**");
  }
  lines.push("");

  for (const section of orderSections(view.brief_sections ?? [])) {
    const title = BRIEF_SECTION_TITLES[section.key] ?? section.key;
    lines.push(`## ${title}`);
    if (section.status === "pending") {
      lines.push("", "_Not yet — this part of the case had not run._", "");
      continue;
    }
    if (section.status === "not_assessed") {
      lines.push("", "_Not assessed for this case._", "");
      continue;
    }
    lines.push("");
    for (const block of section.blocks ?? []) {
      const voice = provenanceVoice(block.provenance).label;
      const citations = (block.citation_ids ?? []).map((id) => `[${id}]`).join(" ");
      lines.push(`- **${voice}.** ${block.text}${citations ? ` ${citations}` : ""}`);
    }
    lines.push("");
  }

  const objections = view.rooms?.challenges?.objections ?? [];
  if (objections.length > 0) {
    lines.push("## Objections raised", "");
    for (const objection of objections) {
      lines.push(
        `- **${objection.objection_id}** (${objection.resolution_status}, ${objection.materiality} materiality) — ${objection.claim}`,
      );
    }
    lines.push("");
  }

  const divergence = view.rooms?.challenges?.track_divergence;
  if (divergence && divergence.agreement === false) {
    // Dissent travels with the document. An exported brief that dropped it
    // would be a more confident document than the case actually produced.
    lines.push("## The two Directors disagreed", "");
    lines.push(divergence.divergence_summary, "");
    for (const position of divergence.positions ?? []) {
      lines.push(
        `- **${String(position["track_id"] ?? "track")}**: ${String(position["preferred_alternative"] ?? "—")}`,
      );
    }
    lines.push("", "_These positions were not averaged._", "");
  }

  const ids = citationIds(view);
  if (ids.length > 0) {
    lines.push("## Citations", "");
    for (const id of ids) lines.push(`- ${id}`);
    lines.push("");
  }

  return lines.join("\n");
}

/** A stable, filesystem-safe name. No clock: the same case exports the same name. */
export function exportFilename(view: CaseView): string {
  return `${view.case_id}.md`;
}
