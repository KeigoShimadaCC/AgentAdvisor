import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useCaseView } from "../screens/shared/useCaseView";
import { readStoredCursor, hasStoredCursor } from "../api/sse";
import { CaseDataContext } from "../screens/shared/caseContext";
import { InspectorHost } from "../screens/inspector/InspectorHost";
import { CitationText } from "../screens/inspector/CitationText";
import { CitationLink } from "../screens/inspector/CitationLink";
import { Narrator } from "../narration/Narrator";
import { MarginNarration } from "../screens/Brief/MarginNarration";
import { SealedAnswerCard } from "../screens/Brief/SealedAnswerCard";
import { WorkingViewCard } from "../screens/Brief/WorkingViewCard";
import { FailurePath } from "../screens/shared/FailurePath";
import { Dissent, independentReviewFrom } from "../screens/Brief/Dissent";
import { MarginNotes, placeObjections } from "../screens/Brief/MarginNotes";
import { CaseMap, countersFromView } from "../screens/shared/CaseMap";
import { CaseChrome, useAltitude } from "../screens/shell/CaseChrome";
import { AppShell } from "../screens/shell/AppShell";
import { RoomPanel, isRoomKey } from "../screens/shell/RoomPanel";
import { RoomRail } from "../screens/shell/RoomRail";
import { Skeleton } from "../screens/shared/Skeleton";
import { Failure } from "../screens/shared/Failure";
import { StalledCase } from "../screens/shared/StalledCase";
import { AwayDigest } from "../presence/AwayDigest";
import { useCaseTitle } from "../presence/title";
import { useCaseNotices } from "../presence/useCaseNotices";
import { OutcomePrompt } from "../screens/Calibration/OutcomePrompt";
import { ExportControls } from "../export/ExportControls";
import { UncertaintySummary } from "../uncertainty/UncertaintySummary";
import { Why } from "../uncertainty/Why";
import { showsAt } from "../screens/shell/altitude";
import { BRIEF_SECTION_TITLES, EMPTY_TRUTHS, ROOMS } from "../copy/terms";
import { provenanceVoice } from "../copy/voices";
import type { BriefSection, ObjectionView } from "../generated/case_view";

/** Sections that carry the answer itself, and so survive at Answer altitude. */
const ANSWER_SECTIONS = ["executive_recommendation", "decision_confidence"];

/**
 * The one case surface (SPEC-048).
 *
 * `CaseDetail` and `Brief` used to both render `brief_sections`, so a case had
 * two competing homes with no reason to prefer either, and this one opened with
 * a definition list whose rows were Phase, Stage, Status and `Terminal: no` —
 * internal state presented as a spec sheet. Rooms were six more pages, each
 * costing the reader their place in the argument.
 *
 * Now: one surface, persistent chrome carrying the decision question, one
 * altitude control, and rooms opening beside the argument instead of replacing
 * it. Every previous route still resolves here. Borders are reserved for two
 * meanings — this needs your action, or this is uncertain — so a border carries
 * information instead of being wallpaper.
 */
export function CaseDetail() {
  const { caseId, room } = useParams<{ caseId: string; room: string }>();
  const navigate = useNavigate();
  const { view, events, narration, connection, loading, error, failure, retry, stalled } =
    useCaseView(caseId);
  const [altitude, setAltitude] = useAltitude();

  // SPEC-051. The cursor is read once, on mount, before the stream advances it —
  // it is "where this reader was", and reading it later would always be "now".
  //
  // SPEC-052: null when this reader has never opened the case. A first visit is
  // not a return, and "while you were away" on a case you have never seen is
  // both wrong and non-deterministic — it summarised whatever had arrived by
  // the time the screenshot was taken.
  const [arrivalCursor] = useState<number | null>(() =>
    caseId && hasStoredCursor(caseId) ? readStoredCursor(caseId) : null,
  );
  useCaseTitle(view);
  useCaseNotices(view);

  const settleKeys = useSettledSections(view?.brief_sections);
  const caseData = useMemo(() => (view ? { view, events } : null), [view, events]);

  if (loading) return <Skeleton shape="brief" label="Loading the case" />;
  if (failure) return <Failure error={failure} onRetry={retry} />;
  if (error) return <p className="error" role="alert">{error}</p>;
  if (!view || !caseData) return <p>No data.</p>;

  const sections = view.brief_sections ?? [];
  const needsAction = view.needs_you !== "none";
  const deep = showsAt(altitude, "reasoning");
  const openRoom = isRoomKey(room) ? room : undefined;

  // Objections are placed against the passage they attack (SPEC-049); the ones
  // naming a section this brief does not have are shown at the end rather than
  // dropped.
  const objections: ObjectionView[] = view.rooms?.challenges?.objections ?? [];
  const { bySection, unplaced } = placeObjections(
    objections,
    sections.map((s) => s.key),
  );

  return (
    <CaseDataContext.Provider value={caseData}>
      <InspectorHost events={events}>
        <CaseChrome
          view={view}
          connection={connection}
          altitude={altitude}
          onAltitudeChange={setAltitude}
        />

        <AppShell
          panel={openRoom ? <RoomPanel room={openRoom} /> : undefined}
          panelTitle={openRoom ? ROOMS[openRoom].label : undefined}
          onPanelClose={() => navigate(`/cases/${caseId}`)}
          rail={
            deep ? (
              <>
                <CaseMap view={view} counters={countersFromView(view)} />
                {showsAt(altitude, "method") && <RoomRail activeRoom={openRoom} />}
              </>
            ) : undefined
          }
        >
          <div className="case-surface">
            {/* The one bordered element at Answer altitude: it is the thing that
                needs a human. That is what a border is reserved to mean. */}
            {needsAction && caseId && (
              <section className="action-card" aria-label="What this needs from you">
                <p className="action-card-what">
                  {view.needs_you === "scope_checkpoint"
                    ? "This is waiting for you to review the scope."
                    : view.needs_you === "delivery_checkpoint"
                      ? "The recommendation is ready for your decision."
                      : "This case stopped before finishing."}
                </p>
                {view.needs_you !== "interrupted" && (
                  <Link
                    to={
                      view.needs_you === "scope_checkpoint"
                        ? `/cases/${caseId}/scope`
                        : `/cases/${caseId}/delivery`
                    }
                    className="primary-action"
                  >
                    {view.needs_you === "scope_checkpoint"
                      ? "Review the scope"
                      : "Review the recommendation"}
                  </Link>
                )}
              </section>
            )}

            {stalled && caseId && <StalledCase caseId={caseId} />}
            <AwayDigest events={events} sinceCursor={arrivalCursor} />
            <FailurePath view={view} />
            {/* Disagreement sits above the answer, not in a room: a blocked
                signature or a Director split changes how the recommendation
                below should be read. */}
            <Dissent
              divergence={view.rooms?.challenges?.track_divergence}
              independentReview={independentReviewFrom(view)}
            />
            <SealedAnswerCard stage={view.stage} />

            {/* SPEC-054: the same four measures the delivery screen carries, in
                their summary scale. One vocabulary, three densities — a reader
                who learns a band here knows it in a room. */}
            <UncertaintySummary uncertainty={view.uncertainty} />
            {/* The transcript is a collapsed <details> here and the full
                expandable log lives at Method: sixty lines of "Task T-001
                started" in the reading column is the crowding this phase is
                about, and it is the Method room's register, not the brief's. */}
            <Narrator narration={narration} events={events} showTranscript={deep} />

            <section className="brief-document" aria-label="Brief">
              {sections.length === 0 ? (
                <p className="screen-help">{EMPTY_TRUTHS.not_yet}</p>
              ) : (
                sections
                  .filter((s) => deep || ANSWER_SECTIONS.includes(s.key))
                  .map((section) => (
                    <BriefPassage
                      key={section.key}
                      section={section}
                      deep={deep}
                      settle={settleKeys.has(section.key)}
                      objections={deep ? (bySection.get(section.key) ?? []) : []}
                    />
                  ))
              )}
              {deep && <MarginNotes objections={unplaced} unplaced />}
            </section>

            {deep && (
              <WorkingViewCard
                caseId={view.case_id}
                revisions={view.history?.thesis_revisions ?? []}
              />
            )}

            {showsAt(altitude, "method") && <MarginNarration events={events} />}

            {/* The outcome loop closes here (SPEC-051). Until now the only
                caller of POST /outcome was a script, so the record that makes
                the calibration score mean anything could only be fed from a
                terminal. */}
            {view.is_terminal && caseId && <OutcomePrompt caseId={caseId} />}

            {/* A brief that cannot leave the tool is not a package (SPEC-052). */}
            {deep && <ExportControls view={view} />}
          </div>
        </AppShell>
      </InspectorHost>
    </CaseDataContext.Provider>
  );
}

/**
 * Which sections just stopped being pending.
 *
 * Kept from the old Brief screen: a section that fills in while you are reading
 * needs to say so, or new text appears with no signal that it is new. Reduced
 * motion suppresses the animation, not the update.
 */
function useSettledSections(sections: BriefSection[] | undefined): Set<string> {
  const [settleKeys, setSettleKeys] = useState<Set<string>>(new Set());
  const [reducedMotion, setReducedMotion] = useState(false);
  const previous = useRef<BriefSection[] | undefined>(undefined);

  useEffect(() => {
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mql.matches);
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);

  useEffect(() => {
    const prev = previous.current;
    previous.current = sections;
    if (!prev || !sections) return;
    const prevStatus = new Map(prev.map((s) => [s.key, s.status]));
    const changed = new Set<string>();
    for (const s of sections) {
      if (prevStatus.get(s.key) === "pending" && s.status !== "pending") changed.add(s.key);
    }
    if (changed.size === 0) return;
    setSettleKeys(changed);
    const timer = setTimeout(() => setSettleKeys(new Set()), 300);
    return () => clearTimeout(timer);
  }, [sections]);

  return reducedMotion ? new Set() : settleKeys;
}

const STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  partial: "Partial",
  final: "Final",
  not_assessed: "Not assessed",
};

/**
 * One brief section, set as prose with a hanging label (SPEC-048).
 *
 * Was `.brief-section`: a bordered card, one per section, so eight equally
 * weighted boxes said nothing about which one was the recommendation. A
 * document has passages, not cards.
 */
function BriefPassage({
  section,
  deep,
  settle,
  objections,
}: {
  section: BriefSection;
  deep: boolean;
  settle: boolean;
  objections: ObjectionView[];
}) {
  const title = BRIEF_SECTION_TITLES[section.key] ?? section.key;
  const isPending = section.status === "pending";
  const isNotAssessed = section.status === "not_assessed";
  const isRecommendation = section.key === "executive_recommendation";

  return (
    <article
      className={`brief-passage${settle ? " brief-passage-settle" : ""}`}
      data-status={section.status}
      aria-label={title}
    >
      <h3 className="brief-passage-label">
        {title}
        {deep && (
          <span
            className={`brief-passage-status status-${section.status}`}
            aria-label={`status ${section.status}`}
          >
            {STATUS_LABELS[section.status] ?? section.status}
          </span>
        )}
      </h3>

      {isPending && <p className="brief-passage-placeholder">{EMPTY_TRUTHS.not_yet}</p>}
      {isNotAssessed && (
        <p className="brief-passage-placeholder">Not assessed for this case.</p>
      )}

      {!isPending &&
        !isNotAssessed &&
        section.blocks?.map((block, i) => (
          <div key={i} className="brief-block">
            {deep && (
              <span
                className={`provenance-stripe provenance-${block.provenance}`}
                title={provenanceVoice(block.provenance).blurb}
              >
                {provenanceVoice(block.provenance).label}
              </span>
            )}
            <p
              className={
                isRecommendation && i === 0
                  ? "brief-passage-text answer-recommendation"
                  : "brief-passage-text"
              }
            >
              <CitationText>{block.text}</CitationText>
            </p>
            {deep && block.citation_ids && block.citation_ids.length > 0 && (
              <div className="brief-block-citations">
                {block.citation_ids.map((id) => (
                  <CitationLink key={id} id={id} />
                ))}
                {/* Support for this sentence, in place: following a citation
                    should not cost the reader the paragraph they are in. */}
                <Why subject="this claim" citations={block.citation_ids} />
              </div>
            )}
          </div>
        ))}

      <MarginNotes objections={objections} />
    </article>
  );
}
