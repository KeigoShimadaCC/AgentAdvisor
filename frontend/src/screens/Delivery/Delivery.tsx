import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { CaseCrumb } from "../shell/CaseCrumb";
import { Skeleton } from "../shared/Skeleton";
import { useToast } from "../shared/Toast";
import { readReactions, revisionNoteFrom, clearReactions } from "../../engagement/reactions";
import { useCaseView } from "../shared/useCaseView";
import { InspectorHost } from "../inspector/InspectorHost";
import { CitationLink } from "../inspector/CitationLink";
import { CitationText } from "../inspector/CitationText";
import { FailurePath } from "../shared/FailurePath";
import { Dissent, independentReviewFrom, isBlockingDissent } from "../Brief/Dissent";
import { ProbabilityBand } from "../../uncertainty/ProbabilityBand";
import { ConfidenceBands } from "../../uncertainty/ConfidenceBands";
import { SourceStrengthGrade } from "../../uncertainty/SourceStrengthGrade";
import { StabilityDots } from "../../uncertainty/StabilityDots";
import { NotAssessedWidget } from "../../uncertainty/NotAssessedWidget";
import { api, type MonitoringResponse } from "../../api/client";
import {
  BRIEF_SECTION_TITLES,
  EMPTY_TRUTHS,
  FAILURE_COPY,
  TRIPWIRE_COPY,
  ACTION_PLAN_COPY,
} from "../../copy/terms";
import { provenanceVoice } from "../../copy/voices";
import { honestSentence } from "../../copy/honestSentence";
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
  // SPEC-051: three hours of passive reading accumulate into a position. What
  // the reader marked as wrong or as under-weighted is what the note should
  // open with, rather than an empty box at the one moment it matters.
  const [revisionNote, setRevisionNote] = useState(() =>
    caseId ? revisionNoteFrom(readReactions(caseId)) : "",
  );
  const [revisionSent, setRevisionSent] = useState(false);
  const [confirmingSendBack, setConfirmingSendBack] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    if (!caseId) return;
    setFinalLoading(true);
    api
      .getFinalRecommendation(caseId)
      .then((env) => setFinal(env.data))
      .catch(() => setFinal(null))
      .finally(() => setFinalLoading(false));
  }, [caseId]);

  if (loading || finalLoading) return <Skeleton shape="brief" label="Loading the recommendation" />;
  if (error) return <p className="error" role="alert">{error}</p>;
  if (!view) return <p>No data.</p>;

  // SPEC-039's independent reviewer sees the conclusion and the evidence but
  // not the reasoning, and a dissent from it blocks delivery. Rendering the
  // dissent while leaving the signature live would make the block advisory.
  const independentReview = independentReviewFrom(view);
  const blocked = isBlockingDissent(independentReview);
  const canAccept = view.stage === "awaiting_final_approval" && !blocked;
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
      toast.show("Recommendation accepted and signed.", "success");
    } catch (e) {
      const detail = (e as { detail?: string; error?: string }).detail ?? "Accept failed";
      setActionError(detail);
      toast.show(detail, "error");
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
      // Spent: the marks have been said, and re-offering them on the next pass
      // would put stale objections in a fresh note.
      clearReactions(caseId);
      toast.show("Sent back with your note — synthesis will re-run.", "success");
    } catch (e) {
      const detail =
        (e as { detail?: string; error?: string }).detail ?? "Send back failed";
      setActionError(detail);
      toast.show(detail, "error");
    } finally {
      setSubmitting(false);
    }
  }

  if (signed) {
    return (
      <InspectorHost events={events}>
        <div className="delivery signed">
          <CaseCrumb caseId={caseId} label={FAILURE_COPY.backToCase} />
          <h2>Recommendation accepted</h2>
          <p>Signed by user at {new Date().toLocaleString()}.</p>
        </div>
      </InspectorHost>
    );
  }

  if (revisionSent) {
    return (
      <InspectorHost events={events}>
        <div className="delivery revision-sent">
          <CaseCrumb caseId={caseId} label={FAILURE_COPY.backToCase} />
          <h2>Revision requested</h2>
          <p>
            The case will re-run synthesis with your note. You can follow progress
            on the brief.
          </p>
        </div>
      </InspectorHost>
    );
  }

  return (
    <InspectorHost events={events}>
      <div className="delivery">
        <CaseCrumb caseId={caseId} label={FAILURE_COPY.backToCase} />
        <h2>Delivery</h2>
        <FailurePath view={view} />
        <Dissent
          divergence={view.rooms?.challenges?.track_divergence}
          independentReview={independentReview}
        />

        {final && (
          <>
            <section className="answer-card" aria-label="Answer">
              <h3>Recommended action</h3>
              <p className="answer-recommendation"><CitationText>{final.recommended_action}</CitationText></p>
              <p className="answer-timing">Timing: <CitationText>{final.timing}</CitationText></p>
            </section>

            {/* SPEC-050: one honest sentence, then the reasons. The four
                encodings used to sit between the answer and its reasons, so a
                reader asking "how sure is this" got a dashboard instead of an
                answer. They are unchanged in substance, one click down. */}
            <p className="honest-sentence">{honestSentence(view.uncertainty).text}</p>

            <section className="key-reasons" aria-label="Key reasons">
              <h3>Why this recommendation</h3>
              <ul>
                {final.key_reasons.slice(0, 4).map((reason, i) => (
                  <li key={i}><CitationText>{reason}</CitationText></li>
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

            {/* The action-plan slot (SPEC-050). `MonitoringPanel` has existed
                since SPEC-042 and was never rendered by anything — a whole
                feature written, tested and invisible. It is wired here, and it
                returns null when a case has no plan, which is the normal case
                for an in-flight decision. SPEC-053 fills the rest of the slot
                with phase 8 SPEC-041's typed action plan. */}
            {caseId && <MonitoringPanel caseId={caseId} />}

            <details className="uncertainty-disclosure">
              <summary>How sure is this?</summary>
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
            </details>

            <IntegritySlip view={view} />

            <FullBrief sections={view.brief_sections ?? []} />
          </>
        )}

        {blocked && view.stage === "awaiting_final_approval" && (
          <section className="signature signature-blocked" aria-label="Signature">
            <h3>Your signature</h3>
            <p className="screen-help">
              Signing is blocked while the independent reviewer's dissent stands. It is shown
              above, with the conclusion that reviewer would reach instead.
            </p>
          </section>
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
              {/* SPEC-050: MAX_FINAL_REVISIONS is 1, so this button spends the
                  only send-back the case has. A one-shot, irreversible action
                  behind a single click is a trap; the confirmation names what
                  it costs rather than asking "are you sure". */}
              {confirmingSendBack ? (
                <div className="send-back-confirm" role="alertdialog" aria-label="Confirm send back">
                  <p className="send-back-cost">
                    This is the only send-back this case has. Once it is used, the next
                    recommendation is the one you accept or leave.
                  </p>
                  <button
                    type="button"
                    className="secondary-action"
                    onClick={handleSendBack}
                    disabled={submitting}
                  >
                    Send it back
                  </button>
                  <button
                    type="button"
                    className="tertiary-action"
                    onClick={() => setConfirmingSendBack(false)}
                    disabled={submitting}
                  >
                    Keep reading
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  className="secondary-action"
                  onClick={() => setConfirmingSendBack(true)}
                  disabled={!canSendBack || !revisionNote.trim() || submitting}
                >
                  Send back
                </button>
              )}
              {!canSendBack && hasReviseApproval && (
                <p className="screen-help">
                  Final revision cap reached — you can only send back once.
                </p>
              )}
            </div>
            {actionError && <p className="error" role="alert">{actionError}</p>}
          </section>
        )}

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
          <li key={i}><CitationText>{t}</CitationText></li>
        ))}
      </ul>
    </section>
  );
}

/**
 * SPEC-042 — what to watch after delivery, and the prepared responses.
 *
 * Replaces nothing: the tripwire list stays, because it is the recommendation's own
 * statement of what would change it. This shows the *tracked* version — observables with
 * thresholds and cadences — plus which checks are overdue right now.
 */
function MonitoringPanel({ caseId }: { caseId: string }) {
  const [data, setData] = useState<MonitoringResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getMonitoring(caseId)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch(() => {
        // A missing plan is the normal case for an in-flight decision, not an error.
        if (!cancelled) setData({ plan: null, due: [] });
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  if (!data?.plan || data.plan.indicators.length === 0) return null;
  const { plan, due } = data;
  const dueIds = new Set(due.map((d) => d.indicator_id));

  return (
    <section className="monitoring-panel" aria-label={ACTION_PLAN_COPY.monitoringTitle}>
      <h3>{ACTION_PLAN_COPY.monitoringTitle}</h3>
      <p className="section-help">{ACTION_PLAN_COPY.monitoringHelp}</p>
      {!plan.concretized && (
        <p className="monitoring-warning">{ACTION_PLAN_COPY.notConcretized}</p>
      )}
      <ul className="monitoring-list">
        {plan.indicators.map((indicator) => (
          <li
            key={indicator.indicator_id}
            className={`monitoring-item${dueIds.has(indicator.indicator_id) ? " due" : ""}`}
          >
            <span className="monitoring-observable">{indicator.observable}</span>
            {dueIds.has(indicator.indicator_id) && (
              <span className="monitoring-due-badge">{ACTION_PLAN_COPY.dueLabel}</span>
            )}
            <dl className="monitoring-detail">
              <dt>{ACTION_PLAN_COPY.thresholdLabel}</dt>
              <dd>{indicator.threshold}</dd>
              <dt>{ACTION_PLAN_COPY.cadenceLabel}</dt>
              <dd>{indicator.check_cadence_days} days</dd>
              <dt>{ACTION_PLAN_COPY.wouldImplyLabel}</dt>
              <dd>{indicator.would_imply}</dd>
            </dl>
          </li>
        ))}
      </ul>
      {plan.mitigations.length > 0 && (
        <>
          <h4>{ACTION_PLAN_COPY.mitigationsTitle}</h4>
          <ul className="mitigation-list">
            {plan.mitigations.map((m) => (
              <li key={m.mitigation_id}>
                <span className="mitigation-text">{m.mitigation}</span>
                <span className="mitigation-owner">
                  {ACTION_PLAN_COPY.ownerLabel}: {m.owner}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
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
              <span
                className={`provenance-stripe provenance-${block.provenance}`}
                title={provenanceVoice(block.provenance).blurb}
              >
                {provenanceVoice(block.provenance).label}
              </span>
              <p><CitationText>{block.text}</CitationText></p>
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
