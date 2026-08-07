import { CitationLink } from "../inspector/CitationLink";
import { objectionStatusLabel, levelLabel } from "../../copy/terms";
import { roleVoice } from "../../copy/voices";
import type { ObjectionView } from "../../generated/case_view";

/** The section a `target_section` path points at: `key_reasons[0]` → `key_reasons`. */
export function targetSectionKey(path: string | null | undefined): string {
  if (!path) return "";
  return path.split(/[.[]/)[0];
}

/**
 * Split objections into the ones that can be placed beside a passage and the
 * ones that cannot.
 *
 * An objection whose target section is missing or names a section this brief
 * does not have is still an objection — dropping it would be the worst possible
 * handling of "the Challenger disagreed and we could not find where to put it".
 * Those render at the end of the brief instead.
 */
export function placeObjections(
  objections: ObjectionView[],
  sectionKeys: string[],
): { bySection: Map<string, ObjectionView[]>; unplaced: ObjectionView[] } {
  const known = new Set(sectionKeys);
  const bySection = new Map<string, ObjectionView[]>();
  const unplaced: ObjectionView[] = [];

  for (const objection of objections) {
    const key = targetSectionKey(objection.target_section);
    if (key && known.has(key)) {
      const list = bySection.get(key) ?? [];
      list.push(objection);
      bySection.set(key, list);
    } else {
      unplaced.push(objection);
    }
  }
  return { bySection, unplaced };
}

interface MarginNotesProps {
  objections: ObjectionView[];
  /** Set when these are the objections nothing could be matched to. */
  unplaced?: boolean;
}

/**
 * Objections rendered against the passage they attack (SPEC-049).
 *
 * `ObjectionView.target_section` has always carried the association; nothing
 * here computes it. What changes is that the objection now appears *next to
 * what it objects to* rather than in a room, so reading the recommendation and
 * reading the argument against it are the same act. An open, high-materiality
 * objection is visually distinct from a settled one, because the difference is
 * the whole point: one of them is a live problem with the recommendation.
 */
export function MarginNotes({ objections, unplaced = false }: MarginNotesProps) {
  if (objections.length === 0) return null;

  const voice = roleVoice("challenger");

  return (
    <aside
      className={`margin-notes${unplaced ? " margin-notes-unplaced" : ""}`}
      aria-label={unplaced ? "Objections without a target section" : "Objections to this passage"}
    >
      {unplaced && (
        <p className="margin-notes-orphan-note">
          These objections name a part of the brief that is not in it. They are shown here rather
          than dropped.
        </p>
      )}
      {objections.map((objection) => {
        const open = objection.resolution_status === "open";
        const high = objection.materiality === "high";
        return (
          <div
            key={objection.objection_id}
            className={`margin-note margin-note-${objection.resolution_status}${
              open && high ? " margin-note-live" : ""
            }`}
            data-materiality={objection.materiality}
          >
            <p className="margin-note-who" title={voice.blurb}>
              {voice.label}
              <span className="margin-note-status">
                {objectionStatusLabel(objection.resolution_status)}
              </span>
              <span className="margin-note-materiality">
                {levelLabel(objection.materiality)} materiality
              </span>
            </p>
            <p className="margin-note-claim">{objection.claim}</p>
            <p className="margin-note-reasoning">{objection.reasoning}</p>
            <p className="margin-note-record">
              <CitationLink id={objection.objection_id} />
            </p>
          </div>
        );
      })}
    </aside>
  );
}
