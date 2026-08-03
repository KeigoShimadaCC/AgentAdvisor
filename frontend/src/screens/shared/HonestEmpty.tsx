import { EMPTY_TRUTHS, type EmptyTruth } from "../../copy/terms";

interface HonestEmptyProps {
  /** Which of the three truths applies. */
  truth: EmptyTruth;
  /** Optional search notes rendered below the headline (no_evidence_found). */
  searchNotes?: string | null;
  /** Optional heading override. */
  heading?: string;
}

/**
 * Honest-empty state (report §12.3): one of three truths — not yet,
 * nothing found, or cut at limit — never a silent blank.
 *
 * For `nothing_found`, the search notes (what was looked for) are rendered
 * so the absence is auditable rather than assumed.
 */
export function HonestEmpty({ truth, searchNotes, heading }: HonestEmptyProps) {
  return (
    <div className={`honest-empty honest-empty-${truth}`}>
      <p className="honest-empty-head">{heading ?? EMPTY_TRUTHS[truth]}</p>
      {truth === "nothing_found" && searchNotes && (
        <p className="honest-empty-notes">
          <span className="honest-empty-notes-label">What was searched: </span>
          {searchNotes}
        </p>
      )}
    </div>
  );
}
