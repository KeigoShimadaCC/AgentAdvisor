import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { InterviewCards } from "./InterviewCards";
import type { ClarificationQuestion } from "../../generated/intake_record";
import { SCOPE_COPY } from "../../copy/terms";

const questions: ClarificationQuestion[] = [
  {
    question_id: "q-deadline",
    question: "When do you need to decide by?",
    materiality_reason: "The deadline affects how much evidence we can gather.",
    resolves_field: "deadline",
  },
  {
    question_id: "q-risk",
    question: "How much risk can you accept?",
    materiality_reason: "Risk tolerance shapes the options I will weigh.",
    resolves_field: "risk_tolerance",
  },
];

describe("InterviewCards", () => {
  it("renders one card per question", () => {
    render(<InterviewCards caseId="c1" questions={questions} onDone={() => {}} />);
    expect(screen.getByText("When do you need to decide by?")).toBeInTheDocument();
    expect(screen.getByText("How much risk can you accept?")).toBeInTheDocument();
  });

  it("shows the declared-assumption label when a question is skipped", () => {
    render(<InterviewCards caseId="c1" questions={questions} onDone={() => {}} />);
    const skipButtons = screen.getAllByText("Skip — assume something reasonable");
    fireEvent.click(skipButtons[0]);

    expect(screen.getByText(SCOPE_COPY.declaredAssumptionLabel)).toBeInTheDocument();
    // The skip button for the first card is gone.
    expect(screen.getAllByText("Skip — assume something reasonable")).toHaveLength(1);
  });

  it("allows un-skipping a question", () => {
    render(<InterviewCards caseId="c1" questions={questions} onDone={() => {}} />);
    const skipButtons = screen.getAllByText("Skip — assume something reasonable");
    fireEvent.click(skipButtons[0]);
    fireEvent.click(screen.getByText("Answer it instead"));
    // Two skip buttons again.
    expect(screen.getAllByText("Skip — assume something reasonable")).toHaveLength(2);
  });

  it("disables continue until all questions are answered or skipped", () => {
    render(<InterviewCards caseId="c1" questions={questions} onDone={() => {}} />);
    const continueButton = screen.getByText("Continue to the scope sheet");
    expect(continueButton).toBeDisabled();

    // Skip both.
    const skipButtons = screen.getAllByText("Skip — assume something reasonable");
    fireEvent.click(skipButtons[0]);
    fireEvent.click(skipButtons[1]);
    expect(continueButton).not.toBeDisabled();
  });

  it("collects answers from quick-answer chips and calls onDone", () => {
    const onDone = vi.fn();
    render(<InterviewCards caseId="c1" questions={questions} onDone={onDone} />);
    // risk_tolerance has quick-answer chips; pick "Cautious".
    const cautious = screen.getByText("Cautious");
    fireEvent.click(cautious);
    // Skip the deadline question.
    const skipButtons = screen.getAllByText("Skip — assume something reasonable");
    fireEvent.click(skipButtons[0]);

    fireEvent.click(screen.getByText("Continue to the scope sheet"));
    // Keyed by question_id: that is what the engine's clarification_answers mapping
    // expects. Keying by resolves_field silently produced the wrong keys until
    // SPEC-043 made the field optional and forced the question.
    expect(onDone).toHaveBeenCalledWith({ "q-risk": "low" });
  });
});

describe("InterviewCards with non-field questions (SPEC-043)", () => {
  const openQuestions: ClarificationQuestion[] = [
    {
      question_id: "q-doc",
      kind: "document",
      question: "Can you add the vendor's quote to the case?",
      materiality_reason: "Renewal pricing decides the buy path's real cost.",
    },
    {
      question_id: "q-fact",
      kind: "fact",
      question: "What do you currently spend on this per year?",
      materiality_reason: "Without today's baseline neither option is comparable.",
    },
  ];

  it("renders questions that fill no framing field", () => {
    render(<InterviewCards caseId="c1" questions={openQuestions} onDone={() => {}} />);
    expect(screen.getByText("Can you add the vendor's quote to the case?")).toBeInTheDocument();
    expect(screen.getAllByText(/only you can answer it/)).toHaveLength(2);
  });

  it("offers no quick-answer chips for an open question", () => {
    render(<InterviewCards caseId="c1" questions={openQuestions} onDone={() => {}} />);
    expect(screen.queryByRole("group", { name: "Quick answers" })).not.toBeInTheDocument();
  });

  it("collects free-text answers keyed by question_id", () => {
    const onDone = vi.fn();
    render(<InterviewCards caseId="c1" questions={openQuestions} onDone={onDone} />);
    const inputs = screen.getAllByPlaceholderText("Or type your own answer");
    fireEvent.change(inputs[0], { target: { value: "Attached as quote.md" } });
    fireEvent.blur(inputs[0]);
    fireEvent.change(inputs[1], { target: { value: "About 48,000 a year" } });
    fireEvent.blur(inputs[1]);

    fireEvent.click(screen.getByText("Continue to the scope sheet"));
    expect(onDone).toHaveBeenCalledWith({
      "q-doc": "Attached as quote.md",
      "q-fact": "About 48,000 a year",
    });
  });
});
