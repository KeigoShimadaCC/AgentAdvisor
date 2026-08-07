import { voiceFor, roleVoice } from "../../copy/voices";
import type {
  CaseView,
  TrackDivergenceView,
  IndependentReviewView as ProjectedIndependentReview,
} from "../../generated/case_view";

/**
 * The reviewer that can block delivery (phase 8 SPEC-039, projected by SPEC-053).
 *
 * SPEC-049 shipped this component against a shape the projection did not yet
 * carry, with `independentReviewFrom` as the single adapter that would change
 * when it landed. It has landed: `IntegrityView.independent_review` is a real
 * field now, so this reads it directly and the cast is gone.
 */
export type IndependentReviewView = ProjectedIndependentReview;

export function independentReviewFrom(view: CaseView): IndependentReviewView | null {
  return view.integrity?.independent_review ?? null;
}

/** Whether a dissent is standing that must stop a signature. */
export function isBlockingDissent(review: IndependentReviewView | null): boolean {
  return review?.verdict === "dissent";
}

interface DissentProps {
  divergence?: TrackDivergenceView | null;
  independentReview?: IndependentReviewView | null;
}

/**
 * Disagreement, promoted to the answer (SPEC-049).
 *
 * Three voices can disagree about a case, and until now all three were reported
 * in the same flat way — or not at all. The two Directors run on different model
 * families precisely so that their agreement carries information; that made
 * their *disagreement* a card in a room most users never open. The independent
 * reviewer's dissent is stronger still: it blocks delivery. A blocked signature
 * and a caveat should not look alike.
 *
 * The invariant this component exists to hold: **never averaged**. Two
 * disagreeing tracks render as two standing positions with their own
 * alternatives. No midpoint, no blended confidence, no merged third position —
 * a synthesised number here would destroy the exact property the dual-track
 * design was built to produce.
 */
export function Dissent({ divergence, independentReview }: DissentProps) {
  const blocking = isBlockingDissent(independentReview ?? null);
  const split = divergence != null && divergence.agreement === false;

  if (!blocking && !split) return null;

  return (
    <section className="dissent" aria-label="Disagreement about this recommendation">
      {blocking && independentReview && (
        <BlockingDissent review={independentReview} />
      )}
      {split && divergence && <DirectorSplit divergence={divergence} />}
    </section>
  );
}

function BlockingDissent({ review }: { review: IndependentReviewView }) {
  const voice = roleVoice("independent_reviewer");
  return (
    <div className="dissent-blocking" role="alert">
      <p className="dissent-blocking-verdict">
        <span className="dissent-blocking-stamp">Signature blocked</span>
        {voice.label} does not agree with this conclusion.
      </p>
      <p className="dissent-voice-blurb">{voice.blurb}</p>
      <p className="dissent-blocking-reasoning">{review.reasoning}</p>
      {/* A dissent that cannot name an alternative is a reservation, not a
          dissent — the artifact enforces this, so it is always here to show. */}
      {review.divergent_conclusion && (
        <p className="dissent-blocking-alternative">
          <span className="dissent-label">Would instead recommend</span>
          {review.divergent_conclusion}
        </p>
      )}
      {review.unsupported_claims && review.unsupported_claims.length > 0 && (
        <div className="dissent-unsupported">
          <p className="dissent-label">Claims the evidence does not carry</p>
          <ul>
            {review.unsupported_claims.map((claim, i) => (
              <li key={i}>{claim}</li>
            ))}
          </ul>
        </div>
      )}
      <p className="dissent-consequence">
        This cannot be signed off while the dissent stands.
      </p>
    </div>
  );
}

function DirectorSplit({ divergence }: { divergence: TrackDivergenceView }) {
  const positions = divergence.positions ?? [];
  return (
    <div className="dissent-split">
      <p className="dissent-split-headline">
        <span className="dissent-split-stamp">The two Directors disagree</span>
        {divergence.divergence_summary}
      </p>
      <p className="dissent-voice-blurb">{roleVoice("director_b").blurb}</p>

      <div className="dissent-positions">
        {positions.map((pos, i) => {
          const trackId = String(pos["track_id"] ?? `Track ${i + 1}`);
          const alternative = String(pos["preferred_alternative"] ?? "—");
          const reason = String(pos["top_reason"] ?? "");
          const confidence = pos["recommendation_confidence"];
          return (
            <div key={i} className="dissent-position">
              <p className="dissent-position-who">{voiceFor(trackId) || trackId}</p>
              <p className="dissent-position-alternative">{alternative}</p>
              {reason && <p className="dissent-position-reason">{reason}</p>}
              {confidence != null && (
                <p className="dissent-position-confidence">
                  {Math.round(Number(confidence) * 100)}% confident in its own position
                </p>
              )}
            </div>
          );
        })}
      </div>

      <p className="dissent-never-averaged">
        These positions were not averaged. Where the tracks disagree, both stand.
      </p>
    </div>
  );
}
