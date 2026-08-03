import { METHOD_STRIP_COPY } from "../../copy/terms";

interface SealedAnswerCardProps {
  stage: string;
}

/**
 * Shown during synthesis/review while the answer is being drafted and
 * independently checked.
 */
export function SealedAnswerCard({ stage }: SealedAnswerCardProps) {
  if (stage !== "synthesis" && stage !== "review" && stage !== "awaiting_final_approval") {
    return null;
  }

  return (
    <section className="sealed-answer-card" aria-label="Answer in progress">
      <p>{METHOD_STRIP_COPY.sealed}</p>
    </section>
  );
}
