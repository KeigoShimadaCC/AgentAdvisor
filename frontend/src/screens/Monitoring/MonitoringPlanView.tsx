import { useEffect, useState } from "react";
import { api, type MonitoringResponse } from "../../api/client";
import { ACTION_PLAN_COPY } from "../../copy/terms";

/**
 * What to watch after the decision, and what is overdue (SPEC-053 rendering
 * phase 8's SPEC-042).
 *
 * The plan and the risk register existed, were stored outside the case
 * directory so a delivered case could stay terminal, and were served by
 * `GET /api/cases/{id}/monitoring` — which only `advisor watch` on the CLI had
 * ever called. A decision's aftercare was a terminal command.
 *
 * The register is not a second list of the same thing: an indicator says what
 * to watch, a mitigation says what to *do* about the failure it watches for,
 * and a mitigation still `not_started` against a high-severity failure mode is
 * the most actionable line on the screen.
 */
export function MonitoringPlanView({ caseId }: { caseId: string }) {
  const [data, setData] = useState<MonitoringResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getMonitoring(caseId)
      .then((res) => !cancelled && setData(res))
      // A missing plan is the normal case for an in-flight decision, not an error.
      .catch(() => !cancelled && setData({ plan: null, due: [] }));
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  if (!data?.plan || data.plan.indicators.length === 0) return null;
  const { plan, due } = data;
  const dueIds = new Set(due.map((d) => d.indicator_id));
  const openMitigations = plan.mitigations.filter((m) => m.status === "not_started");

  return (
    <section className="monitoring-plan" aria-label={ACTION_PLAN_COPY.monitoringTitle}>
      <h3>{ACTION_PLAN_COPY.monitoringTitle}</h3>
      <p className="section-help">{ACTION_PLAN_COPY.monitoringHelp}</p>

      {/* A degraded plan beats no plan, but the reader has to be able to tell
          which one they have. */}
      {!plan.concretized && (
        <p className="monitoring-warning">{ACTION_PLAN_COPY.notConcretized}</p>
      )}

      {dueIds.size > 0 && (
        <p className="monitoring-due-summary">
          {dueIds.size} {dueIds.size === 1 ? "check is" : "checks are"} due now.
        </p>
      )}

      <ul className="monitoring-list">
        {plan.indicators.map((indicator) => {
          const isDue = dueIds.has(indicator.indicator_id);
          return (
            <li
              key={indicator.indicator_id}
              className={`monitoring-item${isDue ? " due" : ""}`}
            >
              <p className="monitoring-observable">
                {indicator.observable}
                {isDue && <span className="monitoring-due-badge">{ACTION_PLAN_COPY.dueLabel}</span>}
              </p>
              <dl className="monitoring-detail">
                <dt>{ACTION_PLAN_COPY.thresholdLabel}</dt>
                <dd>{indicator.threshold}</dd>
                <dt>{ACTION_PLAN_COPY.cadenceLabel}</dt>
                <dd>every {indicator.check_cadence_days} days</dd>
                <dt>{ACTION_PLAN_COPY.wouldImplyLabel}</dt>
                <dd>{indicator.would_imply}</dd>
              </dl>
            </li>
          );
        })}
      </ul>

      {plan.mitigations.length > 0 && (
        <div className="risk-register">
          <h4>{ACTION_PLAN_COPY.mitigationsTitle}</h4>
          {openMitigations.length > 0 && (
            <p className="risk-register-open">
              {openMitigations.length} of {plan.mitigations.length} not started.
            </p>
          )}
          <ul className="mitigation-list">
            {plan.mitigations.map((m) => (
              <li key={m.mitigation_id} className={`mitigation mitigation-${m.status}`}>
                <p className="mitigation-text">{m.mitigation}</p>
                <p className="mitigation-meta">
                  <span className="mitigation-owner">
                    {ACTION_PLAN_COPY.ownerLabel}: {m.owner}
                  </span>
                  <span className="mitigation-status">{m.status.replace(/_/g, " ")}</span>
                  {m.severity && <span className="mitigation-severity">{m.severity} severity</span>}
                </p>
                {m.failure_mode && (
                  <p className="mitigation-against">Guards against: {m.failure_mode}</p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
