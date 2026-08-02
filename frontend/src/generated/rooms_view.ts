/* Generated from rooms_view.schema.json. Do not edit manually. */

export type AssumptionId = string;
export type Claim = string;
export type Confidence = string;
export type EstimatePoint = number | null;
export type EvidenceAgainst = string[];
export type EvidenceFor = string[];
export type Materiality = string;
export type Status = string;
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
export type Stage = string;
export type Alternative = string;
export type ExpectedValue = number | null;
export type Rank = number;
export type Rationale = string;
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
export type PublicationDate = string;
export type Publisher = string;
export type Reliability = string;
export type SourceTier = string | null;
export type SourceType = string;
export type SourceUrl = string;
export type Sources = SourceView[];

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
  status: Status;
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
  stage: Stage;
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
  expected_value?: ExpectedValue;
  rank: Rank;
  rationale: Rationale;
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
  publication_date: PublicationDate;
  publisher: Publisher;
  reliability: Reliability;
  source_tier?: SourceTier;
  source_type: SourceType;
  source_url: SourceUrl;
}
