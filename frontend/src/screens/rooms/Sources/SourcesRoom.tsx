import { useMemo, useState } from "react";
import { RoomShell } from "../../shared/RoomShell";
import { GradeChip } from "../../shared/GradeChip";
import { HonestEmpty } from "../../shared/HonestEmpty";
import { CitationLink } from "../../inspector/CitationLink";
import type { CaseView, SourceView } from "../../../generated/case_view";
import {
  authorityWords,
  sourceTypeLabel,
  sourceTierLabel,
  evidenceFlagLabel,
  levelLabel,
  ROOMS,
  SOURCES_COPY,
} from "../../../copy/terms";

/** Filters a user can apply to the source corpus. */
type FilterKey = "all" | "high" | "medium" | "low" | "flagged";

const FILTER_LABELS: Record<FilterKey, string> = {
  all: "All sources",
  high: "High reliability",
  medium: "Medium reliability",
  low: "Low reliability",
  flagged: "Flagged",
};

export function SourcesRoom() {
  return (
    <RoomShell room="sources">
      {(view) => <SourcesBody view={view} />}
    </RoomShell>
  );
}

function SourcesBody({ view }: { view: CaseView }) {
  const room = view.rooms?.sources;
  const [filter, setFilter] = useState<FilterKey>("all");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const sources = room?.sources ?? [];
  const corpusMean = room?.corpus_authority_mean ?? null;
  const maxCluster = room?.max_cluster_share ?? null;
  const originCount = room?.independent_group_count ?? null;

  const filtered = useMemo(() => {
    if (filter === "all") return sources;
    if (filter === "flagged") return sources.filter((s) => (s.flags?.length ?? 0) > 0);
    return sources.filter((s) => s.reliability === filter);
  }, [sources, filter]);

  // Cluster view: group by independence_group, sorted by share desc.
  const clusters = useMemo(() => {
    const map = new Map<string, { group: string; share: number | null; count: number }>();
    for (const s of sources) {
      const entry = map.get(s.independence_group) ?? {
        group: s.independence_group,
        share: s.cluster_share ?? null,
        count: 0,
      };
      entry.count += 1;
      if (s.cluster_share != null) entry.share = s.cluster_share;
      map.set(s.independence_group, entry);
    }
    return [...map.values()].sort((a, b) => (b.share ?? 0) - (a.share ?? 0));
  }, [sources]);

  // Weakest-evidence callout: lowest authority score.
  const weakest = useMemo(() => {
    return sources
      .filter((s) => s.authority_score != null)
      .sort((a, b) => (a.authority_score ?? 1) - (b.authority_score ?? 1))[0];
  }, [sources]);

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (!room || sources.length === 0) {
    return (
      <HonestEmpty
        truth="not_yet"
        heading={`${ROOMS.sources.label}: not yet — evidence has not been gathered for this case.`}
      />
    );
  }

  const concentrationWarning =
    maxCluster != null && maxCluster > 0.4;

  return (
    <div className="sources-room">
      {/* Corpus header */}
      <section className="corpus-header">
        <div className="corpus-authority">
          <span className="corpus-authority-label">Authority</span>
          <span className="corpus-authority-words">{authorityWords(corpusMean)}</span>
          {corpusMean != null && (
            <span className="corpus-authority-score">{Math.round(corpusMean * 100)}/100</span>
          )}
        </div>
        <div className="corpus-mix">
          <span className="corpus-mix-label">Source mix</span>
          <SourceMixBar sources={sources} />
        </div>
        <div className="corpus-origins">
          <span className="corpus-origins-label">Independent origins</span>
          <span className="corpus-origins-count">{originCount ?? "—"}</span>
          {concentrationWarning && (
            <p className="corpus-concentration-warning">
              One origin accounts for {Math.round((maxCluster ?? 0) * 100)}% of the corpus —
              treat conclusions that lean on it with extra caution.
            </p>
          )}
        </div>
      </section>

      {/* Weakest-evidence callout */}
      {weakest && (
        <section className="weakest-callout" aria-label="Weakest evidence">
          <h3>Weakest evidence</h3>
          <p>
            <CitationLink id={weakest.evidence_id}>{weakest.evidence_id}</CitationLink>
            {" — "}
            {weakest.claim}
          </p>
          <GradeChip
            sourceTier={weakest.source_tier}
            reliability={weakest.reliability}
            directness={weakest.directness}
          />
        </section>
      )}

      {/* Cluster view */}
      {clusters.length > 1 && (
        <section className="cluster-view" aria-label="Source clusters">
          <h3>Clusters by origin</h3>
          <ul className="cluster-list">
            {clusters.map((c) => (
              <li key={c.group} className="cluster-bubble">
                <span className="cluster-group">{c.group}</span>
                <span className="cluster-share">
                  {c.share != null ? `${Math.round(c.share * 100)}%` : "—"}
                </span>
                <span className="cluster-count">{c.count} record{c.count === 1 ? "" : "s"}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Filters */}
      <section className="source-filters" aria-label="Filter sources">
        {(Object.keys(FILTER_LABELS) as FilterKey[]).map((key) => (
          <button
            key={key}
            type="button"
            className={`filter-chip${filter === key ? " filter-chip-active" : ""}`}
            aria-pressed={filter === key}
            onClick={() => setFilter(key)}
          >
            {FILTER_LABELS[key]}
          </button>
        ))}
      </section>

      {/* Source cards */}
      <ul className="source-cards">
        {filtered.map((s) => (
          <SourceCard
            key={s.evidence_id}
            source={s}
            expanded={expanded.has(s.evidence_id)}
            onToggle={() => toggle(s.evidence_id)}
          />
        ))}
        {filtered.length === 0 && (
          <li><HonestEmpty truth="nothing_found" heading="No sources match this filter." /></li>
        )}
      </ul>
    </div>
  );
}

function SourceMixBar({ sources }: { sources: SourceView[] }) {
  const byTier = new Map<string, number>();
  for (const s of sources) {
    const tier = s.source_tier ?? "ungraded";
    byTier.set(tier, (byTier.get(tier) ?? 0) + 1);
  }
  const total = sources.length || 1;
  const order = ["primary", "official", "reputable", "weak", "ungraded"];
  const summary = order
    .filter((tier) => byTier.get(tier))
    .map((tier) => `${sourceTierLabel(tier)}: ${byTier.get(tier)}`)
    .join(", ");
  return (
    <div className="source-mix-bar" role="img" aria-label={`Source mix by tier — ${summary}`}>
      {order.map((tier) => {
        const count = byTier.get(tier);
        if (!count) return null;
        const pct = (count / total) * 100;
        return (
          <div
            key={tier}
            className={`source-mix-seg source-mix-${tier}`}
            style={{ width: `${pct}%` }}
            title={`${sourceTierLabel(tier)}: ${count}`}
          />
        );
      })}
    </div>
  );
}

interface SourceCardProps {
  source: SourceView;
  expanded: boolean;
  onToggle: () => void;
}

function SourceCard({ source, expanded, onToggle }: SourceCardProps) {
  const isExpanded = expanded;
  return (
    <li className={`source-card${isExpanded ? " source-card-expanded" : ""}`}>
      <div className="source-card-head">
        <button
          type="button"
          className="source-card-toggle"
          aria-expanded={isExpanded}
          onClick={onToggle}
        >
          <span className="source-card-claim">{source.claim}</span>
        </button>
        <CitationLink id={source.evidence_id} />
      </div>

      <div className="source-card-grades">
        <GradeChip
          sourceTier={source.source_tier}
          reliability={source.reliability}
          directness={source.directness}
        />
      </div>

      <dl className="source-card-meta">
        <dt>Publisher</dt><dd>{source.publisher}</dd>
        <dt>Type</dt><dd>{sourceTypeLabel(source.source_type)}</dd>
        <dt>Published</dt><dd>{source.publication_date}</dd>
        <dt>Origin group</dt><dd>{source.independence_group}</dd>
        {source.authority_score != null && (
          <>
            <dt>Authority</dt><dd>{Math.round(source.authority_score * 100)}/100</dd>
          </>
        )}
      </dl>

      {/* Limitations are always visible pre-expansion (SPEC-036), taken
          verbatim from the record.  The grade line is a separate statement:
          calling "high reliability, high directness" a limitation asserted
          the opposite of what the grades mean. */}
      <p className="source-card-limitations">
        <span className="source-card-limitations-label">
          {SOURCES_COPY.limitationsLabel}{" "}
        </span>
        <span className="source-card-limitations-text">
          {source.limitations && source.limitations.length > 0
            ? source.limitations.join("; ")
            : SOURCES_COPY.noLimitationsStated}
        </span>
      </p>
      <p className="source-card-grade-line">
        {levelLabel(source.reliability)} reliability, {levelLabel(source.directness)} directness
      </p>

      {source.flags && source.flags.length > 0 && (
        <ul className="source-card-flags">
          {source.flags.map((f) => (
            <li key={f} className="source-card-flag">{evidenceFlagLabel(f)}</li>
          ))}
        </ul>
      )}

      {isExpanded && source.source_url && (
        <p className="source-card-url">
          <a href={source.source_url} target="_blank" rel="noreferrer noopener">
            {source.source_url}
          </a>
        </p>
      )}
    </li>
  );
}
