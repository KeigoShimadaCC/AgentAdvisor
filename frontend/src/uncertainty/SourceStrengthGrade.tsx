import { sourceStrengthGrade } from "../copy/terms";
import { NotAssessedWidget } from "./NotAssessedWidget";
import type { AssessedConfidence, NotAssessed } from "../generated/uncertainty_view";

interface SourceStrengthGradeProps {
  source: AssessedConfidence | NotAssessed | null | undefined;
}

/**
 * Source-strength encoding: letter grade + fill bar, with the basis text.
 */
export function SourceStrengthGrade({ source }: SourceStrengthGradeProps) {
  if (!source || source.kind === "not_assessed") {
    return <NotAssessedWidget reason={source?.reason ?? "Not assessed"} />;
  }

  const assessed = source as AssessedConfidence;
  const grade = sourceStrengthGrade(assessed.value);
  const pct = Math.round(assessed.value * 100);

  return (
    <div className="source-strength">
      <span className="source-strength-grade" aria-label={`Source strength grade ${grade}`}>
        {grade}
      </span>
      <div className="source-strength-bar" aria-hidden="true">
        <div className="source-strength-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="source-strength-basis">{assessed.basis}</span>
    </div>
  );
}
