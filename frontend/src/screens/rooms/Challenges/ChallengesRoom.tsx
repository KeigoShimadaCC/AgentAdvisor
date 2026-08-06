import { RoomShell } from "../../shared/RoomShell";
import { HonestEmpty } from "../../shared/HonestEmpty";
import { CitationLink } from "../../inspector/CitationLink";
import type { CaseView, ObjectionView } from "../../../generated/case_view";
import { voiceFor, roleVoice } from "../../../copy/voices";
import {
  objectionStatusLabel,
  levelLabel,
  targetSectionLabel,
  OBJECTION_STATUS_SORT,
  ROOMS,
} from "../../../copy/terms";

export function ChallengesRoom() {
  return (
    <RoomShell room="challenges">
      {(view) => <ChallengesBody view={view} />}
    </RoomShell>
  );
}

function ChallengesBody({ view }: { view: CaseView }) {
  const room = view.rooms?.challenges;
  const objections = room?.objections ?? [];
  const premortem = room?.premortem ?? null;
  const trackDivergence = room?.track_divergence ?? null;

  if (!room || (objections.length === 0 && !premortem && !trackDivergence)) {
    return (
      <HonestEmpty
        truth="not_yet"
        heading={`${ROOMS.challenges.label}: not yet — the challenge pass has not run for this case.`}
      />
    );
  }

  // Status-first sorting: open on top, never hidden. Mirrors the orchestrator
  // rule but reapplied here so the room is robust to re-sorts.
  const sortedObjections = [...objections].sort(
    (a, b) =>
      (OBJECTION_STATUS_SORT[a.resolution_status] ?? 99) -
      (OBJECTION_STATUS_SORT[b.resolution_status] ?? 99),
  );

  return (
    <div className="challenges-room">
      {/* Objections */}
      {objections.length > 0 && (
        <section className="objections-section" aria-label="Objections">
          <h3>Objections</h3>
          <ul className="objection-list">
            {sortedObjections.map((o) => (
              <ObjectionRow key={o.objection_id} objection={o} />
            ))}
          </ul>
        </section>
      )}

      {/* Pre-mortem */}
      {premortem && (
        <section className="premortem-section" aria-label="Pre-mortem">
          <h3>Pre-mortem</h3>
          <p className="premortem-intro">
            Assume the decision was made and it went wrong. Here is what most likely happened.
          </p>
          <p className="premortem-assumed">
            <span className="premortem-label">Assumed outcome: </span>
            {premortem.assumed_outcome}
          </p>
          <p className="premortem-horizon">
            <span className="premortem-label">Horizon: </span>
            {premortem.horizon}
          </p>
          <p className="premortem-most-likely">
            <span className="premortem-label">Most likely failure: </span>
            {premortem.most_likely_failure_mode}
          </p>
          {premortem.failure_modes && premortem.failure_modes.length > 0 && (
            <ul className="premortem-modes">
              {premortem.failure_modes.map((mode, i) => {
                const fm = String(mode["failure_mode"] ?? "—");
                const severity = String(mode["severity"] ?? "—");
                const prob = mode["probability_point"];
                const indicators = Array.isArray(mode["leading_indicators"])
                  ? (mode["leading_indicators"] as string[])
                  : [];
                return (
                  <li key={i} className="premortem-mode">
                    <div className="premortem-mode-head">
                      <span className="premortem-mode-name">{fm}</span>
                      <span className="premortem-mode-chips">
                        {prob != null && (
                          <span className="chip chip-probability">
                            {probabilityChipText(Number(prob))}
                          </span>
                        )}
                        <span className="chip chip-severity">{levelLabel(severity)} severity</span>
                      </span>
                    </div>
                    {indicators.length > 0 && (
                      <p className="premortem-indicators">
                        <span className="premortem-label">Leading indicators: </span>
                        {indicators.join(", ")}
                      </p>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}

      {/* Second opinion / dual track.
          SPEC-049: the divergence itself is promoted to the case surface, above
          the answer, because a split between the two Directors changes how the
          recommendation should be read and this room is one most users never
          open. What stays here is the detail — the per-track positions and the
          reconciliation — which is what a room is for. */}
      <section className="second-opinion-section" aria-label="Second opinion">
        <h3>Second opinion</h3>
        {trackDivergence ? (
          <>
            {trackDivergence.agreement ? (
              <p className="second-opinion-agreement">
                <span className="agreement-badge agreement-badge-yes">Agree</span>
                Both reasoning tracks reached the same conclusion.
              </p>
            ) : (
              <p className="second-opinion-divergence">
                <span className="agreement-badge agreement-badge-no">Disagree</span>
                {trackDivergence.divergence_summary}
              </p>
            )}
            {trackDivergence.positions && trackDivergence.positions.length > 0 && (
              <div className="second-opinion-positions">
                {trackDivergence.positions.map((pos, i) => {
                  const trackId = String(pos["track_id"] ?? `Track ${i + 1}`);
                  const who = voiceFor(trackId);
                  const alt = String(pos["preferred_alternative"] ?? "—");
                  const reason = String(pos["top_reason"] ?? "—");
                  const conf = pos["recommendation_confidence"];
                  return (
                    <div key={i} className="position-card">
                      <h4>{who}</h4>
                      <p className="position-alternative">{alt}</p>
                      <p className="position-reason">{reason}</p>
                      {conf != null && (
                        <p className="position-confidence">
                          Confidence: {Math.round(Number(conf) * 100)}%
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </>
        ) : (
          <p className="second-opinion-absent">
            A second reasoning track was not run for this case — the recommendation
            reflects a single line of analysis.
          </p>
        )}
        <p className="never-averaged-footer">
          The two tracks were never averaged into a single number. Where they disagree,
          both positions stand on their own.
        </p>
      </section>
    </div>
  );
}

function ObjectionRow({ objection }: { objection: ObjectionView }) {
  return (
    <li className={`objection-row objection-status-${objection.resolution_status}`}>
      <div className="objection-row-head">
        <span className="objection-voice" title={roleVoice("challenger").blurb}>
          {roleVoice("challenger").label}
        </span>
        <span className={`objection-status-pill objection-status-pill-${objection.resolution_status}`}>
          {objectionStatusLabel(objection.resolution_status)}
        </span>
        <CitationLink id={objection.objection_id} />
        <span className="objection-target">
          Targets: <CitationLink id={objection.target_section}>{targetSectionLabel(objection.target_section)}</CitationLink>
        </span>
        <span className="objection-materiality">{levelLabel(objection.materiality)} materiality</span>
      </div>
      <p className="objection-claim">{objection.claim}</p>
      <p className="objection-reasoning">{objection.reasoning}</p>
    </li>
  );
}

function probabilityChipText(point: number): string {
  if (point >= 0.7) return "Likely";
  if (point >= 0.4) return "Possible";
  return "Unlikely";
}
