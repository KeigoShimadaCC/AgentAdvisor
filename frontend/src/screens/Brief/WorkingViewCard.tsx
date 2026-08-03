import { Link } from "react-router-dom";
import { NON_FINAL_STAMP } from "../../copy/terms";
import type { ThesisRevisionView } from "../../generated/case_view";

interface WorkingViewCardProps {
  caseId: string;
  revisions: ThesisRevisionView[];
}

/**
 * Discrete thesis-revision cards shown mid-run.
 * Carries the NON-FINAL stamp and avoids exposing live numeric estimates.
 */
export function WorkingViewCard({ caseId, revisions }: WorkingViewCardProps) {
  const changed = revisions.filter((r) => r.changed);
  if (changed.length === 0) return null;

  return (
    <section className="working-view-card" aria-label="Working view">
      <h3>Working view</h3>
      <ul className="working-view-list">
        {changed.map((r) => (
          <li key={r.revision} className="working-view-change">
            <span className="non-final-stamp" aria-label="Non-final">
              {NON_FINAL_STAMP}
            </span>
            <p className="working-view-summary">
              The working view changed to <strong>{r.preferred_alternative}</strong>
              {r.previous_alternative && <> from {r.previous_alternative}</>}.
            </p>
            {r.rationale_digest && r.rationale_digest.length > 0 && (
              <div className="working-view-because">
                <span>Changed because:</span>
                <ul>
                  {r.rationale_digest.map((line, i) => (
                    <li key={i}>{line}</li>
                  ))}
                </ul>
              </div>
            )}
            <Link to={`/cases/${caseId}/rooms/method`} className="link-button">
              See the reasoning in the Method room
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
