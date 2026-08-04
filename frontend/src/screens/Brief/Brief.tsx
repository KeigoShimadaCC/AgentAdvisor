import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useCaseView } from "../shared/useCaseView";
import { InspectorHost } from "../inspector/InspectorHost";
import { CitationLink } from "../inspector/CitationLink";
import { CitationText } from "../inspector/CitationText";
import { FailurePath } from "../shared/FailurePath";
import { MarginNarration } from "./MarginNarration";
import { WorkingViewCard } from "./WorkingViewCard";
import { MethodStrip } from "./MethodStrip";
import { SealedAnswerCard } from "./SealedAnswerCard";
import {
  BRIEF_SECTION_TITLES,
  EMPTY_TRUTHS,
  FAILURE_COPY,
  provenanceLabel,
} from "../../copy/terms";
import type { BriefSection } from "../../generated/case_view";

const STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  partial: "Partial",
  final: "Final",
  not_assessed: "Not assessed",
};

export function Brief() {
  const { caseId } = useParams<{ caseId: string }>();
  const { view, events, loading, error } = useCaseView(caseId);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [settleKeys, setSettleKeys] = useState<Set<string>>(new Set());
  const prevSections = useRef<BriefSection[] | undefined>(undefined);

  useEffect(() => {
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mql.matches);
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);

  useEffect(() => {
    const current = view?.brief_sections;
    const prev = prevSections.current;
    prevSections.current = current;
    if (prev && current) {
      const prevMap = new Map(prev.map((s) => [s.key, s.status]));
      const changed = new Set<string>();
      for (const s of current) {
        if (prevMap.get(s.key) === "pending" && s.status !== "pending") {
          changed.add(s.key);
        }
      }
      if (changed.size > 0) {
        setSettleKeys(changed);
        const t = setTimeout(() => setSettleKeys(new Set()), 300);
        return () => clearTimeout(t);
      }
    }
  }, [view?.brief_sections]);

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="error" role="alert">{error}</p>;
  if (!view) return <p>No data.</p>;

  const sections = view.brief_sections ?? [];
  const isFailed = view.stage === "failed";

  const body = (
    <div className="brief">
      <div className="brief-header">
        <h2>{view.case_id}</h2>
        <p className="screen-help">Living brief</p>
      </div>

      {isFailed ? (
        <section className="failure-path" role="alert">
          <h3>{FAILURE_COPY.failedTitle}</h3>
          <p>{FAILURE_COPY.failedDetail}</p>
          <Link to={`/cases/${caseId}`} className="secondary-action">
            {FAILURE_COPY.backToCase}
          </Link>
        </section>
      ) : (
        <>
          <MethodStrip view={view} />
          <SealedAnswerCard stage={view.stage} />
          <WorkingViewCard
            caseId={view.case_id}
            revisions={view.history?.thesis_revisions ?? []}
          />
          <MarginNarration events={events} />
          <FailurePath view={view} />
          <section className="brief-sections" aria-label="Brief sections">
            {sections.length === 0 ? (
              <p className="screen-help">{EMPTY_TRUTHS.not_yet}</p>
            ) : (
              sections.map((section) => (
                <BriefSectionCard
                  key={section.key}
                  section={section}
                  settle={settleKeys.has(section.key) && !reducedMotion}
                />
              ))
            )}
          </section>
        </>
      )}

      <p className="back-link">
        <Link to={`/cases/${caseId}`}>{FAILURE_COPY.backToCase}</Link>
      </p>
    </div>
  );

  return <InspectorHost events={events}>{body}</InspectorHost>;
}

function BriefSectionCard({
  section,
  settle,
}: {
  section: BriefSection;
  settle: boolean;
}) {
  const title = BRIEF_SECTION_TITLES[section.key] ?? section.key;
  const isPending = section.status === "pending";
  const isNotAssessed = section.status === "not_assessed";

  return (
    <article
      className={`brief-section ${settle ? "brief-section-settle" : ""}`}
      data-status={section.status}
      aria-label={title}
    >
      <h3 className="brief-section-title">
        {title}
        <span
          className={`brief-section-status status-${section.status}`}
          aria-label={`status ${section.status}`}
        >
          {STATUS_LABELS[section.status] ?? section.status}
        </span>
      </h3>
      {isPending && <p className="brief-section-placeholder">{EMPTY_TRUTHS.not_yet}</p>}
      {isNotAssessed && (
        <p className="brief-section-placeholder">Not assessed for this case.</p>
      )}
      {!isPending && !isNotAssessed && (
        <div className="brief-section-body">
          {section.blocks?.map((block, i) => (
            <div key={i} className="brief-block">
              <span className="provenance-stripe">
                {provenanceLabel(block.provenance)}
              </span>
              <p className="brief-block-text"><CitationText>{block.text}</CitationText></p>
              {block.citation_ids && block.citation_ids.length > 0 && (
                <div className="brief-block-citations">
                  {block.citation_ids.map((id) => (
                    <CitationLink key={id} id={id} />
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </article>
  );
}
