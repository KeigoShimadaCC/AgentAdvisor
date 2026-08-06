import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useCaseView } from "../shared/useCaseView";
import { Narrator } from "../../narration/Narrator";
import { CaseMap, countersFromView } from "../shared/CaseMap";
import { Dissent, independentReviewFrom } from "../Brief/Dissent";
import { Skeleton } from "../shared/Skeleton";
import { markOnboarded } from "./onboarding";
import type { CaseSummary } from "../../api/client";

/**
 * The tour is a real case, replayed (SPEC-052).
 *
 * A scripted demo would be a second description of how the product behaves, and
 * it would drift — silently, and fastest exactly when the pipeline changes,
 * which is when an accurate demo matters most. A recorded case *is* the product
 * behaving, and it stays true on its own.
 *
 * So this screen does not simulate anything. It opens a committed fixture case
 * through the same `useCaseView` every other screen uses, and points at what is
 * happening: the narrator, the map with its loops, and the dissent.
 */
export function Onboarding() {
  const navigate = useNavigate();
  const [caseId, setCaseId] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    // Whatever case the service is serving — in replay mode that is the
    // recorded one, and in fixture mode the completed fixture. Both show a
    // full deliberation.
    api
      .listCases()
      .then((cases: CaseSummary[]) => {
        const complete = cases.find((c) => c.stage === "done") ?? cases[0];
        if (complete) setCaseId(complete.case_id);
        else setUnavailable(true);
      })
      .catch(() => setUnavailable(true));
  }, []);

  function finish() {
    markOnboarded();
    navigate("/new");
  }

  if (unavailable) {
    return (
      <div className="onboarding">
        <h2>Nothing to show you yet</h2>
        <p>
          The tour replays a real recorded case, and there is not one here. Start a decision instead
          — the same narration runs live.
        </p>
        <button type="button" className="primary-action" onClick={finish}>
          Start a decision
        </button>
      </div>
    );
  }

  if (!caseId) return <Skeleton shape="brief" label="Loading the tour" />;

  return <Tour caseId={caseId} onFinish={finish} />;
}

function Tour({ caseId, onFinish }: { caseId: string; onFinish: () => void }) {
  const { view, events, narration, loading } = useCaseView(caseId);

  if (loading || !view) return <Skeleton shape="brief" label="Loading the tour" />;

  const divergence = view.rooms?.challenges?.track_divergence;
  const objections = view.rooms?.challenges?.objections ?? [];
  const revisions = view.history?.thesis_revisions ?? [];

  return (
    <div className="onboarding">
      <header className="onboarding-head">
        <h2>This is what a case looks like</h2>
        <button type="button" className="onboarding-skip" onClick={onFinish}>
          Skip
        </button>
      </header>

      <section className="onboarding-step">
        <h3>It tells you what it is doing</h3>
        <p className="screen-help">
          A case runs for a long time. It says where it is the whole way through, including when it
          goes back and redoes something.
        </p>
        <Narrator narration={narration} events={events} showTranscript={false} />
      </section>

      <section className="onboarding-step">
        <h3>It does not run in a straight line</h3>
        <p className="screen-help">
          The work loops: a challenge round can send research back, a failed review can rewrite the
          synthesis. Those loops are on the map, so a second round never looks like a stall.
        </p>
        <CaseMap view={view} counters={countersFromView(view)} />
      </section>

      {(divergence || objections.length > 0 || revisions.length > 0) && (
        <section className="onboarding-step">
          <h3>It argues with itself, on the record</h3>
          <p className="screen-help">
            Two Directors run on different model families, a Challenger argues against the emerging
            answer, and an independent reviewer can block delivery outright. Where they disagree,
            both positions stand — nothing is averaged.
          </p>
          {divergence && (
            <Dissent divergence={divergence} independentReview={independentReviewFrom(view)} />
          )}
          {objections.length > 0 && (
            <p className="onboarding-count">
              {objections.length} objection{objections.length === 1 ? "" : "s"} were raised against
              this recommendation and are recorded with it.
            </p>
          )}
          {revisions.length > 0 && (
            <p className="onboarding-count">
              The working view was revised {revisions.length} time
              {revisions.length === 1 ? "" : "s"} as evidence arrived.
            </p>
          )}
        </section>
      )}

      <section className="onboarding-step">
        <h3>Then you decide</h3>
        <p className="screen-help">
          Nothing is signed without you. You review the scope before it starts, and the
          recommendation before it is final.
        </p>
        <div className="onboarding-actions">
          <button type="button" className="primary-action" onClick={onFinish}>
            Start my own decision
          </button>
          <Link to={`/cases/${caseId}`} className="secondary-action" onClick={markOnboarded}>
            Read this case in full
          </Link>
        </div>
      </section>
    </div>
  );
}
