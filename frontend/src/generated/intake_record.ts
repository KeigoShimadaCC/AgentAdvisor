/* Generated from intake_record.schema.json. Do not edit manually. */

export type AlternativesMentioned = [string, ...string[]] | null;
/**
 * @maxItems 8
 */
export type ClarificationQuestions =
  | []
  | [ClarificationQuestion]
  | [ClarificationQuestion, ClarificationQuestion]
  | [ClarificationQuestion, ClarificationQuestion, ClarificationQuestion]
  | [ClarificationQuestion, ClarificationQuestion, ClarificationQuestion, ClarificationQuestion]
  | [ClarificationQuestion, ClarificationQuestion, ClarificationQuestion, ClarificationQuestion, ClarificationQuestion]
  | [
      ClarificationQuestion,
      ClarificationQuestion,
      ClarificationQuestion,
      ClarificationQuestion,
      ClarificationQuestion,
      ClarificationQuestion
    ]
  | [
      ClarificationQuestion,
      ClarificationQuestion,
      ClarificationQuestion,
      ClarificationQuestion,
      ClarificationQuestion,
      ClarificationQuestion,
      ClarificationQuestion
    ]
  | [
      ClarificationQuestion,
      ClarificationQuestion,
      ClarificationQuestion,
      ClarificationQuestion,
      ClarificationQuestion,
      ClarificationQuestion,
      ClarificationQuestion,
      ClarificationQuestion
    ];
/**
 * What an intake question is asking for.
 *
 * Before SPEC-043 every question had to map to one of eight framing fields, so intake
 * could ask "what is your risk tolerance?" but not "what is your cost basis?" — and the
 * facts that decide personal cases usually live in the decision owner's head rather
 * than on the public web.
 */
export type ClarificationKind = 'field' | 'document' | 'fact';
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
  | 'depth'
  | 'internal_information';
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
  kind?: ClarificationKind;
  materiality_reason: MaterialityReason;
  question: Question;
  question_id: QuestionId;
  resolves_field?: IntakeField | null;
  schema_version?: SchemaVersion;
}
