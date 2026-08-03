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

// ── Rooms (SPEC-036) ─────────────────────────────────────────────────────────

export type RoomKey =
  | "sources"
  | "assumptions"
  | "options"
  | "challenges"
  | "plan"
  | "method";

export interface RoomDescriptor {
  /** Tab label shown in the room navigation. */
  label: string;
  /** One-line description of what the room shows. */
  blurb: string;
}

export const ROOMS: Record<RoomKey, RoomDescriptor> = {
  sources: {
    label: "Sources",
    blurb: "Every evidence record, weighed by reliability, directness, and independence.",
  },
  assumptions: {
    label: "Assumptions",
    blurb: "The load-bearing assumptions, with what supports and what cuts against each.",
  },
  options: {
    label: "Options",
    blurb: "The ranked alternatives, with expected value where they were modeled.",
  },
  challenges: {
    label: "Challenges",
    blurb: "Objections, the pre-mortem, and the second-opinion pass — never averaged.",
  },
  plan: {
    label: "Plan",
    blurb: "The question tree that structured the investigation, with coverage.",
  },
  method: {
    label: "Method",
    blurb: "How this case ran: phases, gates, invocations, and the raw audit trail.",
  },
};

export const ROOM_TAB_ORDER: RoomKey[] = [
  "sources",
  "assumptions",
  "options",
  "challenges",
  "plan",
  "method",
];

// ── Level (high / medium / low) ──────────────────────────────────────────────

const LEVEL_LABELS: Record<string, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

export function levelLabel(value: string | null | undefined): string {
  if (!value) return "Not set";
  return LEVEL_LABELS[value] ?? value;
}

// ── Source tier ──────────────────────────────────────────────────────────────

const SOURCE_TIER_LABELS: Record<string, string> = {
  primary: "Primary source",
  official: "Official source",
  reputable: "Reputable secondary",
  weak: "Weak source",
};

export function sourceTierLabel(value: string | null | undefined): string {
  if (!value) return "Ungraded";
  return SOURCE_TIER_LABELS[value] ?? value;
}

// ── Source type ──────────────────────────────────────────────────────────────

const SOURCE_TYPE_LABELS: Record<string, string> = {
  regulatory_filing: "Regulatory filing",
  official_statistic: "Official statistic",
  law_or_standard: "Law or standard",
  original_research: "Original research",
  reputable_secondary: "Reputable secondary source",
  specialist_reporting: "Specialist reporting",
  other: "Other source",
};

export function sourceTypeLabel(value: string | null | undefined): string {
  if (!value) return "Unknown source type";
  return SOURCE_TYPE_LABELS[value] ?? value;
}

// ── Evidence flags ───────────────────────────────────────────────────────────

const EVIDENCE_FLAG_LABELS: Record<string, string> = {
  single_source_cluster: "Single-source cluster",
  stale: "Stale",
  low_directness: "Low directness",
  low_reliability: "Low reliability",
  missing_limitations: "Limitations not stated",
  weak_source_tier: "Weak source tier",
  incentive_conflict: "Incentive conflict",
};

export function evidenceFlagLabel(value: string): string {
  return EVIDENCE_FLAG_LABELS[value] ?? value;
}

// ── Assumption type ──────────────────────────────────────────────────────────

const ASSUMPTION_TYPE_LABELS: Record<string, string> = {
  forecast: "Forecast",
  structural: "Structural",
  operational: "Operational",
  financial: "Financial",
  regulatory: "Regulatory",
  behavioral: "Behavioral",
};

export function assumptionTypeLabel(value: string | null | undefined): string {
  if (!value) return "Unspecified";
  return ASSUMPTION_TYPE_LABELS[value] ?? value;
}

// ── Assumption status ────────────────────────────────────────────────────────

const ASSUMPTION_STATUS_LABELS: Record<string, string> = {
  unresolved: "Unresolved",
  supported: "Supported by evidence",
  contradicted: "Contradicted by evidence",
  retired: "Retired",
};

export function assumptionStatusLabel(value: string | null | undefined): string {
  if (!value) return "Unknown status";
  return ASSUMPTION_STATUS_LABELS[value] ?? value;
}

// ── Objection resolution status ──────────────────────────────────────────────

const OBJECTION_STATUS_LABELS: Record<string, string> = {
  open: "Open",
  partially_resolved: "Partially resolved",
  resolved: "Resolved",
  dismissed: "Dismissed",
};

export function objectionStatusLabel(value: string | null | undefined): string {
  if (!value) return "Unknown status";
  return OBJECTION_STATUS_LABELS[value] ?? value;
}

// Objection status sort order: open first (mirrors the orchestrator rule).
export const OBJECTION_STATUS_SORT: Record<string, number> = {
  open: 0,
  partially_resolved: 1,
  resolved: 2,
  dismissed: 3,
};

// ── Issue node type ──────────────────────────────────────────────────────────

const NODE_TYPE_LABELS: Record<string, string> = {
  root: "Decision question",
  driver: "Driver",
  sub_question: "Sub-question",
};

export function nodeTypeLabel(value: string | null | undefined): string {
  if (!value) return "Node";
  return NODE_TYPE_LABELS[value] ?? value;
}

// ── Authority score → words ──────────────────────────────────────────────────

/** Render the corpus authority mean (0–1) as a short phrase. */
export function authorityWords(score: number | null | undefined): string {
  if (score == null || Number.isNaN(score)) return "Not yet assessed";
  if (score >= 0.75) return "Strong, mostly primary sources";
  if (score >= 0.55) return "Solid, a mix of primary and reputable sources";
  if (score >= 0.35) return "Mixed, leaning on secondary sources";
  return "Weak, mostly thin or indirect sources";
}

// ── Probability phrase ───────────────────────────────────────────────────────

/** Render a point probability (0–1) as a qualitative phrase. */
export function probabilityPhrase(point: number | null | undefined): string {
  if (point == null || Number.isNaN(point)) return "Not estimated";
  if (point >= 0.9) return "Very likely";
  if (point >= 0.7) return "Likely";
  if (point >= 0.55) return "More likely than not";
  if (point >= 0.45) return "Roughly even odds";
  if (point >= 0.3) return "Unlikely";
  if (point > 0.1) return "Quite unlikely";
  return "Very unlikely";
}

/** Render a probability interval as a bracketed range, or empty string. */
export function probabilityRange(
  low: number | null | undefined,
  high: number | null | undefined,
): string {
  if (low == null && high == null) return "";
  const lo = low != null ? `${Math.round(low * 100)}%` : "—";
  const hi = high != null ? `${Math.round(high * 100)}%` : "—";
  return `[${lo}–${hi}]`;
}

// ── Three-truths empty-state vocabulary (report §12.3) ───────────────────────

export type EmptyTruth = "not_yet" | "nothing_found" | "cut_at_limit";

export const EMPTY_TRUTHS: Record<EmptyTruth, string> = {
  not_yet: "Not yet — this part of the case has not run.",
  nothing_found: "Nothing found — the search ran and returned no usable evidence.",
  cut_at_limit: "Cut at limit — this was stopped early to stay within the case budget.",
};

// ── Method room ──────────────────────────────────────────────────────────────

/** Human label for an audit event type, for the Method room event log. */
export function eventTypeLabel(eventType: string): string {
  return EVENT_TYPE_LABELS[eventType] ?? eventType;
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  control_case_created: "Case created",
  control_run_started: "Run started",
  control_run_stopped: "Run stopped",
  control_checkpoint_signed: "Checkpoint signed",
  control_resume_reconciled: "Resume reconciled",
  budget_profile_selected: "Budget profile selected",
  role_invocation_attempt: "Agent invocation",
  stage_completed: "Stage completed",
  stage_gate_evaluated: "Gate evaluated",
  task_started: "Task started",
  task_completed: "Task completed",
  thesis_revision_recorded: "Thesis revised",
  evidence_batch_unpacked: "Evidence gathered",
  objection_batch_unpacked: "Objections unpacked",
  assumption_batch_unpacked: "Assumptions recorded",
  review_evaluated: "Review evaluated",
  stop_decision_evaluated: "Stop decision evaluated",
  dual_track_compared: "Dual-track compared",
  case_recorded_to_memory: "Case recorded to memory",
  case_finalized: "Case finalized",
  framing_revision_requested: "Framing revision requested",
  final_revision_requested: "Final revision requested",
};

/** Human label for a TaskRole, for the Method invocation table. */
const ROLE_LABELS: Record<string, string> = {
  intake: "Intake",
  planner: "Planner",
  director: "Director",
  structurer: "Structurer",
  challenger: "Challenger",
  premortem: "Pre-mortem",
  auditor: "Auditor",
  researcher: "Researcher",
  analyst: "Analyst",
  assumption_analyst: "Assumption analyst",
  synthesizer: "Synthesizer",
  reviewer: "Reviewer",
  specialist: "Specialist",
};

export function roleLabel(value: string | null | undefined): string {
  if (!value) return "Unknown role";
  return ROLE_LABELS[value] ?? value;
}

// ── Inspector copy ───────────────────────────────────────────────────────────

export const INSPECTOR_COPY = {
  title: "Record",
  closeLabel: "Close inspector",
  machineryToggle: "Show the machinery",
  machineryHide: "Hide the machinery",
  rawYaml: "Raw artifact (YAML)",
  auditSlice: "Audit trail for this record",
  chainHeading: "Provenance chain",
  chainClaim: "Claim",
  chainExcerpt: "Excerpt",
  chainGrades: "Grades",
  chainLimitations: "Limitations",
  notFound: "This record could not be found.",
  loading: "Loading record…",
} as const;

/** Human label for an artifact id prefix (E-, A-, O-, T-, Q-, VC-). */
export function artifactKindLabel(artifactId: string): string {
  const m = /^([A-Z]+)-/.exec(artifactId);
  if (!m) return "Record";
  const map: Record<string, string> = {
    E: "Evidence record",
    A: "Assumption",
    O: "Objection",
    T: "Task",
    Q: "Question",
    VC: "Versioned checkpoint",
  };
  return map[m[1]] ?? "Record";
}

// ── Provenance labels (SPEC-035) ───────────────────────────────────────────

export const PROVENANCE_LABELS: Record<string, string> = {
  sourced_fact: "Sourced fact",
  interpretation: "Interpretation",
  user_input: "Your input",
  assumption: "Assumption",
  calculation: "Calculation",
  recommendation: "Recommendation",
};

export function provenanceLabel(value: string | null | undefined): string {
  if (!value) return "Unattributed";
  return PROVENANCE_LABELS[value] ?? value;
}

// ── Brief section titles (SPEC-035) ─────────────────────────────────────────

export const BRIEF_SECTION_TITLES: Record<string, string> = {
  executive_recommendation: "Executive recommendation",
  decision_confidence: "Decision confidence",
  alternatives_considered: "Alternatives considered",
  key_reasons: "Key reasons",
  scenario_analysis: "Scenario analysis",
  quantitative_findings: "Quantitative findings",
  strongest_counterarguments: "Strongest counterarguments",
  premortem: "Pre-mortem",
  critical_assumptions: "Critical assumptions",
  recommendation_change_triggers: "Recommendation change triggers",
  next_actions: "Next actions",
  user_supplied_inputs: "Your inputs",
  budget_depth_stop_disclosure: "Budget, depth, and stop disclosure",
  evidence_and_citations: "Evidence and citations",
};

/**
 * Render an objection ``target_section`` field path (e.g.
 * ``preliminary_recommendation.rationale[0]``) as a human-readable phrase.
 * The raw path carries internal stage/section enum strings and a machine
 * field index that must never surface in the DOM (SPEC-036).
 */
const TARGET_SECTION_LABELS: Record<string, string> = {
  preliminary_recommendation: "the preliminary recommendation",
  executive_recommendation: "the recommendation",
  provisional_thesis: "the provisional view",
  key_reasons: "the key reasons",
  scenario_analysis: "the scenario analysis",
  quantitative_findings: "the quantitative findings",
  critical_assumptions: "the critical assumptions",
  alternatives_considered: "the alternatives considered",
  next_actions: "the next actions",
  synthesis: "the synthesis",
};

export function targetSectionLabel(path: string | null | undefined): string {
  if (!path) return "the recommendation";
  const base = path.split(/[.[]/)[0];
  return (
    TARGET_SECTION_LABELS[base] ??
    (BRIEF_SECTION_TITLES[base] ? BRIEF_SECTION_TITLES[base].toLowerCase() : null) ??
    "the recommendation"
  );
}

// ── Method phases (SPEC-035) ─────────────────────────────────────────────────
export const PHASE_ORDER: string[] = [
  "intake",
  "framing",
  "investigation",
  "challenge",
  "synthesis",
  "complete",
];

export const PHASE_LABELS: Record<string, string> = {
  intake: "Intake",
  framing: "Framing",
  investigation: "Investigation",
  challenge: "Challenge",
  synthesis: "Synthesis",
  complete: "Complete",
};

export const PHASE_TIME_RANGES: Record<string, string> = {
  intake: "under 1 minute",
  framing: "1–3 minutes",
  investigation: "3–15 minutes",
  challenge: "2–8 minutes",
  synthesis: "1–5 minutes",
  complete: "done",
};

// ── Method strip copy (SPEC-035) ───────────────────────────────────────────

export const METHOD_STRIP_COPY = {
  nothingNeedsYou: "Nothing needs you right now.",
  needsYou: "This case needs you.",
  leaveSafely:
    "You can leave the page. Work continues in the background and the brief will update when something happens.",
  sealed: "The answer is being drafted and independently checked before it is shown to you.",
} as const;

// ── Non-final stamp (SPEC-035) ─────────────────────────────────────────────

export const NON_FINAL_STAMP = "NON-FINAL — may change as the case runs";

// ── Tripwire copy (SPEC-035) ───────────────────────────────────────────────

export const TRIPWIRE_COPY = {
  title: "This advice expires if…",
  empty: "No explicit tripwires were recorded.",
} as const;

// ── Confidence bands (5-step) (SPEC-035) ───────────────────────────────────

export const CONFIDENCE_BANDS = [
  { threshold: 0.85, label: "Very high", key: "very_high" },
  { threshold: 0.65, label: "High", key: "high" },
  { threshold: 0.45, label: "Moderate", key: "moderate" },
  { threshold: 0.25, label: "Low", key: "low" },
  { threshold: 0, label: "Very low", key: "very_low" },
] as const;

export function confidenceBand(
  point: number | null | undefined,
): { label: string; index: number } {
  if (point == null || Number.isNaN(point)) return { label: "Not assessed", index: -1 };
  for (let i = 0; i < CONFIDENCE_BANDS.length; i++) {
    if (point >= CONFIDENCE_BANDS[i].threshold) {
      return { label: CONFIDENCE_BANDS[i].label, index: i };
    }
  }
  return {
    label: CONFIDENCE_BANDS[CONFIDENCE_BANDS.length - 1].label,
    index: CONFIDENCE_BANDS.length - 1,
  };
}

// ── Source-strength grade (SPEC-035) ────────────────────────────────────────

export function sourceStrengthGrade(score: number | null | undefined): string {
  if (score == null || Number.isNaN(score)) return "—";
  if (score >= 0.9) return "A";
  if (score >= 0.75) return "B";
  if (score >= 0.55) return "C";
  if (score >= 0.35) return "D";
  return "F";
}

// ── Failure-path copy (SPEC-035) ─────────────────────────────────────────────

export const FAILURE_COPY = {
  failedTitle: "This case stopped before finishing",
  failedDetail: "The run failed. You can resume from the last checkpoint to continue the investigation.",
  interruptedTitle: "This case was interrupted",
  interruptedDetail: "It stopped before the recommendation was ready. Resume to continue.",
  earlyStopTitle: "This case stopped early",
  earlyStopDetail: "It ran into a budget or depth limit before the full investigation completed.",
  acceptAsIs: "Accept this result as-is",
  extendFraming: "Extend the framing",
  resume: "Resume",
  backToCase: "Back to the case",
} as const;
