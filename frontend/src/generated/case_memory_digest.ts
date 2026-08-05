/* Generated from case_memory_digest.schema.json. Do not edit manually. */

export type BrierScore = number | null;
export type Interpretation = string;
export type MeanForecast = number | null;
export type MeanRealized = number | null;
export type SampleSize = number;
export type SchemaVersion = number;
export type GeneratedAt = string;
export type AlternativesConsidered = string[];
export type CaseId = string;
export type CompletedAt = string;
export type DecisionQuestion = string;
export type Domains = string[];
export type EvidenceConfidence = number;
export type HeadlineOutcomeName = string | null;
export type HeadlineOutcomeProbability = number | null;
export type Keywords = string[];
export type ForecastOutcomeName = string;
export type ForecastProbability = number;
export type OutcomeSummary = string;
export type Realized = boolean;
export type RecommendationFollowed = boolean;
export type RecordedAt = string;
export type SchemaVersion1 = number;
export type RecommendationConfidence = number;
export type RecommendedAction = string;
export type SchemaVersion2 = number;
export type PriorCases = PriorCaseEntry[];
export type CaseIds = string[];
export type ExampleClaim = string;
export type Level = 'high' | 'medium' | 'low';
export type NormalizedClaim = string;
export type Occurrences = number;
export type SchemaVersion3 = number;
export type RecurringAssumptions = RecurringAssumption[];
export type SchemaVersion4 = number;
export type CaseIds1 = string[];
export type Domain = string;
export type MeanAuthority = number;
export type SchemaVersion5 = number;
export type SourceType =
  | 'regulatory_filing'
  | 'official_statistic'
  | 'law_or_standard'
  | 'original_research'
  | 'reputable_secondary'
  | 'specialist_reporting'
  | 'user_document'
  | 'other';
export type SourceTypes = SourceType[];
export type TimesCited = number;
export type TimesContradicted = number;
export type SourceReputations = SourceReputation[];
export type UsageNote = string;

/**
 * The compact cross-case brief projected into a live case.
 *
 * Everything here is prior context, not evidence. Nothing in this digest may be
 * cited; it exists to stop the system from starting every case with an empty head.
 */
export interface CaseMemoryDigest {
  calibration?: CalibrationSummary | null;
  generated_at: GeneratedAt;
  prior_cases?: PriorCases;
  recurring_assumptions?: RecurringAssumptions;
  schema_version?: SchemaVersion4;
  source_reputations?: SourceReputations;
  usage_note: UsageNote;
}
export interface CalibrationSummary {
  brier_score?: BrierScore;
  interpretation: Interpretation;
  mean_forecast?: MeanForecast;
  mean_realized?: MeanRealized;
  sample_size: SampleSize;
  schema_version?: SchemaVersion;
}
export interface PriorCaseEntry {
  alternatives_considered?: AlternativesConsidered;
  case_id: CaseId;
  completed_at: CompletedAt;
  decision_question: DecisionQuestion;
  domains?: Domains;
  evidence_confidence: EvidenceConfidence;
  headline_outcome_name?: HeadlineOutcomeName;
  headline_outcome_probability?: HeadlineOutcomeProbability;
  keywords?: Keywords;
  outcome?: OutcomeRecord | null;
  recommendation_confidence: RecommendationConfidence;
  recommended_action: RecommendedAction;
  schema_version?: SchemaVersion2;
}
/**
 * A realized outcome attached to a completed case, recorded by the user.
 */
export interface OutcomeRecord {
  forecast_outcome_name: ForecastOutcomeName;
  forecast_probability: ForecastProbability;
  outcome_summary: OutcomeSummary;
  realized: Realized;
  recommendation_followed: RecommendationFollowed;
  recorded_at: RecordedAt;
  schema_version?: SchemaVersion1;
}
export interface RecurringAssumption {
  case_ids?: CaseIds;
  example_claim: ExampleClaim;
  max_materiality: Level;
  normalized_claim: NormalizedClaim;
  occurrences: Occurrences;
  schema_version?: SchemaVersion3;
}
export interface SourceReputation {
  case_ids?: CaseIds1;
  domain: Domain;
  mean_authority: MeanAuthority;
  schema_version?: SchemaVersion5;
  source_types?: SourceTypes;
  times_cited: TimesCited;
  times_contradicted: TimesContradicted;
}
