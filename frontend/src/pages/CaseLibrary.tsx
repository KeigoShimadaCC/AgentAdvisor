import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type CaseSummary, type ErrorResponse } from "../api/client";
import { stageLabel, NEEDS_YOU, type NeedsYouKey } from "../copy/terms";
import { Skeleton } from "../screens/shared/Skeleton";
import { Failure } from "../screens/shared/Failure";

/**
 * The library as a workspace (SPEC-052).
 *
 * Was a three-column table — case, status, updated — which showed less than
 * `advisor status` does in a terminal, for a product whose engagements run for
 * hours. And it derived needs-you from the raw stage string with a local
 * `needsYouFromStage`, a second copy of a rule the projection already
 * implements: two implementations of one rule is one implementation and one
 * future bug.
 *
 * `needs_you` now comes from the server (SPEC-046 added it to `CaseSummary`),
 * grouping is by that field, and the derivation is gone.
 */

/** Where a case should funnel to, given what it is waiting for. */
function funnelRoute(c: CaseSummary): string {
  if (c.needs_you === "scope_checkpoint") return `/cases/${c.case_id}/scope`;
  if (c.needs_you === "delivery_checkpoint") return `/cases/${c.case_id}/delivery`;
  return `/cases/${c.case_id}`;
}

const TERMINAL_STAGES = new Set(["done", "failed"]);

interface Group {
  key: string;
  heading: string;
  blurb: string;
  cases: CaseSummary[];
}

export function groupCases(cases: CaseSummary[]): Group[] {
  const waiting = cases.filter((c) => c.needs_you !== "none");
  const running = cases.filter((c) => c.needs_you === "none" && !TERMINAL_STAGES.has(c.stage));
  const finished = cases.filter((c) => c.needs_you === "none" && TERMINAL_STAGES.has(c.stage));

  return [
    {
      key: "waiting",
      heading: "Waiting on you",
      blurb: "These will not proceed until you act.",
      cases: waiting,
    },
    { key: "running", heading: "Running", blurb: "Working now. You can leave the page.", cases: running },
    { key: "done", heading: "Finished", blurb: "", cases: finished },
  ].filter((group) => group.cases.length > 0);
}

/** Case-insensitive match over what a user would actually type: the question. */
export function filterCases(cases: CaseSummary[], query: string): CaseSummary[] {
  const q = query.trim().toLowerCase();
  if (!q) return cases;
  return cases.filter(
    (c) => c.title.toLowerCase().includes(q) || c.case_id.toLowerCase().includes(q),
  );
}

export function CaseLibrary() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ErrorResponse | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    setLoading(true);
    api
      .listCases()
      .then((next) => {
        setCases(next);
        setError(null);
      })
      .catch((e: ErrorResponse) => setError(e))
      .finally(() => setLoading(false));
  }, [attempt]);

  const groups = useMemo(() => groupCases(filterCases(cases, query)), [cases, query]);

  if (loading) return <Skeleton shape="list" label="Loading your cases" />;
  // SPEC-055: "the service is not running" is a different fact from "you have
  // no cases", and the empty state below must not stand in for it.
  if (error) return <Failure error={error} onRetry={() => setAttempt((n) => n + 1)} />;
  if (cases.length === 0) {
    return (
      <div className="case-library-empty">
        <p>No cases yet.</p>
        <Link to="/new" className="primary-action">Start a new decision</Link>
      </div>
    );
  }

  return (
    <div className="case-library">
      <div className="library-search">
        <label htmlFor="library-search" className="sr-only">Search your decisions</label>
        <input
          id="library-search"
          type="search"
          className="library-search-input"
          placeholder="Search your decisions"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {groups.length === 0 && (
        <p className="screen-help">No decision matches “{query}”.</p>
      )}

      {groups.map((group) => (
        <section key={group.key} className={`library-group library-group-${group.key}`} aria-label={group.heading}>
          <h2 className="library-group-heading">{group.heading}</h2>
          {group.blurb && <p className="library-group-blurb">{group.blurb}</p>}
          <ul className="library-cards">
            {group.cases.map((c) => (
              <CaseCard key={c.case_id} summary={c} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function CaseCard({ summary }: { summary: CaseSummary }) {
  const needs = NEEDS_YOU[summary.needs_you as NeedsYouKey] ?? NEEDS_YOU.none;
  const waiting = summary.needs_you !== "none";

  return (
    <li className={`library-card${waiting ? " library-card-waiting" : ""}`}>
      <Link to={funnelRoute(summary)} className="library-card-link">
        {/* The decision question leads. The old table led with a slug. */}
        <span className="library-card-question">{summary.title}</span>
      </Link>
      <p className="library-card-meta">
        {needs.badge && <span className={`needs-you-pill pill-${summary.needs_you}`}>{needs.badge}</span>}
        <span className="library-card-stage">{stageLabel(summary.stage)}</span>
        <span className="library-card-updated">{summary.updated.slice(0, 16).replace("T", " ")}</span>
      </p>
      {/* The consequence line, on the card rather than a page away: a user
          scanning the library needs to know that nothing moves without them. */}
      {waiting && <p className="library-card-consequence">{needs.consequence}</p>}
    </li>
  );
}
