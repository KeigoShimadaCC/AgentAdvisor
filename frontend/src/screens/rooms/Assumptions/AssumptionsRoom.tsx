import { useMemo, useState } from "react";
import { RoomShell } from "../../shared/RoomShell";
import { SplitBar } from "../../shared/SplitBar";
import { HonestEmpty } from "../../shared/HonestEmpty";
import { CitationLink } from "../../inspector/CitationLink";
import type { CaseView, AssumptionView } from "../../../generated/case_view";
import {
  assumptionTypeLabel,
  assumptionStatusLabel,
  levelLabel,
  probabilityPhrase,
  ROOMS,
} from "../../../copy/terms";

type TypeFilter = "all" | "forecast" | "structural" | "operational" | "financial" | "regulatory" | "behavioral";
type StatusFilter = "all" | "unresolved" | "supported" | "contradicted" | "retired";
type MaterialityFilter = "all" | "high" | "medium" | "low";

export function AssumptionsRoom() {
  return (
    <RoomShell room="assumptions">
      {(view) => <AssumptionsBody view={view} />}
    </RoomShell>
  );
}

function AssumptionsBody({ view }: { view: CaseView }) {
  const room = view.rooms?.assumptions;
  const assumptions = room?.assumptions ?? [];
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [materialityFilter, setMaterialityFilter] = useState<MaterialityFilter>("all");

  const filtered = useMemo(() => {
    return assumptions.filter((a) => {
      if (typeFilter !== "all" && a.type !== typeFilter) return false;
      if (statusFilter !== "all" && a.status !== statusFilter) return false;
      if (materialityFilter !== "all" && a.materiality !== materialityFilter) return false;
      return true;
    });
  }, [assumptions, typeFilter, statusFilter, materialityFilter]);

  // Load-bearing callout: highest materiality (high > medium > low) × lowest confidence (low < medium < high).
  const loadBearing = useMemo(() => {
    const order: Record<string, number> = { high: 3, medium: 2, low: 1 };
    const confOrder: Record<string, number> = { low: 1, medium: 2, high: 3 };
    return [...assumptions]
      .sort((a, b) => {
        const matDiff = (order[b.materiality] ?? 0) - (order[a.materiality] ?? 0);
        if (matDiff !== 0) return matDiff;
        return (confOrder[a.confidence] ?? 9) - (confOrder[b.confidence] ?? 9);
      })[0];
  }, [assumptions]);

  if (!room || assumptions.length === 0) {
    return (
      <HonestEmpty
        truth="not_yet"
        heading={`${ROOMS.assumptions.label}: not yet — assumptions have not been recorded for this case.`}
      />
    );
  }

  const isLoadBearing =
    loadBearing && loadBearing.materiality === "high" && loadBearing.confidence !== "high";

  return (
    <div className="assumptions-room">
      {isLoadBearing && (
        <section className="load-bearing-callout" aria-label="Load-bearing assumption">
          <h3>Load-bearing assumption</h3>
          <p>
            The whole recommendation leans on this assumption, and the evidence for it is{" "}
            {levelLabel(loadBearing.confidence).toLowerCase()}:
          </p>
          <p className="load-bearing-claim">
            <CitationLink id={loadBearing.assumption_id}>{loadBearing.assumption_id}</CitationLink>
            {" — "}{loadBearing.claim}
          </p>
        </section>
      )}

      {/* Facet filters */}
      <section className="assumption-facets" aria-label="Filter assumptions">
        <fieldset className="facet-group">
          <legend>Type</legend>
          <FacetSelect
            label="Type"
            value={typeFilter}
            onChange={(v) => setTypeFilter(v as TypeFilter)}
            options={[
              ["all", "All"],
              ["forecast", "Forecast"],
              ["structural", "Structural"],
              ["operational", "Operational"],
              ["financial", "Financial"],
              ["regulatory", "Regulatory"],
              ["behavioral", "Behavioral"],
            ]}
          />
        </fieldset>
        <fieldset className="facet-group">
          <legend>Status</legend>
          <FacetSelect
            label="Status"
            value={statusFilter}
            onChange={(v) => setStatusFilter(v as StatusFilter)}
            options={[
              ["all", "All"],
              ["unresolved", "Unresolved"],
              ["supported", "Supported"],
              ["contradicted", "Contradicted"],
              ["retired", "Retired"],
            ]}
          />
        </fieldset>
        <fieldset className="facet-group">
          <legend>Materiality</legend>
          <FacetSelect
            label="Materiality"
            value={materialityFilter}
            onChange={(v) => setMaterialityFilter(v as MaterialityFilter)}
            options={[
              ["all", "All"],
              ["high", "High"],
              ["medium", "Medium"],
              ["low", "Low"],
            ]}
          />
        </fieldset>
      </section>

      {/* Ledger */}
      <ul className="assumption-ledger">
        {filtered.map((a) => (
          <AssumptionRow key={a.assumption_id} assumption={a} />
        ))}
        {filtered.length === 0 && (
          <li><HonestEmpty truth="nothing_found" heading="No assumptions match these filters." /></li>
        )}
      </ul>
    </div>
  );
}

interface FacetSelectProps {
  /** Accessible name for the control itself, not the group around it. */
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
}

function FacetSelect({ label, value, onChange, options }: FacetSelectProps) {
  return (
    <select
      className="facet-select"
      // The enclosing <legend> names the group; a control needs its own name.
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {options.map(([v, label]) => (
        <option key={v} value={v}>{label}</option>
      ))}
    </select>
  );
}

function AssumptionRow({ assumption }: { assumption: AssumptionView }) {
  const forCount = assumption.evidence_for?.length ?? 0;
  const againstCount = assumption.evidence_against?.length ?? 0;
  const isSkipped = assumption.status === "unresolved" && forCount === 0 && againstCount === 0;

  return (
    <li className="assumption-row">
      <div className="assumption-row-head">
        <CitationLink id={assumption.assumption_id} />
        <span className="assumption-type">{assumptionTypeLabel(assumption.type)}</span>
        <span className={`assumption-status assumption-status-${assumption.status}`}>
          {assumptionStatusLabel(assumption.status)}
        </span>
        <span className={`assumption-materiality assumption-materiality-${assumption.materiality}`}>
          {levelLabel(assumption.materiality)} materiality
        </span>
      </div>

      <p className="assumption-claim">{assumption.claim}</p>

      <div className="assumption-probability">
        <span className="assumption-probability-phrase">
          {probabilityPhrase(assumption.estimate_point)}
        </span>
        {assumption.estimate_point != null && (
          <span className="assumption-probability-point">
            {Math.round(assumption.estimate_point * 100)}%
          </span>
        )}
      </div>

      <SplitBar forCount={forCount} againstCount={againstCount} label={assumption.claim} />

      {(assumption.evidence_for?.length ?? 0) > 0 && (
        <p className="assumption-evidence-for">
          <span className="assumption-evidence-label">Supports: </span>
          {assumption.evidence_for!.map((id, i) => (
            <span key={id}>
              {i > 0 && ", "}
              <CitationLink id={id} />
            </span>
          ))}
        </p>
      )}
      {(assumption.evidence_against?.length ?? 0) > 0 && (
        <p className="assumption-evidence-against">
          <span className="assumption-evidence-label">Against: </span>
          {assumption.evidence_against!.map((id, i) => (
            <span key={id}>
              {i > 0 && ", "}
              <CitationLink id={id} />
            </span>
          ))}
        </p>
      )}

      {isSkipped && (
        <p className="assumption-skipped-origin">
          <span className="assumption-skipped-label">Origin: </span>
          Skipped question — no evidence gathered for or against.
        </p>
      )}
    </li>
  );
}
