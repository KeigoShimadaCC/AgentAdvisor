import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, type ErrorResponse } from "../../api/client";
import type { FramingApproval } from "../../generated/framing_approval";
import type { CaseView } from "../../generated/case_view";
import { SIGNED_COPY, GROUND_RULE_LABELS } from "../../copy/terms";

/**
 * Read-only view of the signed scope checkpoint (SPEC-034).
 *
 * Renders who signed, when, the confirmations and sheet hash, and what
 * changed since the last revision — sourced from the ``FramingApproval``
 * artifact and the case view.
 */
export function SignedRecord() {
  const { caseId } = useParams<{ caseId: string }>();
  const [approval, setApproval] = useState<FramingApproval | null>(null);
  const [view, setView] = useState<CaseView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    setLoading(true);
    Promise.all([
      api.getFramingApproval(caseId).catch(() => null),
      api.getCaseView(caseId).catch(() => null),
    ])
      .then(([approvalEnv, v]) => {
        if (approvalEnv) setApproval(approvalEnv.data);
        if (v) setView(v);
      })
      .catch((e: ErrorResponse) => setError(e.detail ?? e.error))
      .finally(() => setLoading(false));
  }, [caseId]);

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="error" role="alert">{error}</p>;
  if (!approval) {
    return (
      <div className="signed-record">
        <h2>{SIGNED_COPY.title}</h2>
        <p>The signed scope record is not available yet.</p>
        <p className="back-link">
          <Link to={caseId ? `/cases/${caseId}` : "/"}>{SIGNED_COPY.backToCase}</Link>
        </p>
      </div>
    );
  }

  const editedFields = Object.keys(approval.edits ?? {});
  const answeredFields = Object.keys(approval.clarification_answers ?? {});

  return (
    <div className="signed-record">
      <h2>{SIGNED_COPY.title}</h2>

      <dl className="signed-meta">
        <dt>{SIGNED_COPY.signedBy}</dt>
        <dd>{approval.approved_by}</dd>
        <dt>{SIGNED_COPY.signedAt}</dt>
        <dd>{approval.approved_at.replace("T", " ").replace(/\.\d+Z$/, " UTC")}</dd>
      </dl>

      <section className="signed-section">
        <h3>{SIGNED_COPY.whatChanged}</h3>
        {editedFields.length === 0 && answeredFields.length === 0 ? (
          <p>{SIGNED_COPY.noChanges}</p>
        ) : (
          <ul className="signed-changes">
            {editedFields.map((f) => (
              <li key={f}>Edited: {f}</li>
            ))}
            {answeredFields.map((f) => (
              <li key={f}>Answered clarification: {GROUND_RULE_LABELS[f] ?? f}</li>
            ))}
          </ul>
        )}
      </section>

      {view && (
        <section className="signed-section">
          <h3>Case status</h3>
          <p>The investigation is now running. You can follow along on the case page.</p>
        </section>
      )}

      <p className="back-link">
        <Link to={caseId ? `/cases/${caseId}` : "/"}>{SIGNED_COPY.backToCase}</Link>
      </p>
    </div>
  );
}
