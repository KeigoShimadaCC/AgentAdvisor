/**
 * Who is speaking (SPEC-049).
 *
 * Thirteen roles work a case, two Directors run on deliberately different model
 * families so that their agreement carries information, and a third reviewer on
 * a third family can block delivery outright. In the UI before this file, an
 * agent was named in exactly two places, and `BriefBlock.provenance` — which is
 * the north star's own "sourced fact vs interpretation vs assumption" division —
 * rendered as a grey uppercase enum.
 *
 * A table rather than a formatter, because exhaustiveness is then checkable:
 * `voices.test.ts` reads the enums out of the Python source and fails on any
 * value without an entry here. That is what stops a new role or provenance from
 * regressing the UI into rendering `assumption_analyst` at a reader.
 */

export interface Voice {
  /** What the reader sees. */
  label: string;
  /** One line on what this voice is *for*, used as a title and in help text. */
  blurb: string;
}

// ── Roles ────────────────────────────────────────────────────────────────────
//
// Keys are `TaskRole` values from orchestrator/artifacts/common.py, plus the
// synthetic actors the audit stream emits (director_framing, director_b,
// independent_reviewer, orchestrator) which are not TaskRole members but do
// appear as `actor` on events.

export const ROLE_VOICES: Record<string, Voice> = {
  intake: {
    label: "Intake",
    blurb: "Reads your question and records what you actually asked for.",
  },
  planner: {
    label: "Planning",
    blurb: "Breaks the decision into the questions that have to be answered.",
  },
  director: {
    label: "The Director",
    blurb: "Decides what the case does next, and when it has done enough.",
  },
  director_framing: {
    label: "Framing",
    blurb: "Turns your question into a decision with alternatives and criteria.",
  },
  director_b: {
    label: "The second Director",
    blurb:
      "Runs the same decisions on a different model family. Agreement between the two is evidence; disagreement is reported, never averaged.",
  },
  structurer: {
    label: "Structuring",
    blurb: "Lays out the alternatives and the criteria they are judged on.",
  },
  challenger: {
    label: "The Challenger",
    blurb: "Argues against the emerging recommendation, on the record.",
  },
  premortem: {
    label: "Pre-mortem",
    blurb: "Assumes the decision failed, and works backwards to why.",
  },
  auditor: {
    label: "The Auditor",
    blurb: "Checks the evidence for reliability, directness and independence.",
  },
  researcher: {
    label: "Research",
    blurb: "Gathers the evidence and records where each piece came from.",
  },
  analyst: {
    label: "Analysis",
    blurb: "Works the numbers: scenarios, expected value, sensitivity.",
  },
  assumption_analyst: {
    label: "Assumptions",
    blurb: "Names what the recommendation is resting on that was not proven.",
  },
  ach: {
    label: "Competing hypotheses",
    blurb:
      "Ranks the alternatives by what the evidence fails to rule out, rather than by what supports them.",
  },
  monitor: {
    label: "Monitoring",
    blurb: "Sets out what to watch after the decision, and what would change it.",
  },
  synthesizer: {
    label: "Synthesis",
    blurb: "Writes the brief from everything the case produced.",
  },
  reviewer: {
    label: "Review",
    blurb: "Checks the brief for defects: citations that do not resolve, claims that overreach.",
  },
  independent_reviewer: {
    label: "The independent reviewer",
    blurb:
      "Sees the conclusion and the raw evidence, but not the reasoning that produced it, and answers one question: would you reach this conclusion from this evidence?",
  },
  specialist: {
    label: "A specialist",
    blurb: "Brought in for a question the standing roles are not equipped to answer.",
  },
  orchestrator: {
    label: "The orchestrator",
    blurb: "Runs the case: gates, retries, and the order of work.",
  },
};

const UNKNOWN_ROLE: Voice = {
  label: "The system",
  blurb: "An actor with no voice of its own.",
};

export function roleVoice(role: string | null | undefined): Voice {
  if (!role) return UNKNOWN_ROLE;
  return ROLE_VOICES[role] ?? { label: role.replace(/_/g, " "), blurb: "" };
}

/** The display name alone, which is what most call sites want. */
export function voiceFor(role: string | null | undefined): string {
  return roleVoice(role).label;
}

// ── Provenance ───────────────────────────────────────────────────────────────
//
// North star Section 15 requires the interface to distinguish sourced facts,
// agent interpretation, user-supplied information, assumptions, calculations
// and recommendations. These are those six, said as voices rather than as
// field values.

export const PROVENANCE_VOICES: Record<string, Voice> = {
  sourced_fact: {
    label: "From a source",
    blurb: "Taken from a named piece of evidence, not inferred.",
  },
  interpretation: {
    label: "Read of the evidence",
    blurb: "An agent's judgement about what the evidence means. It could be wrong.",
  },
  user_input: {
    label: "From you",
    blurb: "Something you told the case. It was taken as given, not verified.",
  },
  assumption: {
    label: "Assumed",
    blurb: "Not established. The recommendation rests on it being true.",
  },
  calculation: {
    label: "Calculated",
    blurb: "Derived arithmetically from stated inputs.",
  },
  recommendation: {
    label: "The recommendation",
    blurb: "What the case advises, and the thing everything else is here to support.",
  },
};

const UNKNOWN_PROVENANCE: Voice = {
  label: "Unattributed",
  blurb: "This line carries no provenance, which is itself worth knowing.",
};

export function provenanceVoice(provenance: string | null | undefined): Voice {
  if (!provenance) return UNKNOWN_PROVENANCE;
  return PROVENANCE_VOICES[provenance] ?? UNKNOWN_PROVENANCE;
}

// ── Source types ─────────────────────────────────────────────────────────────
//
// `user_document` (SPEC-043) is the one that matters here: a document you
// dropped in, or your own answer to an intake question. It is direct and often
// decisive, and it is never independent corroboration for anything — so it has
// to read as your voice rather than as a research finding.

export const SOURCE_VOICES: Record<string, Voice> = {
  regulatory_filing: { label: "Regulatory filing", blurb: "Filed with a regulator." },
  official_statistic: { label: "Official statistic", blurb: "Published by a statistical agency." },
  law_or_standard: { label: "Law or standard", blurb: "The text of a rule." },
  original_research: { label: "Original research", blurb: "First-hand study." },
  reputable_secondary: { label: "Reputable secondary", blurb: "Reporting on a primary source." },
  specialist_reporting: { label: "Specialist reporting", blurb: "Trade or domain press." },
  user_document: {
    label: "Your own document",
    blurb:
      "You supplied this. It is direct and usually decisive, and it can never corroborate anything else — it is one voice, yours, counted once.",
  },
  other: { label: "Other", blurb: "Not one of the recognised source kinds." },
};

export function sourceVoice(sourceType: string | null | undefined): Voice {
  if (!sourceType) return { label: "Unclassified", blurb: "" };
  return SOURCE_VOICES[sourceType] ?? { label: sourceType.replace(/_/g, " "), blurb: "" };
}
