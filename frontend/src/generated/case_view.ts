/* Generated from case_view.schema.json. Do not edit manually. */

export type CitationIds = string[];
export type Provenance = string;
export type Text = string;
export type Blocks = BriefBlock[];
export type Key = string;
export type Status = 'pending' | 'partial' | 'final' | 'not_assessed';
export type BriefSections = BriefSection[];
export type CaseId = string;
export type InputTokens = number;
export type InvocationAttempts = number;
export type InvocationSuccesses = number;
export type OutputTokens = number;
export type Retries = number;
export type TotalTokens = number;
export type WallClockS = number | null;
export type ApprovedAt = string;
export type ApprovedBy = string;
export type Decision = string;
export type Kind = 'framing' | 'final';
export type Approvals = ApprovalRecordView[];
export type Changed = boolean;
export type EvidenceConfidence = number;
export type PreferredAlternative = string;
export type PreviousAlternative = string | null;
export type RationaleDigest = string[];
export type RecommendationConfidence = number;
export type Revision = number;
export type Trigger = string;
export type ThesisRevisions = ThesisRevisionView[];
export type Disclosure = {
  [k: string]: unknown;
} | null;
export type Findings = {
  [k: string]: unknown;
}[];
export type Outcome = string;
export type Stage = string;
export type Gates = GateSummaryView[];
export type ReviewAccepted = boolean | null;
export type ReviewBlockingFindings = {
  [k: string]: unknown;
}[];
export type ReviewDefects = {
  [k: string]: unknown;
}[];
export type ReviewOutcome = string | null;
export type IsTerminal = boolean;
export type NeedsYou = 'scope_checkpoint' | 'delivery_checkpoint' | 'interrupted' | 'none';
export type Phase = 'intake' | 'framing' | 'investigation' | 'challenge' | 'synthesis' | 'complete';
export type AssumptionId = string;
export type Claim = string;
export type Confidence = string;
export type EstimatePoint = number | null;
export type EvidenceAgainst = string[];
export type EvidenceFor = string[];
export type Materiality = string;
export type Status1 = string;
export type Type = string;
export type Assumptions = AssumptionView[];
export type Claim1 = string;
export type Materiality1 = string;
export type ObjectionId = string;
export type Reasoning = string;
export type ResolutionStatus = string;
export type TargetSection = string;
export type Objections = ObjectionView[];
export type AssumedOutcome = string;
export type FailureModes = {
  [k: string]: unknown;
}[];
export type Horizon = string;
export type MostLikelyFailureMode = string;
export type Agreement = boolean;
export type DivergenceSummary = string;
export type Positions = {
  [k: string]: unknown;
}[];
export type ReconciledAlternative = string | null;
export type Stage1 = string;
export type Alternative = string;
export type Eliminated = boolean;
export type ExpectedValue = number | null;
export type ObjectiveScores = {
  [k: string]: number;
} | null;
export type Rank = number;
export type Rationale = string;
export type WeightedRank = number | null;
export type WeightedScore = number | null;
export type Options = OptionView[];
export type CoverageFraction = number;
export type DecisionQuestion = string;
export type MeceJustification = string;
export type Covered = boolean;
export type Materiality2 = string;
export type NodeId = string;
export type NodeType = string;
export type ParentId = string | null;
export type Question = string;
export type ResolutionCriteria = string;
export type Nodes = IssueNodeView[];
export type CorpusAuthorityMean = number | null;
export type IndependentGroupCount = number | null;
export type MaxClusterShare = number | null;
export type PrimarySourceShare = number | null;
export type AuthorityScore = number | null;
export type Claim2 = string;
export type ClusterShare = number | null;
export type Directness = string;
export type EvidenceId = string;
export type Flags = string[];
export type IndependenceGroup = string;
export type Limitations = string[];
export type PublicationDate = string;
export type Publisher = string;
export type Reliability = string;
export type SourceTier = string | null;
export type SourceType = string;
export type SourceUrl = string;
export type Sources = SourceView[];
export type Stage2 = string;
export type EvidenceConfidence1 = AssessedConfidence | NotAssessed;
export type Basis = string;
export type Kind1 = 'assessed';
export type Value = number;
export type Kind2 = 'not_assessed';
export type Reason = string;
export type ModelStability = AssessedStability | NotAssessed;
export type Kind3 = 'assessed';
export type RunsSupporting = number;
export type RunsTotal = number;
export type Share = number;
export type Adjustments = {
  [k: string]: unknown;
}[];
export type IntervalHigh = number | null;
export type IntervalLow = number | null;
export type Method = string;
export type Point = number | null;
export type RecommendationConfidence1 = AssessedConfidence | NotAssessed;
export type ViewVersion = number;

/**
 * Versioned read model for one case, assembled from disk.
 */
export interface CaseView {
  brief_sections?: BriefSections;
  case_id: CaseId;
  effort?: EffortView;
  history?: HistoryView;
  integrity?: IntegrityView;
  is_terminal: IsTerminal;
  needs_you: NeedsYou;
  phase: Phase;
  rooms?: RoomsView;
  stage: Stage2;
  uncertainty?: UncertaintyView | null;
  view_version?: ViewVersion;
}
export interface BriefSection {
  blocks?: Blocks;
  key: Key;
  status: Status;
}
/**
 * One rendered line/element within a brief section, carrying provenance.
 */
export interface BriefBlock {
  citation_ids?: CitationIds;
  provenance: Provenance;
  text: Text;
}
export interface EffortView {
  budget_caps?: BudgetCaps;
  budget_counters?: BudgetCounters;
  by_role?: ByRole;
  event_counts?: EventCounts;
  input_tokens?: InputTokens;
  invocation_attempts?: InvocationAttempts;
  invocation_successes?: InvocationSuccesses;
  output_tokens?: OutputTokens;
  retries?: Retries;
  total_tokens?: TotalTokens;
  wall_clock_s?: WallClockS;
}
export interface BudgetCaps {
  [k: string]: number;
}
export interface BudgetCounters {
  [k: string]: number;
}
export interface ByRole {
  [k: string]: {
    [k: string]: number;
  };
}
export interface EventCounts {
  [k: string]: number;
}
export interface HistoryView {
  approvals?: Approvals;
  thesis_revisions?: ThesisRevisions;
}
export interface ApprovalRecordView {
  approved_at: ApprovedAt;
  approved_by: ApprovedBy;
  decision: Decision;
  kind: Kind;
}
export interface ThesisRevisionView {
  changed: Changed;
  evidence_confidence: EvidenceConfidence;
  preferred_alternative: PreferredAlternative;
  previous_alternative?: PreviousAlternative;
  rationale_digest?: RationaleDigest;
  recommendation_confidence: RecommendationConfidence;
  revision: Revision;
  trigger: Trigger;
}
export interface IntegrityView {
  disclosure?: Disclosure;
  gates?: Gates;
  review_accepted?: ReviewAccepted;
  review_blocking_findings?: ReviewBlockingFindings;
  review_defects?: ReviewDefects;
  review_outcome?: ReviewOutcome;
}
export interface GateSummaryView {
  findings?: Findings;
  outcome: Outcome;
  stage: Stage;
}
export interface RoomsView {
  assumptions?: AssumptionsRoom;
  challenges?: ChallengesRoom;
  options?: OptionsRoom;
  plan?: PlanView | null;
  sources?: SourcesRoom;
}
export interface AssumptionsRoom {
  assumptions?: Assumptions;
}
export interface AssumptionView {
  assumption_id: AssumptionId;
  claim: Claim;
  confidence: Confidence;
  estimate_point?: EstimatePoint;
  evidence_against?: EvidenceAgainst;
  evidence_for?: EvidenceFor;
  materiality: Materiality;
  status: Status1;
  type: Type;
}
export interface ChallengesRoom {
  objections?: Objections;
  premortem?: PreMortemView | null;
  track_divergence?: TrackDivergenceView | null;
}
export interface ObjectionView {
  claim: Claim1;
  materiality: Materiality1;
  objection_id: ObjectionId;
  reasoning: Reasoning;
  resolution_status: ResolutionStatus;
  target_section: TargetSection;
}
export interface PreMortemView {
  assumed_outcome: AssumedOutcome;
  failure_modes?: FailureModes;
  horizon: Horizon;
  most_likely_failure_mode: MostLikelyFailureMode;
}
export interface TrackDivergenceView {
  agreement: Agreement;
  divergence_summary: DivergenceSummary;
  positions?: Positions;
  reconciled_alternative?: ReconciledAlternative;
  stage: Stage1;
}
export interface OptionsRoom {
  ev_table?: EvTable;
  options?: Options;
}
export interface EvTable {
  [k: string]: number;
}
export interface OptionView {
  alternative: Alternative;
  eliminated?: Eliminated;
  expected_value?: ExpectedValue;
  objective_scores?: ObjectiveScores;
  rank: Rank;
  rationale: Rationale;
  weighted_rank?: WeightedRank;
  weighted_score?: WeightedScore;
}
export interface PlanView {
  coverage_fraction?: CoverageFraction;
  decision_question: DecisionQuestion;
  mece_justification?: MeceJustification;
  nodes?: Nodes;
}
export interface IssueNodeView {
  covered?: Covered;
  materiality: Materiality2;
  node_id: NodeId;
  node_type: NodeType;
  parent_id?: ParentId;
  question: Question;
  resolution_criteria: ResolutionCriteria;
}
export interface SourcesRoom {
  corpus_authority_mean?: CorpusAuthorityMean;
  independent_group_count?: IndependentGroupCount;
  max_cluster_share?: MaxClusterShare;
  primary_source_share?: PrimarySourceShare;
  sources?: Sources;
}
/**
 * An evidence record joined with its critique scores/tiers/flags.
 */
export interface SourceView {
  authority_score?: AuthorityScore;
  claim: Claim2;
  cluster_share?: ClusterShare;
  directness: Directness;
  evidence_id: EvidenceId;
  flags?: Flags;
  independence_group: IndependenceGroup;
  limitations?: Limitations;
  publication_date: PublicationDate;
  publisher: Publisher;
  reliability: Reliability;
  source_tier?: SourceTier;
  source_type: SourceType;
  source_url: SourceUrl;
}
export interface UncertaintyView {
  evidence_confidence: EvidenceConfidence1;
  model_stability: ModelStability;
  outcome_probabilities?: OutcomeProbabilities;
  recommendation_confidence: RecommendationConfidence1;
}
/**
 * A confidence that was actually assessed (not a coercion default).
 */
export interface AssessedConfidence {
  basis: Basis;
  kind?: Kind1;
  value: Value;
}
/**
 * A confidence/stability that is a sentinel placeholder.
 */
export interface NotAssessed {
  kind?: Kind2;
  reason: Reason;
}
/**
 * Model stability that was actually assessed (multiple sensitivity runs).
 */
export interface AssessedStability {
  kind?: Kind3;
  runs_supporting: RunsSupporting;
  runs_total: RunsTotal;
  share: Share;
}
export interface OutcomeProbabilities {
  [k: string]: ProbabilityView;
}
/**
 * One outcome probability entry, preserving point-XOR-interval.
 */
export interface ProbabilityView {
  adjustments?: Adjustments;
  interval_high?: IntervalHigh;
  interval_low?: IntervalLow;
  method: Method;
  point?: Point;
}
