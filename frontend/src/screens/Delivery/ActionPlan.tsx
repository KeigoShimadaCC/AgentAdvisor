import type { NextActionView } from "../../generated/case_view";

/**
 * The typed action plan (SPEC-053 rendering phase 8's SPEC-041).
 *
 * Phase 8 replaced a list of strings with a typed artifact — owner, date, first
 * step, why now, cost, dependencies — and the projection flattened it back into
 * one sentence per action on the way to the screen. Every typed field was
 * computed and then discarded.
 *
 * The first step is given its own weight because it is the field that makes a
 * plan get started: "place the initial 30% allocation" is a decision, "block 30
 * minutes and start" is an action someone can take today.
 */
export function ActionPlan({ actions }: { actions: NextActionView[] }) {
  if (actions.length === 0) return null;

  const byId = new Map(actions.map((a) => [a.action_id, a]));

  return (
    <section className="action-plan" aria-label="What to do next">
      <h3>What to do next</h3>
      <ol className="action-plan-list">
        {actions.map((action) => (
          <li key={action.action_id} className="action-plan-item">
            <p className="action-plan-what">{action.action}</p>
            <p className="action-plan-first-step">
              <span className="action-plan-label">Start with</span>
              {action.first_step}
            </p>
            <dl className="action-plan-meta">
              <div>
                <dt>Owner</dt>
                <dd>{action.owner}</dd>
              </div>
              <div>
                <dt>By</dt>
                <dd>{action.by_date}</dd>
              </div>
              {action.estimated_cost && (
                <div>
                  <dt>Cost</dt>
                  <dd>{action.estimated_cost}</dd>
                </div>
              )}
              {action.depends_on && action.depends_on.length > 0 && (
                <div>
                  <dt>After</dt>
                  {/* Named, not numbered: "after N-001" tells a reader nothing
                      they can act on. */}
                  <dd>
                    {action.depends_on
                      .map((id) => byId.get(id)?.action || id)
                      .join("; ")}
                  </dd>
                </div>
              )}
            </dl>
            <p className="action-plan-why">{action.why_now}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
