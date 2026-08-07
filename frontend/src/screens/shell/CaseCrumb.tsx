import { Link } from "react-router-dom";

/**
 * Top-of-screen chrome for the screens that are not the case surface (SPEC-048).
 *
 * Replaces `.back-link`: a paragraph at the *bottom* of ten screens, so the way
 * out was below the fold on every one of them, and the reader had to scroll
 * past everything to leave. Navigation belongs in chrome, at the top, before
 * the content — where a user looks for it without being told.
 */
export function CaseCrumb({ caseId, label = "Back to the case" }: { caseId?: string; label?: string }) {
  return (
    <nav className="case-crumb" aria-label="Breadcrumb">
      <Link to="/" className="case-crumb-link">All cases</Link>
      {caseId && (
        <>
          <span className="case-crumb-sep" aria-hidden="true">/</span>
          <Link to={`/cases/${caseId}`} className="case-crumb-link">{label}</Link>
        </>
      )}
    </nav>
  );
}
