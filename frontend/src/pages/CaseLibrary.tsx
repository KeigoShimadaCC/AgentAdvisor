import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type CaseSummary } from "../api/client";

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

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="error">{error}</p>;
  if (cases.length === 0) return <p>No cases yet.</p>;

  return (
    <table className="case-list">
      <thead>
        <tr>
          <th>Case</th>
          <th>Stage</th>
          <th>Updated</th>
        </tr>
      </thead>
      <tbody>
        {cases.map((c) => (
          <tr key={c.case_id}>
            <td><Link to={`/cases/${c.case_id}`}>{c.title}</Link></td>
            <td>{c.stage}</td>
            <td>{c.updated.slice(0, 19).replace("T", " ")}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
