import { useEffect, useState } from "react";
import {
  readReactions,
  toggleReaction,
  hasReaction,
  REACTION_LABELS,
  type Reaction,
  type ReactionKind,
} from "./reactions";

interface ReactionControlsProps {
  caseId: string;
  targetId: string;
  targetKind: Reaction["targetKind"];
  label: string;
  /** Which marks make sense here. An objection cannot "look wrong" to a reader
   *  in the same way an assumption can — it is already a challenge. */
  kinds?: ReactionKind[];
}

/**
 * Mark a record as you read it (SPEC-051).
 *
 * Nothing is written to the case. These accumulate in `localStorage` and are
 * spent once, at the delivery gate, as the pre-filled revision note.
 */
export function ReactionControls({
  caseId,
  targetId,
  targetKind,
  label,
  kinds = ["looks_wrong", "matters"],
}: ReactionControlsProps) {
  const [reactions, setReactions] = useState<Reaction[]>(() => readReactions(caseId));

  // SPEC-055: two tabs on one case must not disagree about what was marked.
  // Altitude already reconciled this way; reactions did not, so a mark made in
  // one tab was invisible in the other until a reload — and the delivery gate
  // would then pre-fill from whichever tab happened to be used.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === `agentadvisor:reactions:${caseId}`) setReactions(readReactions(caseId));
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [caseId]);

  return (
    <div className="reaction-controls" role="group" aria-label={`Mark ${targetId}`}>
      {kinds.map((kind) => {
        const on = hasReaction(reactions, targetId, kind);
        return (
          <button
            key={kind}
            type="button"
            className={`reaction-chip${on ? " selected" : ""}`}
            aria-pressed={on}
            onClick={() =>
              setReactions(toggleReaction(caseId, { targetId, targetKind, kind, label }))
            }
          >
            {REACTION_LABELS[kind]}
          </button>
        );
      })}
    </div>
  );
}
