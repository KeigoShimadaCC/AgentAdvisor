import { CitationLink } from "../../inspector/CitationLink";
import type { OptionsRoom } from "../../../generated/case_view";

/**
 * Competing hypotheses, ranked by what the evidence fails to rule out (SPEC-053
 * rendering phase 8's SPEC-040).
 *
 * The technique's point is inverted from how people usually read evidence: an
 * alternative is strong not because much supports it but because little
 * *disconfirms* it, which is what stops the case from simply accumulating
 * agreement with whatever it thought first. Phase 8 computed the whole thing —
 * disconfirmation rank, weight, which evidence did the ruling out, and which
 * evidence turned out to be uninformative — and projected it. Nothing drew it,
 * so it was reachable only by reading `shared/ach_matrix.yaml`.
 *
 * Rank 1 is therefore the alternative the evidence has *least* successfully
 * argued against, and the column says so, because "rank 1" with no gloss reads
 * as "best" and would invert the meaning.
 */
export function DiagnosticityMatrix({ room }: { room: OptionsRoom }) {
  // Only options the matrix actually scored. An `ach_scored` case whose options
  // carry no rank would otherwise draw an empty table, which reads as "the
  // technique found nothing" rather than "the technique did not run here".
  const ranked = [...(room.options ?? [])]
    .filter((o) => o.disconfirmation_rank != null)
    .sort((a, b) => a.disconfirmation_rank! - b.disconfirmation_rank!);
  if (!room.ach_scored || ranked.length === 0) return null;

  const uninformative = room.ach_uninformative_evidence_ids ?? [];

  return (
    <section className="ach-matrix" aria-label="Competing hypotheses">
      <h3>What the evidence could not rule out</h3>
      <p className="section-help">
        A second reading of the same options: ranked by weight of <em>disconfirming</em> evidence,
        not by support. Rank 1 is the alternative the evidence argued against least successfully.
      </p>

      <div className="ach-scroll">
        <table className="ach-table">
          <thead>
            <tr>
              <th scope="col">Rank</th>
              <th scope="col">Alternative</th>
              <th scope="col">Disconfirming weight</th>
              <th scope="col">Ruled against by</th>
            </tr>
          </thead>
          <tbody>
            {ranked.map((option) => (
              <tr
                key={option.alternative}
                className={option.eliminated ? "ach-row-eliminated" : undefined}
              >
                <td className="ach-rank">{option.disconfirmation_rank ?? "—"}</td>
                <td>
                  {option.alternative}
                  {option.eliminated && (
                    <span className="ach-eliminated-mark"> — ruled out</span>
                  )}
                </td>
                <td className="ach-weight">
                  {option.disconfirming_weight != null
                    ? option.disconfirming_weight.toFixed(2)
                    : "—"}
                </td>
                <td>
                  {(option.disconfirming_evidence_ids ?? []).length === 0 ? (
                    <span className="ach-none">nothing yet</span>
                  ) : (
                    (option.disconfirming_evidence_ids ?? []).map((id, i) => (
                      <span key={id}>
                        {i > 0 && ", "}
                        <CitationLink id={id} />
                      </span>
                    ))
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Naming the evidence that could not have changed the ranking is one of
          the more useful outputs of the technique, and it is the one a reader
          would never derive themselves. */}
      <div className="ach-uninformative">
        <p className="ach-uninformative-label">Evidence that changed nothing</p>
        {uninformative.length === 0 ? (
          <p className="screen-help">
            Every piece of evidence discriminated between at least two alternatives.
          </p>
        ) : (
          <>
            <p className="screen-help">
              {uninformative.length} record{uninformative.length === 1 ? "" : "s"} scored identically
              against every alternative, so they could not have moved the ranking either way.
            </p>
            <p className="ach-uninformative-ids">
              {uninformative.map((id, i) => (
                <span key={id}>
                  {i > 0 && ", "}
                  <CitationLink id={id} />
                </span>
              ))}
            </p>
          </>
        )}
      </div>
    </section>
  );
}
