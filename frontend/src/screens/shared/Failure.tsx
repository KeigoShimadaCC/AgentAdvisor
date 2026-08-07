import { Link } from "react-router-dom";
import { stageLabel } from "../../copy/terms";
import type { ErrorResponse } from "../../api/client";

/**
 * What went wrong, said precisely (SPEC-055).
 *
 * Every failure used to render as `<p className="error">{detail}</p>` — one red
 * paragraph for "the service is not running", "this case does not exist" and
 * "another writer holds this case". Those are three different situations with
 * three different next actions, and a user who cannot tell them apart cannot
 * act on any of them.
 *
 * The taxonomy is the service's own (SPEC-033); this consumes it rather than
 * inventing a second one.
 */
export function Failure({ error, onRetry }: { error: ErrorResponse; onRetry?: () => void }) {
  const kind = classify(error);

  return (
    <section className={`failure failure-${kind}`} role="alert">
      <h2>{TITLES[kind]}</h2>
      <p className="failure-what">{BODIES[kind](error)}</p>

      <div className="failure-actions">
        {onRetry && (
          <button type="button" className="primary-action" onClick={onRetry}>
            Try again
          </button>
        )}
        <Link to="/" className="secondary-action">
          Back to your cases
        </Link>
      </div>

      {/* The service's own words, kept: a user reporting this needs the detail,
          and hiding it would make the message unactionable for whoever helps. */}
      {error.detail && <p className="failure-detail">{error.detail}</p>}
    </section>
  );
}

type Kind = "unavailable" | "not_found" | "locked" | "invalid" | "unknown";

export function classify(error: ErrorResponse): Kind {
  if (error.status === 0 || error.error === "service_unavailable") return "unavailable";
  if (error.status === 404) return "not_found";
  if (error.status === 409) return "locked";
  if (error.status === 422) return "invalid";
  return "unknown";
}

const TITLES: Record<Kind, string> = {
  unavailable: "The service is not running",
  not_found: "That case does not exist",
  locked: "This case is being written to",
  invalid: "That request was not valid",
  unknown: "Something went wrong",
};

const BODIES: Record<Kind, (error: ErrorResponse) => string> = {
  unavailable: () =>
    "Nothing was lost — cases live on disk, not in this page. Start the service and try again.",
  not_found: () =>
    "The link may be stale, or the case may have been removed from the cases directory.",
  locked: (error) =>
    error.case_stage
      ? `A worker is running this case (${stageLabel(error.case_stage)}). Controls unlock when it reaches a checkpoint.`
      : "A worker holds this case. Controls unlock when it reaches a checkpoint.",
  invalid: () => "The service rejected the request. The details below say why.",
  unknown: () => "The service returned an error that this screen does not recognise.",
};
