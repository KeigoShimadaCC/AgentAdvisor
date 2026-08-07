import { useMemo } from "react";
import { RoomShell } from "../../shared/RoomShell";
import { EVBar } from "../../shared/EVBar";
import { HonestEmpty } from "../../shared/HonestEmpty";
import type { CaseView, OptionView } from "../../../generated/case_view";
import { ROOMS } from "../../../copy/terms";
import { DiagnosticityMatrix } from "./DiagnosticityMatrix";

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
                />
              ))}
            </ul>
          </li>
        ))}
      </ol>

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

      {/* SPEC-053: phase 8 computed this and projected it, and nothing drew it. */}
      {room && <DiagnosticityMatrix room={room} />}
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
}

function OptionRow({ option, hasEV, evMin, evMax, recommended }: OptionRowProps) {
  return (
    <li className={`option-row${recommended ? " option-row-recommended" : ""}`}>
      <div className="option-row-head">
        <span className="option-alternative">{option.alternative}</span>
        {option.expected_value != null && (
          <span className="option-modeled-badge" title="Modeled with a reproducible script">
            modeled
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
