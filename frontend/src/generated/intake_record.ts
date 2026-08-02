/* Generated from intake_record.schema.json. Do not edit manually. */

export type AlternativesMentioned = [string, ...string[]] | null;
/**
 * @maxItems 5
 */
export type ClarificationQuestions =
  | []
  | [ClarificationQuestion]
  | [ClarificationQuestion, ClarificationQuestion]
  | [ClarificationQuestion, ClarificationQuestion, ClarificationQuestion]
  | [ClarificationQuestion, ClarificationQuestion, ClarificationQuestion, ClarificationQuestion]
  | [ClarificationQuestion, ClarificationQuestion, ClarificationQuestion, ClarificationQuestion, ClarificationQuestion];
export type MaterialityReason = string;
export type Question = string;
export type QuestionId = string;
export type IntakeField =
  | 'decision_question'
  | 'deadline'
  | 'alternatives_mentioned'
  | 'objectives'
  | 'constraints'
  | 'risk_tolerance'
  | 'reversibility'
  | 'depth';
export type SchemaVersion = number;
export type Constraints = [string, ...string[]] | null;
export type Deadline = string | null;
export type DecisionQuestion = string | null;
export type Depth = 'light' | 'standard' | 'deep';
export type Objectives = [string, ...string[]] | null;
export type RawPrompt = string;
export type Reversibility = 'fully_reversible' | 'partially_reversible' | 'irreversible';
export type RiskTolerance = 'low' | 'moderate' | 'high';
export type SchemaVersion1 = number;

export interface IntakeRecord {
  alternatives_mentioned?: AlternativesMentioned;
  clarification_questions?: ClarificationQuestions;
  constraints?: Constraints;
  deadline?: Deadline;
  decision_question?: DecisionQuestion;
  depth?: Depth | null;
  objectives?: Objectives;
  raw_prompt: RawPrompt;
  reversibility?: Reversibility | null;
  risk_tolerance?: RiskTolerance | null;
  schema_version?: SchemaVersion1;
}
export interface ClarificationQuestion {
  materiality_reason: MaterialityReason;
  question: Question;
  question_id: QuestionId;
  resolves_field: IntakeField;
  schema_version?: SchemaVersion;
}
