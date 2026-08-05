import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { api, type ErrorResponse } from "../../api/client";
import {
  EFFORT_PROFILES,
  EXAMPLE_CHIPS,
  METHOD_PROMISE,
  NOT_LICENSED_ADVICE,
  FAILURE_COPY,
  DEFAULT_EFFORT,
  type EffortKey,
} from "../../copy/terms";
import { InterviewCards } from "./InterviewCards";
import type { IntakeRecord } from "../../generated/intake_record";

/**
 * The opening screen (SPEC-034 §13.1): one large prompt, an effort selector
 * with honest time-range labels, example chips from the benchmark domains,
 * the method-promise line with the not-licensed-advice disclaimer.
 *
 * On submit it POSTs ``createCase`` and, once the case parks at the scope
 * gate, transitions to the scope sheet.  When the intake record carries
 * clarification questions, the interview cards are shown inline first.
 */
export function NewDecision() {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState("");
  const [effort, setEffort] = useState<EffortKey>(DEFAULT_EFFORT);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // After case creation we hold the case id + intake record so the
  // interview cards can render inline before routing to the scope sheet.
  const [caseId, setCaseId] = useState<string | null>(null);
  const [intake, setIntake] = useState<IntakeRecord | null>(null);

  const trimmed = prompt.trim();

  /**
   * Wait for the case to reach the scope gate.
   *
   * INTERIM (SPEC-046 → SPEC-050). Case creation now returns `202` as soon as
   * the case is durable, instead of holding the HTTP request open through
   * intake and framing — which on a real backend meant a request held for
   * minutes, at the mercy of every proxy timeout in between. The server no
   * longer blocks; until SPEC-050 replaces this screen with one that routes
   * immediately and streams, the client waits here so the scope sheet is never
   * opened before there is a framing to review.
   */
  async function waitForScopeGate(newCaseId: string): Promise<void> {
    const deadline = Date.now() + 30 * 60 * 1000;
    while (Date.now() < deadline) {
      const view = await api.getCaseView(newCaseId);
      if (view.needs_you === "scope_checkpoint") return;
      if (view.stage === "failed") {
        throw { error: "case_failed", detail: FAILURE_COPY.failedDetail } as ErrorResponse;
      }
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }
    throw {
      error: "timed_out",
      detail: "This is taking longer than expected. Open the case to see where it is.",
    } as ErrorResponse;
  }

  async function handleCreate() {
    if (!trimmed || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const profile = EFFORT_PROFILES[effort];
      const created = await api.createCase(trimmed, profile.backendValue);
      await waitForScopeGate(created.case_id);
      setCaseId(created.case_id);
      // Load the intake record to surface clarification questions inline.
      try {
        const env = await api.getIntakeRecord(created.case_id);
        setIntake(env.data);
      } catch {
        // Intake may not be ready instantly; route to the scope sheet
        // which will re-fetch.
        setIntake(null);
      }
    } catch (e) {
      const err = e as ErrorResponse;
      setError(err.detail ?? err.error);
    } finally {
      setSubmitting(false);
    }
  }

  function handleInterviewsDone() {
    if (caseId) navigate(`/cases/${caseId}/scope`);
  }

  // ── Interview cards phase ──────────────────────────────────────────────
  if (caseId && intake && intake.clarification_questions && intake.clarification_questions.length > 0) {
    return (
      <div className="new-decision">
        <h2>A few questions before I frame this</h2>
        <p className="screen-help">
          These help me frame your decision well. Answer what you can, or skip
          and I will assume something reasonable.
        </p>
        <InterviewCards
          caseId={caseId}
          questions={intake.clarification_questions}
          onDone={handleInterviewsDone}
        />
      </div>
    );
  }

  // If a case was created but no clarification questions, go straight to scope.
  // Declarative redirect: calling navigate() here would be a router state update
  // during render, which React rejects with a cross-component setState warning.
  if (caseId && (!intake || !intake.clarification_questions || intake.clarification_questions.length === 0)) {
    return <Navigate to={`/cases/${caseId}/scope`} replace />;
  }

  // ── Entry phase ─────────────────────────────────────────────────────────
  return (
    <div className="new-decision">
      <h2>What decision are you weighing?</h2>
      <p className="screen-help">
        Describe it in your own words. The more context you give, the better the framing.
      </p>

      <label htmlFor="decision-prompt" className="sr-only">
        Decision prompt
      </label>
      <textarea
        id="decision-prompt"
        className="decision-prompt"
        placeholder="e.g. Should I take the Series B offer or stay at my current role for another year?"
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        rows={6}
        aria-describedby="prompt-help"
      />
      <p id="prompt-help" className="prompt-hint">
        Write the decision as a question. Include the options you are considering and any hard constraints.
      </p>

      <fieldset className="effort-selector">
        <legend>How deep should this go?</legend>
        <div className="effort-options">
          {(Object.keys(EFFORT_PROFILES) as EffortKey[]).map((key) => {
            const p = EFFORT_PROFILES[key];
            const selected = effort === key;
            return (
              <button
                key={key}
                type="button"
                className={`effort-chip${selected ? " selected" : ""}`}
                aria-pressed={selected}
                onClick={() => setEffort(key)}
              >
                <span className="effort-label">{p.label}</span>
                <span className="effort-time">{p.timeRange}</span>
                <span className="effort-blurb">{p.blurb}</span>
              </button>
            );
          })}
        </div>
      </fieldset>

      <div className="example-chips" role="group" aria-label="Example decisions">
        <p className="chips-label">Or start from an example:</p>
        {EXAMPLE_CHIPS.map((chip) => (
          <button
            key={chip.label}
            type="button"
            className="example-chip"
            onClick={() => setPrompt(chip.prompt)}
          >
            {chip.label}
          </button>
        ))}
      </div>

      <p className="method-promise">{METHOD_PROMISE}</p>
      <p className="not-licensed-advice">{NOT_LICENSED_ADVICE}</p>

      {error && <p className="error" role="alert">{error}</p>}

      <button
        type="button"
        className="primary-action"
        onClick={handleCreate}
        disabled={!trimmed || submitting}
      >
        {submitting ? "Framing…" : "Frame this decision"}
      </button>
    </div>
  );
}
