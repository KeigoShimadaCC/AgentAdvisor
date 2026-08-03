/**
 * Terminology lexicon for the commissioning and scope-checkpoint screens.
 *
 * All user-facing copy that describes an internal stage, role, enum, or
 * schema field must be sourced from these tables so that no raw
 * CaseStage, TaskRole, or artifact field name ever appears in the
 * rendered DOM (SPEC-034 acceptance criterion).
 *
 * Keep keys stable; they are the contract between the UI and the
 * terminology tables.  Values are the only thing that may change.
 */

// ── Effort / depth profiles (SPEC-029) ──────────────────────────────────────

export type EffortKey = "quick" | "standard" | "deep";

export interface EffortDescriptor {
  /** Human label shown on the selector chip. */
  label: string;
  /** Honest wall-clock time range the user should expect. */
  timeRange: string;
  /** The value sent to the backend ``effort`` field. */
  backendValue: string;
  /** One-line description of what this depth buys. */
  blurb: string;
}

export const EFFORT_PROFILES: Record<EffortKey, EffortDescriptor> = {
  quick: {
    label: "Quick look",
    timeRange: "a few minutes",
    backendValue: "light",
    blurb: "Frames the decision and checks the obvious risks. Good for a first read.",
  },
  standard: {
    label: "Standard",
    timeRange: "roughly 10–20 minutes",
    backendValue: "default",
    blurb: "Frames, researches, challenges, and synthesizes — the default consulting pass.",
  },
  deep: {
    label: "Deep dive",
    timeRange: "30 minutes or more",
    backendValue: "deep",
    blurb: "Wider evidence search, more scenarios, and a second challenger pass.",
  },
};

export const DEFAULT_EFFORT: EffortKey = "standard";

// ── Example chips (benchmark domains) ───────────────────────────────────────

export interface ExampleChip {
  /** Short label on the chip. */
  label: string;
  /** The prompt inserted into the textarea when the chip is picked. */
  prompt: string;
}

export const EXAMPLE_CHIPS: ExampleChip[] = [
  {
    label: "Investment",
    prompt:
      "I have $50,000 and want semiconductor exposure. Should I buy a single stock now, wait for earnings, or use a broad ETF? I can tolerate volatility but not a permanent loss that sets back my house down-payment plan.",
  },
  {
    label: "Career",
    prompt:
      "I earn $180,000 at a stable big-tech role. I have an offer from a Series B startup at $140,000 base plus 0.5% equity. Should I switch now, negotiate, or stay 12–18 months first?",
  },
  {
    label: "Technology adoption",
    prompt:
      "Our 10-person startup needs a customer analytics dashboard this quarter. Should we build it in-house, buy a SaaS platform, or stage a hybrid migration? Account for total cost, delivery risk, and roadmap impact.",
  },
  {
    label: "Hiring",
    prompt:
      "We need a senior engineer. Should we hire a full-time employee, bring on a contractor for six months, or promote from within? Compare cost, ramp time, and retention risk.",
  },
  {
    label: "Make vs buy",
    prompt:
      "We need a billing system. Building it costs about four months of engineering; buying costs $3,000/month with vendor lock-in. Should we build, buy, or do a staged migration?",
  },
];

// ── Method promise + disclaimer ─────────────────────────────────────────────

export const METHOD_PROMISE =
  "It frames your decision, gathers evidence, challenges its own thinking, and returns a recommendation with explicit uncertainty — so you can see how it got there.";

export const NOT_LICENSED_ADVICE =
  "This is decision support, not licensed financial, legal, or medical advice. Confirm consequential choices with a qualified professional.";

// ── Needs-you states (CaseView.needs_you) ───────────────────────────────────

export type NeedsYouKey =
  | "scope_checkpoint"
  | "delivery_checkpoint"
  | "interrupted"
  | "none";

export interface NeedsYouDescriptor {
  /** Short badge label. */
  badge: string;
  /** The consequence-of-doing-nothing line (report §13.4). */
  consequence: string;
  /** Where the user should go. */
  action: string;
}

export const NEEDS_YOU: Record<NeedsYouKey, NeedsYouDescriptor> = {
  scope_checkpoint: {
    badge: "Needs your review",
    consequence:
      "This decision is paused at the scope sheet until you review and sign it. It will not proceed on its own.",
    action: "Review the scope sheet",
  },
  delivery_checkpoint: {
    badge: "Ready for you",
    consequence:
      "The analysis is complete and waiting for you to accept or request changes. It will not act without you.",
    action: "Review the recommendation",
  },
  interrupted: {
    badge: "Interrupted",
    consequence:
      "This case stopped before finishing. Open it to see what happened.",
    action: "Open the case",
  },
  none: {
    badge: "",
    consequence: "",
    action: "",
  },
};

// ── Stage → human label (library + headers) ─────────────────────────────────

const STAGE_LABELS: Record<string, string> = {
  intake: "Reading your question",
  framing: "Framing the decision",
  awaiting_framing_approval: "Waiting for your review",
  structuring: "Structuring the investigation",
  provisional_thesis: "Drafting a provisional view",
  planning: "Planning the research",
  investigation: "Investigating",
  evidence_critique: "Critiquing the evidence",
  assumption_ledger: "Recording assumptions",
  preliminary_recommendation: "Drafting a recommendation",
  pre_mortem: "Stress-testing the recommendation",
  challenge: "Challenging the reasoning",
  repair: "Revising after challenge",
  stop_decision: "Deciding whether to stop",
  synthesis: "Synthesizing",
  review: "Reviewing the synthesis",
  awaiting_final_approval: "Ready for your review",
  done: "Complete",
  failed: "Stopped",
};

export function stageLabel(stage: string): string {
  return STAGE_LABELS[stage] ?? "In progress";
}

// ── Intake field → human label (clarification cards, ground rules) ──────────

const INTAKE_FIELD_LABELS: Record<string, string> = {
  decision_question: "the decision to make",
  deadline: "your deadline",
  alternatives_mentioned: "the options you are considering",
  objectives: "what a good outcome looks like",
  constraints: "your constraints",
  risk_tolerance: "how much risk you can accept",
  reversibility: "how reversible the decision is",
  depth: "how deep to go",
};

export function intakeFieldLabel(field: string): string {
  return INTAKE_FIELD_LABELS[field] ?? field;
}

// ── Risk tolerance ──────────────────────────────────────────────────────────

const RISK_TOLERANCE_LABELS: Record<string, string> = {
  low: "Cautious — protect the downside",
  moderate: "Balanced — accept measured risk",
  high: "Growth-oriented — reach for upside",
};

export function riskToleranceLabel(value: string | null | undefined): string {
  if (!value) return "Not set";
  return RISK_TOLERANCE_LABELS[value] ?? value;
}

// ── Reversibility ───────────────────────────────────────────────────────────

const REVERSIBILITY_LABELS: Record<string, string> = {
  fully_reversible: "Fully reversible — you can change course easily",
  partially_reversible: "Partially reversible — some costs are sunk",
  irreversible: "Hard to reverse — treat as a one-way door",
};

export function reversibilityLabel(value: string | null | undefined): string {
  if (!value) return "Not set";
  return REVERSIBILITY_LABELS[value] ?? value;
}

// ── Option origin marks ─────────────────────────────────────────────────────

export type OptionOrigin = "yours" | "added-by-analysis";

export const OPTION_ORIGIN_LABELS: Record<OptionOrigin, string> = {
  yours: "Your option",
  "added-by-analysis": "Added by analysis",
};

// ── Scope-sheet section copy ────────────────────────────────────────────────

export const SCOPE_COPY = {
  restatementTitle: "Here is what I understood",
  restatementHelp: "Edit the wording so it matches what you actually want decided.",
  optionsTitle: "Options on the table",
  optionsHelp:
    "These are the alternatives I will compare. Remove any that don't belong, annotate them, or add a missing one.",
  outlineTitle: "What I will investigate",
  outlineHelp:
    "The broad questions I plan to answer. Strike through any you do not want me to spend time on.",
  outlineFidelityNote:
    "This is the planned set of questions, not a final task tree. The full investigation plan appears once framing is signed.",
  groundRulesTitle: "Ground rules",
  groundRulesHelp:
    "Confirm each of these so I work within your real constraints. Items I filled in because you skipped them are marked and editable.",
  effortTitle: "Effort and limits",
  whatItCantDoTitle: "What this will not do",
  signatureTitle: "Your signature",
  signButton: "Sign and begin",
  signHelp:
    "Signing records your consent and starts the investigation. This becomes a permanent part of the case record.",
  saveLaterButton: "Save and decide later",
  saveLaterHelp:
    "Parks the decision here. Nothing runs until you come back and sign.",
  declaredAssumptionLabel: "Assumed because you skipped it",
  assumedEditableNote: "You can edit this before signing.",
} as const;

// ── Ground-rule item keys ───────────────────────────────────────────────────

export const GROUND_RULE_KEYS = {
  deadline: "deadline",
  riskTolerance: "risk_tolerance",
  reversibility: "reversibility",
} as const;

export const GROUND_RULE_LABELS: Record<string, string> = {
  deadline: "Deadline",
  risk_tolerance: "Risk tolerance",
  reversibility: "Reversibility",
};

// ── Effort & limits disclosure ──────────────────────────────────────────────

export const EFFORT_LIMITS_INTRO =
  "Here is what this pass will and will not do, so you know what you are signing up for.";

export const WHAT_IT_CAN_DO: string[] = [
  "Frame the decision and compare the options you gave it.",
  "Gather evidence and weigh it, including its independence and reliability.",
  "Stress-test its own reasoning with a challenger and a pre-mortem pass.",
  "Return a recommendation with explicit uncertainty, not a single certain answer.",
];

export const WHAT_IT_CANT_DO: string[] = [
  "It will not execute any transaction, send money, or contact anyone on your behalf.",
  "It will not give licensed financial, legal, or medical advice.",
  "It cannot access your private accounts, documents, or credentials.",
  "It will not keep running after it delivers its recommendation — you decide what to do.",
];

// ── Signed-record copy ──────────────────────────────────────────────────────

export const SIGNED_COPY = {
  title: "Scope signed",
  signedBy: "Signed by",
  signedAt: "Signed at",
  summaryHash: "Sheet hash",
  confirmations: "Confirmed ground rules",
  whatChanged: "What changed since the last revision",
  noChanges: "No changes — this was a clean sign.",
  backToCase: "Back to the case",
} as const;
