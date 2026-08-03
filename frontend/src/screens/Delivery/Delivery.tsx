import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useCaseView } from "../shared/useCaseView";
import { InspectorHost } from "../inspector/InspectorHost";
import { CitationLink } from "../inspector/CitationLink";
import { FailurePath } from "../shared/FailurePath";
import { ProbabilityBand } from "../../uncertainty/ProbabilityBand";
import { ConfidenceBands } from "../../uncertainty/ConfidenceBands";
import { SourceStrengthGrade } from "../../uncertainty/SourceStrengthGrade";
import { StabilityDots } from "../../uncertainty/StabilityDots";
import { NotAssessedWidget } from "../../uncertainty/NotAssessedWidget";
import { api } from "../../api/client";
import {
  BRIEF_SECTION_TITLES,
  EMPTY_TRUTHS,
  FAILURE_COPY,
  TRIPWIRE_COPY,
  provenanceLabel,
} from "../../copy/terms";
import type { FinalRecommendation } from "../../generated/final_recommendation";
import type { CaseView, BriefSection } from "../../generated/case_view";
import type { ProbabilityView } from "../../generated/uncertainty_view";

export function Delivery() {
  const { caseId } = useParams<{ caseId: string }>();
  const { view, events, loading, error } = useCaseView(caseId);
  const [final, setFinal] = useState<FinalRecommendation | null>(null);
  const [finalLoading, setFinalLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [signed, setSigned] = useState(false);
  const [revisionNote, setRevisionNote] = useState("");
  const [revisionSent, setRevisionSent] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    setFinalLoading(true);
    api
      .getFinalRecommendation(caseId)
      .then((env) => setFinal(env.data))
      .catch(() => setFinal(null))
      .finally(() => setFinalLoading(false));
  }, [caseId]);

  if (loading || finalLoading) return <p>Loading…</p>;
  if (error) return <p className="error" role="alert">{error}</p>;
  if (!view) return <p>No data.</p>;

  const canAccept = view.stage === "awaiting_final_approval";
  const hasReviseApproval = (view.history?.approvals ?? []).some(
    (a) => a.kind === "final" && a.decision === "revise",
  );
  const canSendBack = canAccept && !hasReviseApproval;

  async function handleAccept() {
    if (!caseId || !canAccept) return;
    setSubmitting(true);
    setActionError(null);
    try {
      await api.approveDelivery(caseId, "user");
      setSigned(true);
    } catch (e) {
      setActionError((e as { detail?: string; error?: string }).detail ?? "Accept failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSendBack() {
    if (!caseId || !canSendBack || !revisionNote.trim()) return;
    setSubmitting(true);
    setActionError(null);
    try {
      await api.requestFinalRevision(caseId, revisionNote.trim());
      setRevisionSent(true);
    } catch (e) {
      setActionError(
        (e as { detail?: string; error?: string }).detail ?? "Send back failed",
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (signed) {
    return (
      <InspectorHost events={events}>
        <div className="delivery signed">
          <h2>Recommendation accepted</h2>
          <p>Signed by user at {new Date().toLocaleString()}.</p>
          <p className="back-link">
            <Link to={`/cases/${caseId}`}>{FAILURE_COPY.backToCase}</Link>
          </p>
        </div>
      </InspectorHost>
    );
  }

  if (revisionSent) {
    return (
      <InspectorHost events={events}>
        <div className="delivery revision-sent">
          <h2>Revision requested</h2>
          <p>
            The case will re-run synthesis with your note. You can follow progress
            on the brief.
          </p>
          <p className="back-link">
            <Link to={`/cases/${caseId}/brief`}>Go to brief</Link>
          </p>
        </div>
      </InspectorHost>
    );
  }

  return (
    <InspectorHost events={events}>
      <div className="delivery">
        <h2>Delivery</h2>
        <FailurePath view={view} />

        {final && (
          <>
            <section className="answer-card" aria-label="Answer">
              <h3>Recommended action</h3>
              <p className="answer-recommendation">{final.recommended_action}</p>
              <p className="answer-timing">Timing: {final.timing}</p>
            </section>

            <section className="uncertainty-widgets" aria-label="Four uncertainty measures">
              <div className="uncertainty-widget">
                <h4>Probability</h4>
                <PrimaryProbability probabilities={view.uncertainty?.outcome_probabilities} />
              </div>
              <div className="uncertainty-widget">
                <h4>Confidence in this recommendation</h4>
                <ConfidenceBands confidence={view.uncertainty?.recommendation_confidence} />
              </div>
              <div className="uncertainty-widget">
                <h4>Source strength</h4>
                <SourceStrengthGrade source={view.uncertainty?.evidence_confidence} />
              </div>
              <div className="uncertainty-widget">
                <h4>Stability</h4>
                <StabilityDots stability={view.uncertainty?.model_stability} />
              </div>
            </section>

            <section className="key-reasons" aria-label="Key reasons">
              <h3>Why this recommendation</h3>
              <ul>
                {final.key_reasons.slice(0, 4).map((reason, i) => (
                  <li key={i}>{reason}</li>
                ))}
              </ul>
              {final.citations && final.citations.length > 0 && (
                <div className="key-reason-citations">
                  {final.citations.slice(0, 8).map((id) => (
                    <CitationLink key={id} id={id} />
                  ))}
                </div>
              )}
            </section>

            <Tripwires triggers={final.recommendation_change_triggers} />

            <IntegritySlip view={view} />

            <FullBrief sections={view.brief_sections ?? []} />
          </>
        )}

        {canAccept && (
          <section className="signature" aria-label="Signature">
            <h3>Your signature</h3>
            <button
              type="button"
              className="primary-action"
              onClick={handleAccept}
              disabled={submitting}
            >
              Accept this recommendation
            </button>

            <div className="send-back">
              <label htmlFor="revision-note">Send back with a note</label>
              <textarea
                id="revision-note"
                value={revisionNote}
                onChange={(e) => setRevisionNote(e.target.value)}
                disabled={!canSendBack || submitting}
                rows={3}
              />
              <button
                type="button"
                className="secondary-action"
                onClick={handleSendBack}
                disabled={!canSendBack || !revisionNote.trim() || submitting}
              >
                Send back
              </button>
              {!canSendBack && hasReviseApproval && (
                <p className="screen-help">
                  Final revision cap reached — you can only send back once.
                </p>
              )}
            </div>
            {actionError && <p className="error" role="alert">{actionError}</p>}
          </section>
        )}

        <p className="back-link">
          <Link to={`/cases/${caseId}`}>{FAILURE_COPY.backToCase}</Link>
        </p>
      </div>
    </InspectorHost>
  );
}

function PrimaryProbability({
  probabilities,
}: {
  probabilities?: Record<string, ProbabilityView>;
}) {
  if (!probabilities) return <NotAssessedWidget reason="No probability estimates" />;
  const entries = Object.entries(probabilities);
  if (entries.length === 0) return <NotAssessedWidget reason="No probability estimates" />;
  const [label, prob] = entries[0];
  return <ProbabilityBand label={label} probability={prob} />;
}

function Tripwires({ triggers }: { triggers?: string[] }) {
  if (!triggers || triggers.length === 0) {
    return (
      <section className="tripwires" aria-label="Tripwires">
        <h3>{TRIPWIRE_COPY.title}</h3>
        <p>{TRIPWIRE_COPY.empty}</p>
      </section>
    );
  }
  return (
    <section className="tripwires" aria-label="Tripwires">
      <h3>{TRIPWIRE_COPY.title}</h3>
      <ul>
        {triggers.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
    </section>
  );
}

function IntegritySlip({ view }: { view: CaseView }) {
  const review = view.integrity;
  const openHigh =
    view.rooms?.challenges?.objections?.filter(
      (o) => o.resolution_status === "open" && o.materiality === "high",
    ) ?? [];
  const notAssessedSections = (view.brief_sections ?? []).filter(
    (s) => s.status === "not_assessed",
  );
  const notAssessedMeasures = [
    !view.uncertainty?.recommendation_confidence ||
    view.uncertainty.recommendation_confidence.kind === "not_assessed"
      ? "recommendation confidence"
      : null,
    !view.uncertainty?.evidence_confidence ||
    view.uncertainty.evidence_confidence.kind === "not_assessed"
      ? "evidence confidence"
      : null,
    !view.uncertainty?.model_stability ||
    view.uncertainty.model_stability.kind === "not_assessed"
      ? "model stability"
      : null,
  ].filter(Boolean) as string[];

  return (
    <section className="integrity-slip" aria-label="Integrity">
      <h3>Integrity check</h3>
      <p>
        Review verdict:{" "}
        {review?.review_accepted === true
          ? "Accepted"
          : review?.review_accepted === false
            ? "Rejected"
            : "Not reviewed"}
      </p>
      {review?.review_outcome && (
        <p className="screen-help">
          Reviewer's own outcome: {review.review_outcome}
          {review.review_accepted === false
            ? " — the checks below overrode it."
            : ""}
        </p>
      )}
      {/* A rejection is usually driven by deterministic blocking checks rather
          than reviewer-reported defects, so without these the verdict reads as
          "Rejected" with nothing to act on — and next to a "pass" outcome it
          looks like a contradiction. */}
      {review?.review_blocking_findings && review.review_blocking_findings.length > 0 && (
        <div className="integrity-blocking">
          <h4>Why it was rejected</h4>
          <ul>
            {review.review_blocking_findings.map((f, i) => (
              <li key={i}>
                {(f as { message?: string }).message ?? (f as { check_id?: string }).check_id}
              </li>
            ))}
          </ul>
        </div>
      )}
      {review?.review_defects && review.review_defects.length > 0 && (
        <div className="integrity-defects">
          <h4>Defects</h4>
          <ul>
            {review.review_defects.map((d, i) => (
              <li key={i}>{(d as { explanation?: string }).explanation ?? (d as { defect_type?: string }).defect_type}</li>
            ))}
          </ul>
        </div>
      )}
      {openHigh.length > 0 && (
        <div className="integrity-objections">
          <h4>Open high-materiality objections</h4>
          <ul>
            {openHigh.map((o) => (
              <li key={o.objection_id}>{o.claim}</li>
            ))}
          </ul>
        </div>
      )}
      {review?.disclosure && (
        <div className="integrity-disclosure">
          <h4>Disclosure</h4>
          <p>
            Stop reasons:{" "}
            {((review.disclosure.stop_reasons as string[]) ?? []).join(", ")}
          </p>
          <p>
            Exhausted dimensions:{" "}
            {((review.disclosure.exhausted_dimensions as string[]) ?? []).join(", ")}
          </p>
        </div>
      )}
      {(notAssessedSections.length > 0 || notAssessedMeasures.length > 0) && (
        <div className="integrity-not-assessed">
          <h4>Not assessed</h4>
          <ul>
            {notAssessedSections.map((s) => (
              <li key={s.key}>{BRIEF_SECTION_TITLES[s.key] ?? s.key}</li>
            ))}
            {notAssessedMeasures.map((m, i) => (
              <li key={`m-${i}`}>{m}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function FullBrief({ sections }: { sections: BriefSection[] }) {
  return (
    <section className="full-brief" aria-label="Full brief">
      <h3>Full brief</h3>
      {sections.map((section) => (
        <article key={section.key} className="brief-section" data-status={section.status}>
          <h4>{BRIEF_SECTION_TITLES[section.key] ?? section.key}</h4>
          {section.status === "pending" && <p>{EMPTY_TRUTHS.not_yet}</p>}
          {section.status === "not_assessed" && <p>Not assessed.</p>}
          {section.blocks?.map((block, i) => (
            <div key={i} className="brief-block">
              <span className="provenance-stripe">{provenanceLabel(block.provenance)}</span>
              <p>{block.text}</p>
              {block.citation_ids && block.citation_ids.length > 0 && (
                <div className="brief-block-citations">
                  {block.citation_ids.map((id) => (
                    <CitationLink key={id} id={id} />
                  ))}
                </div>
              )}
            </div>
          ))}
        </article>
      ))}
    </section>
  );
}
