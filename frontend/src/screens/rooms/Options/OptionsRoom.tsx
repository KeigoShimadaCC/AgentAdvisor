import { useMemo } from "react";
import { RoomShell } from "../../shared/RoomShell";
import { EVBar } from "../../shared/EVBar";
import { HonestEmpty } from "../../shared/HonestEmpty";
import { CitationLink } from "../../inspector/CitationLink";
import type { CaseView, OptionView } from "../../../generated/case_view";
import { ROOMS } from "../../../copy/terms";

export function OptionsRoom() {
  return (
    <RoomShell room="options">
      {(view) => <OptionsBody view={view} />}
    </RoomShell>
  );
}

function OptionsBody({ view }: { view: CaseView }) {
  const room = view.rooms?.options;
  const options = room?.options ?? [];

  // Every hook runs before the empty-state return: a live case goes from zero
  // options to ranked ones mid-run, and a conditional hook would change the hook
  // count between those two renders.
  const eliminated = useMemo(() => options.filter((o) => o.eliminated), [options]);
  const ranked = useMemo(() => options.filter((o) => !o.eliminated), [options]);
  const grouped = useMemo(() => groupByRank(ranked), [ranked]);
  // SPEC-040: the competing-hypotheses standings, joined onto the same options
  // by the projection. Present only when a matrix was built for the case.
  const achStandings = useMemo(
    () =>
      options
        .filter((o) => o.disconfirmation_rank != null)
        .sort((a, b) => a.disconfirmation_rank! - b.disconfirmation_rank!),
    [options],
  );

  if (!room || options.length === 0) {
    return (
      <HonestEmpty
        truth="not_yet"
        heading={`${ROOMS.options.label}: not yet — alternatives have not been ranked for this case.`}
      />
    );
  }

  const evValues = ranked.map((o) => o.expected_value).filter((v): v is number => v != null);
  const evMin = evValues.length ? Math.min(...evValues, 0) : 0;
  const evMax = evValues.length ? Math.max(...evValues, 0) : 1;
  const hasEV = evValues.length > 0;

  const minRank = ranked.length ? Math.min(...ranked.map((o) => o.rank)) : null;
  const recommended = ranked.find((o) => o.rank === minRank);

  return (
    <div className="options-room">
      <ol className="option-ranked-list" aria-label="Ranked options">
        {grouped.map((group) => (
          <li key={group.rank} className={`option-rank-group${group.rank === minRank ? " option-rank-recommended" : ""}`}>
            <div className="option-rank-label">
              Rank {group.rank}
              {group.rank === minRank && (
                <span className="option-recommended-anchor">Recommended</span>
              )}
              {group.options.length > 1 && (
                <span className="option-equal-rank">Equal rank</span>
              )}
            </div>
            <ul className="option-rows">
              {group.options.map((o) => (
                <OptionRow
                  key={o.alternative}
                  option={o}
                  hasEV={hasEV}
                  evMin={evMin}
                  evMax={evMax}
                  recommended={o === recommended}
                  leastDisconfirmed={
                    room.ach_scored === true && o.disconfirmation_rank === 1
                  }
                />
              ))}
            </ul>
          </li>
        ))}
      </ol>

      {room.ach_scored && achStandings.length > 0 && (
        <section className="ach-exhibit" aria-label="Competing hypotheses">
          <h3>Competing hypotheses</h3>
          <p className="ach-explainer">
            A second reading of the same options: ranked by weight of disconfirming
            evidence, least disconfirmed first. Evidence consistent with every option
            carries no weight.
          </p>
          <table className="ach-table">
            <thead>
              <tr>
                <th scope="col">Rank</th>
                <th scope="col">Option</th>
                <th scope="col">Disconfirming weight</th>
                <th scope="col">Records against</th>
              </tr>
            </thead>
            <tbody>
              {achStandings.map((o) => (
                <tr key={o.alternative}>
                  <td>{o.disconfirmation_rank}</td>
                  <td>{o.alternative}</td>
                  <td>{o.disconfirming_weight?.toFixed(2)}</td>
                  <td>
                    {o.disconfirming_evidence_ids && o.disconfirming_evidence_ids.length > 0
                      ? o.disconfirming_evidence_ids.map((id, i) => (
                          <span key={id}>
                            {i > 0 && ", "}
                            <CitationLink id={id} />
                          </span>
                        ))
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {room.ach_uninformative_evidence_ids &&
            room.ach_uninformative_evidence_ids.length > 0 && (
              <p className="ach-uninformative">
                {room.ach_uninformative_evidence_ids.length} record(s) scored the same
                against every option and could not have changed this reading:{" "}
                {room.ach_uninformative_evidence_ids.map((id, i) => (
                  <span key={id}>
                    {i > 0 && ", "}
                    <CitationLink id={id} />
                  </span>
                ))}
                .
              </p>
            )}
        </section>
      )}

      {eliminated.length > 0 && (
        <section className="eliminated-coda" aria-label="Eliminated options">
          <h3>Eliminated options</h3>
          <ul>
            {eliminated.map((o) => (
              <li key={o.alternative}>
                <strong>{o.alternative}</strong> — {o.rationale}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

interface RankGroup {
  rank: number;
  options: OptionView[];
}

function groupByRank(options: OptionView[]): RankGroup[] {
  const map = new Map<number, OptionView[]>();
  for (const o of options) {
    const list = map.get(o.rank) ?? [];
    list.push(o);
    map.set(o.rank, list);
  }
  return [...map.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([rank, opts]) => ({ rank, options: opts }));
}

interface OptionRowProps {
  option: OptionView;
  hasEV: boolean;
  evMin: number;
  evMax: number;
  recommended: boolean;
  leastDisconfirmed: boolean;
}

function OptionRow({ option, hasEV, evMin, evMax, recommended, leastDisconfirmed }: OptionRowProps) {
  return (
    <li className={`option-row${recommended ? " option-row-recommended" : ""}`}>
      <div className="option-row-head">
        <span className="option-alternative">{option.alternative}</span>
        {option.expected_value != null && (
          <span className="option-modeled-badge" title="Modeled with a reproducible script">
            modeled
          </span>
        )}
        {leastDisconfirmed && (
          <span
            className="option-ach-badge"
            title="The competing-hypotheses matrix rules this option out the least"
          >
            least disconfirmed
          </span>
        )}
      </div>
      <p className="option-rationale">{option.rationale}</p>
      {hasEV && (
        <div className="option-ev">
          <EVBar
            value={option.expected_value}
            min={evMin}
            max={evMax}
            label={option.alternative}
          />
        </div>
      )}
    </li>
  );
}
