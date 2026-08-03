import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { TranslatedEvent } from "../../api/sse";
import {
  INSPECTOR_COPY,
  artifactKindLabel,
  sourceTierLabel,
  levelLabel,
  evidenceFlagLabel,
  objectionStatusLabel,
  assumptionStatusLabel,
  assumptionTypeLabel,
} from "../../copy/terms";
import { GradeChip } from "../shared/GradeChip";

interface RecordInspectorProps {
  caseId: string;
  artifactId: string;
  /** Live audit events, used to find the slice that mentions this record. */
  events: TranslatedEvent[];
  onClose: () => void;
}

interface ArtifactData {
  artifact_id: string;
  schema: string;
  data: unknown;
}

/** Pull a field from a record object as a string, or null. */
function field(record: Record<string, unknown>, key: string): string | null {
  const v = record[key];
  if (v == null) return null;
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  return null;
}

/** Whether a raw audit event payload mentions the artifact id. */
function eventMentions(event: TranslatedEvent, id: string): boolean {
  const blob = JSON.stringify({ ...event.raw_payload, actor: event.actor });
  return blob.includes(id);
}

/**
 * Slide-over record inspector (SPEC-036).
 *
 * Shows the full artifact in product language, a provenance chain
 * (claim → grades → excerpt terminus) for evidence records, and a
 * "show the machinery" toggle that reveals the raw YAML plus the audit
 * slice that touched this record.
 */
export function RecordInspector({ caseId, artifactId, events, onClose }: RecordInspectorProps) {
  const [artifact, setArtifact] = useState<ArtifactData | null>(null);
  const [rawYaml, setRawYaml] = useState<string | null>(null);
  const [showMachinery, setShowMachinery] = useState(false);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    setLoading(true);
    setNotFound(false);
    setArtifact(null);
    setRawYaml(null);
    setShowMachinery(false);
    api
      .getArtifact(caseId, artifactId)
      .then((a) => setArtifact(a as ArtifactData))
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [caseId, artifactId]);

  // Fetch raw YAML lazily when the machinery toggle is first opened.
  useEffect(() => {
    if (!showMachinery || rawYaml !== null) return;
    api
      .getFile(caseId, `${artifactId}.yaml`)
      .then(setRawYaml)
      .catch(() => setRawYaml("Raw file unavailable."));
  }, [showMachinery, rawYaml, caseId, artifactId]);

  const auditSlice = events.filter((e) => eventMentions(e, artifactId));
  const record =
    artifact && typeof artifact.data === "object" && artifact.data !== null && !Array.isArray(artifact.data)
      ? (artifact.data as Record<string, unknown>)
      : null;

  // Close on Escape.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const kind = artifactKindLabel(artifactId);
  const isEvidence = artifactId.startsWith("E-");

  return (
    <aside className="inspector" role="dialog" aria-label={`${INSPECTOR_COPY.title}: ${artifactId}`} aria-modal="false">
      <div className="inspector-header">
        <span className="inspector-kind">{kind}</span>
        <code className="inspector-id">{artifactId}</code>
        <button
          type="button"
          className="inspector-close"
          aria-label={INSPECTOR_COPY.closeLabel}
          onClick={onClose}
        >
          ×
        </button>
      </div>

      <div className="inspector-body">
        {loading && <p>{INSPECTOR_COPY.loading}</p>}
        {notFound && <p className="error">{INSPECTOR_COPY.notFound}</p>}

        {record && isEvidence && (
          <EvidenceChain record={record} />
        )}

        {record && !isEvidence && (
          <GenericRecord record={record} />
        )}

        {record && (
          <div className="inspector-machinery">
            <button
              type="button"
              className="link-button"
              aria-expanded={showMachinery}
              onClick={() => setShowMachinery((s) => !s)}
            >
              {showMachinery ? INSPECTOR_COPY.machineryHide : INSPECTOR_COPY.machineryToggle}
            </button>
            {showMachinery && (
              <div className="inspector-machinery-body">
                <h4>{INSPECTOR_COPY.rawYaml}</h4>
                <pre className="inspector-raw">{rawYaml ?? "Loading…"}</pre>
                <h4>{INSPECTOR_COPY.auditSlice}</h4>
                {auditSlice.length === 0 ? (
                  <p className="screen-help">No audit events reference this record yet.</p>
                ) : (
                  <ul className="inspector-audit-slice">
                    {auditSlice.map((e, i) => (
                      <li key={i} className={e.technical ? "event-technical" : "event-user"}>
                        <small>[{e.line_cursor}]</small> {e.message}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}

/** Chain view for an evidence record: claim → grades → excerpt terminus. */
function EvidenceChain({ record }: { record: Record<string, unknown> }) {
  const claim = field(record, "claim") ?? field(record, "summary") ?? "—";
  const excerpt = field(record, "excerpt") ?? field(record, "quote") ?? null;
  const reliability = field(record, "reliability") ?? "—";
  const directness = field(record, "directness") ?? "—";
  const sourceTier = field(record, "source_tier");
  const publisher = field(record, "publisher") ?? "—";
  const sourceUrl = field(record, "source_url") ?? null;
  // Accept both the schema's string[] and a bare string, and drop blanks so an
  // empty entry cannot render as a stray bullet.
  const rawLimitations = record["limitations"];
  const limitationList = (
    Array.isArray(rawLimitations)
      ? rawLimitations.map((item) => String(item))
      : typeof rawLimitations === "string"
        ? [rawLimitations]
        : []
  )
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
  const flags = Array.isArray(record["flags"]) ? (record["flags"] as string[]) : [];

  return (
    <div className="inspector-chain">
      <h4>{INSPECTOR_COPY.chainHeading}</h4>

      <div className="inspector-chain-step">
        <span className="inspector-chain-label">{INSPECTOR_COPY.chainClaim}</span>
        <p>{claim}</p>
      </div>

      <div className="inspector-chain-step">
        <span className="inspector-chain-label">{INSPECTOR_COPY.chainGrades}</span>
        <GradeChip
          sourceTier={sourceTier}
          reliability={reliability}
          directness={directness}
        />
        <p className="inspector-publisher">
          {publisher}
          {sourceUrl && (
            <>
              {" · "}
              <a
                className="inspector-source-link"
                href={sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                {sourceUrl}
              </a>
            </>
          )}
        </p>
        {flags.length > 0 && (
          <ul className="inspector-flags">
            {flags.map((f) => (
              <li key={f} className="inspector-flag">{evidenceFlagLabel(f)}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="inspector-chain-step">
        <span className="inspector-chain-label">{INSPECTOR_COPY.chainLimitations}</span>
        {/* The schema types limitations as string[], so stringifying it leaked
            JSON brackets and quotes into the chain; SPEC-036 wants it verbatim. */}
        {limitationList.length > 0 ? (
          limitationList.length === 1 ? (
            <p>{limitationList[0]}</p>
          ) : (
            <ul className="inspector-limitations">
              {limitationList.map((item, i) => (
                <li key={`${item}-${i}`}>{item}</li>
              ))}
            </ul>
          )
        ) : (
          <p className="screen-help">No limitations stated.</p>
        )}
      </div>

      <div className="inspector-chain-step">
        <span className="inspector-chain-label">{INSPECTOR_COPY.chainExcerpt}</span>
        {excerpt ? (
          <blockquote className="inspector-excerpt">{excerpt}</blockquote>
        ) : (
          <p className="screen-help">No excerpt recorded.</p>
        )}
      </div>
    </div>
  );
}

/** Generic record renderer for non-evidence artifacts (A-, O-, T-, Q-). */
function GenericRecord({ record }: { record: Record<string, unknown> }) {
  // Apply terminology to a few well-known fields.
  const labeled: Record<string, (v: string) => string> = {
    type: assumptionTypeLabel,
    status: (v) => {
      // Distinguish assumption vs objection by presence of objection-ish fields.
      if ("resolution_status" in record) return objectionStatusLabel(v);
      return assumptionStatusLabel(v);
    },
    materiality: (v) => levelLabel(v),
    confidence: (v) => levelLabel(v),
    reliability: (v) => levelLabel(v),
    directness: (v) => levelLabel(v),
    resolution_status: objectionStatusLabel,
    node_type: (v) => v,
  };

  return (
    <dl className="inspector-generic">
      {Object.entries(record).map(([key, value]) => {
        const display =
          typeof value === "string" || typeof value === "number" || typeof value === "boolean"
            ? String(value)
            : JSON.stringify(value);
        const fmt = labeled[key];
        return (
          <div key={key} className="inspector-generic-row">
            <dt>{key.replace(/_/g, " ")}</dt>
            <dd>{fmt ? fmt(String(value)) : display}</dd>
          </div>
        );
      })}
    </dl>
  );
}
