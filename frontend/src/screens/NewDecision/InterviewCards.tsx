import { useState } from "react";
import type { ClarificationQuestion } from "../../generated/intake_record";
import { intakeFieldLabel, SCOPE_COPY } from "../../copy/terms";

/**
 * Quick-answer chips offered per intake field.  The displayed label is human;
 * the stored value is what the engine expects (an enum value or short string).
 */
interface QuickAnswer {
  label: string;
  value: string;
}

function quickAnswersForField(field: string): QuickAnswer[] {
  switch (field) {
    case "risk_tolerance":
      return [
        { label: "Cautious", value: "low" },
        { label: "Balanced", value: "moderate" },
        { label: "Growth-oriented", value: "high" },
      ];
    case "reversibility":
      return [
        { label: "Fully reversible", value: "fully_reversible" },
        { label: "Partially reversible", value: "partially_reversible" },
        { label: "Hard to reverse", value: "irreversible" },
      ];
    case "depth":
      return [
        { label: "Quick look", value: "light" },
        { label: "Standard", value: "standard" },
        { label: "Deep dive", value: "deep" },
      ];
    case "deadline":
      return [
        { label: "No hard deadline", value: "none" },
        { label: "Within a month", value: "1 month" },
        { label: "This quarter", value: "this quarter" },
        { label: "This year", value: "this year" },
      ];
    default:
      return [];
  }
}

export interface InterviewCardsProps {
  caseId: string;
  questions: ClarificationQuestion[];
  /** Called with the collected clarification answers (field → value). */
  onDone: (answers: Record<string, string>) => void;
}

/**
 * One card per clarification question (SPEC-034 §13.1).
 *
 * Each card shows a plain-language question, the translated materiality
 * reason, quick-answer chips (where applicable) plus a free-text input, and
 * a "Skip — assume something reasonable" button that labels the resulting
 * declared assumption.
 */
export function InterviewCards({ questions, onDone }: InterviewCardsProps) {
  // Answers keyed by question_id, which is what the engine's clarification_answers
  // mapping expects. SPEC-043 made resolves_field optional (document and fact questions
  // fill no framing slot), which surfaced that keying by it was wrong for every
  // question, not just the new kinds.
  const [answers, setAnswers] = useState<Record<string, string>>({});
  // skipped question_ids
  const [skipped, setSkipped] = useState<Set<string>>(new Set());
  // free-text buffer per question_id
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const allResolved = questions.every(
    (q) => answers[q.question_id] !== undefined || skipped.has(q.question_id),
  );

  function setAnswer(questionId: string, value: string) {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  }

  function skip(q: ClarificationQuestion) {
    setSkipped((prev) => new Set(prev).add(q.question_id));
    // A skipped question contributes no answer; clear any draft.
    setDrafts((prev) => {
      const next = { ...prev };
      delete next[q.question_id];
      return next;
    });
  }

  function unskip(q: ClarificationQuestion) {
    setSkipped((prev) => {
      const next = new Set(prev);
      next.delete(q.question_id);
      return next;
    });
  }

  function commitDraft(q: ClarificationQuestion) {
    const text = (drafts[q.question_id] ?? "").trim();
    if (text) setAnswer(q.question_id, text);
  }

  return (
    <ol className="interview-cards">
      {questions.map((q) => {
        const isSkipped = skipped.has(q.question_id);
        const answered = answers[q.question_id];
        // Only framing-field questions have canned answers or a field to name; a
        // document or fact request is free-text by nature.
        const quick = q.resolves_field ? quickAnswersForField(q.resolves_field) : [];

        return (
          <li key={q.question_id} className="interview-card">
            <h3 className="interview-question">{q.question}</h3>
            <p className="interview-materiality">
              {q.resolves_field
                ? `This matters because it shapes ${intakeFieldLabel(q.resolves_field)}.`
                : "This matters because only you can answer it."}
              {q.materiality_reason ? ` ${q.materiality_reason}` : ""}
            </p>

            {isSkipped ? (
              <div className="interview-skipped">
                <span className="declared-assumption-label">
                  {SCOPE_COPY.declaredAssumptionLabel}
                </span>
                <button type="button" className="link-button" onClick={() => unskip(q)}>
                  Answer it instead
                </button>
              </div>
            ) : (
              <div className="interview-controls">
                {quick.length > 0 && (
                  <div className="quick-answers" role="group" aria-label="Quick answers">
                    {quick.map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        className={`quick-answer-chip${answered === opt.value ? " selected" : ""}`}
                        aria-pressed={answered === opt.value}
                        onClick={() => setAnswer(q.question_id, opt.value)}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                )}

                <label htmlFor={`draft-${q.question_id}`} className="sr-only">
                  Your answer
                </label>
                <input
                  id={`draft-${q.question_id}`}
                  type="text"
                  className="interview-text"
                  placeholder="Or type your own answer"
                  value={drafts[q.question_id] ?? ""}
                  onChange={(e) =>
                    setDrafts((prev) => ({ ...prev, [q.question_id]: e.target.value }))
                  }
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      commitDraft(q);
                    }
                  }}
                  onBlur={() => commitDraft(q)}
                />

                <button type="button" className="skip-button" onClick={() => skip(q)}>
                  Skip — assume something reasonable
                </button>
              </div>
            )}
          </li>
        );
      })}

      <li className="interview-actions">
        <button
          type="button"
          className="primary-action"
          disabled={!allResolved}
          onClick={() => onDone(answers)}
        >
          Continue to the scope sheet
        </button>
        {!allResolved && (
          <p className="screen-help">Answer or skip each question to continue.</p>
        )}
      </li>
    </ol>
  );
}
