import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type CaseSummary } from "../api/client";
import { stageLabel, NEEDS_YOU, type NeedsYouKey } from "../copy/terms";
import { Skeleton } from "../screens/shared/Skeleton";

/** Derive a needs-you state from the raw stage string (list endpoint). */
function needsYouFromStage(stage: string): NeedsYouKey {
  if (stage === "awaiting_framing_approval") return "scope_checkpoint";
  if (stage === "awaiting_final_approval") return "delivery_checkpoint";
  if (stage === "failed") return "interrupted";
  return "none";
}

/** The route a case should funnel into based on its needs-you state. */
function funnelRoute(c: CaseSummary): string {
  const needs = needsYouFromStage(c.stage);
  if (needs === "scope_checkpoint") return `/cases/${c.case_id}/scope`;
  return `/cases/${c.case_id}`;
}

export function CaseLibrary() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listCases()
      .then(setCases)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Skeleton shape="list" label="Loading your cases" />;
  if (error) return <p className="error">{error}</p>;
  if (cases.length === 0) {
    return (
      <div className="case-library-empty">
        <p>No cases yet.</p>
        <Link to="/new" className="primary-action">Start a new decision</Link>
      </div>
    );
  }

  const needsYouCases = cases.filter((c) => needsYouFromStage(c.stage) !== "none");

  return (
    <div className="case-library">
      {needsYouCases.length > 0 && (
        <section className="needs-you-header" aria-label="Cases that need you">
          <h2>Waiting on you</h2>
          <ul className="needs-you-list">
            {needsYouCases.map((c) => {
              const needs = needsYouFromStage(c.stage);
              const desc = NEEDS_YOU[needs];
              return (
                <li key={c.case_id} className="needs-you-row">
                  <Link to={funnelRoute(c)} className="needs-you-link">
                    <span className="needs-you-title">{c.title}</span>
                    <span className="needs-you-badge">{desc.badge}</span>
                  </Link>
                  <p className="needs-you-consequence">{desc.consequence}</p>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <table className="case-list">
        <thead>
          <tr>
            <th>Case</th>
            <th>Status</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((c) => {
            const needs = needsYouFromStage(c.stage);
            const desc = NEEDS_YOU[needs];
            return (
              <tr key={c.case_id}>
                <td>
                  <Link to={funnelRoute(c)}>{c.title}</Link>
                  {needs !== "none" && (
                    <span className={`needs-you-pill pill-${needs}`}>{desc.badge}</span>
                  )}
                </td>
                <td>{stageLabel(c.stage)}</td>
                <td>{c.updated.slice(0, 19).replace("T", " ")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
