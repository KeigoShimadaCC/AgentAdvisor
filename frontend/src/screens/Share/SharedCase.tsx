import { useParams } from "react-router-dom";
import { useCaseView } from "../shared/useCaseView";
import { InspectorHost } from "../inspector/InspectorHost";
import { CitationText } from "../inspector/CitationText";
import { Dissent, independentReviewFrom } from "../Brief/Dissent";
import { Skeleton } from "../shared/Skeleton";
import { BRIEF_SECTION_TITLES, EMPTY_TRUTHS } from "../../copy/terms";
import { provenanceVoice } from "../../copy/voices";
import { CANONICAL_SECTION_ORDER } from "../../export/markdown";

/**
 * A case, read-only, for someone who did not run it (SPEC-052).
 *
 * No controls, no altitude, no rooms — a document. The read-only guarantee is
 * not enforced here but at the service, which already refuses every control
 * POST in replay mode with a 409; this route is that same guarantee applied to
 * a live case directory, so there is one mechanism rather than two. A client
 * that merely *omits* the buttons is not read-only, and the e2e test asserts
 * the POST, not the absence of a button.
 *
 * Local by design. The link is a URL on a service bound to 127.0.0.1, and the
 * copy says so rather than implying a hosted document.
 */
export function SharedCase() {
  const { caseId } = useParams<{ caseId: string }>();
  const { view, events, loading, error } = useCaseView(caseId);

  if (loading) return <Skeleton shape="brief" label="Loading the shared brief" />;
  if (error) return <p className="error" role="alert">{error}</p>;
  if (!view) return <p>No data.</p>;

  const rank = new Map(CANONICAL_SECTION_ORDER.map((key, i) => [key, i]));
  const sections = [...(view.brief_sections ?? [])].sort(
    (a, b) =>
      (rank.get(a.key) ?? CANONICAL_SECTION_ORDER.length) -
      (rank.get(b.key) ?? CANONICAL_SECTION_ORDER.length),
  );

  return (
    <InspectorHost events={events}>
      <article className="shared-case">
        <header className="shared-case-head">
          <h2 className="shared-case-question">{view.decision_question || view.case_id}</h2>
          <p className="shared-case-provenance">
            Produced by AgentAdvisor. This is analysis, not licensed advice.
            {!view.is_terminal && " This case had not finished when this was shared."}
          </p>
        </header>

        <Dissent
          divergence={view.rooms?.challenges?.track_divergence}
          independentReview={independentReviewFrom(view)}
        />

        <div className="brief-document">
          {sections.length === 0 ? (
            <p className="screen-help">{EMPTY_TRUTHS.not_yet}</p>
          ) : (
            sections.map((section) => (
              <section key={section.key} className="brief-passage" data-status={section.status}>
                <h3 className="brief-passage-label">
                  {BRIEF_SECTION_TITLES[section.key] ?? section.key}
                </h3>
                {section.status === "pending" && (
                  <p className="brief-passage-placeholder">{EMPTY_TRUTHS.not_yet}</p>
                )}
                {section.status === "not_assessed" && (
                  <p className="brief-passage-placeholder">Not assessed for this case.</p>
                )}
                {section.blocks?.map((block, i) => (
                  <div key={i} className="brief-block">
                    <span
                      className={`provenance-stripe provenance-${block.provenance}`}
                      title={provenanceVoice(block.provenance).blurb}
                    >
                      {provenanceVoice(block.provenance).label}
                    </span>
                    <p
                      className={
                        section.key === "executive_recommendation" && i === 0
                          ? "brief-passage-text answer-recommendation"
                          : "brief-passage-text"
                      }
                    >
                      <CitationText>{block.text}</CitationText>
                    </p>
                  </div>
                ))}
              </section>
            ))
          )}
        </div>
      </article>
    </InspectorHost>
  );
}
