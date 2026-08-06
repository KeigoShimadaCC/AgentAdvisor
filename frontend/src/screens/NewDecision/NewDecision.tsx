import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type ErrorResponse } from "../../api/client";
import {
  EFFORT_PROFILES,
  EXAMPLE_CHIPS,
  METHOD_PROMISE,
  NOT_LICENSED_ADVICE,
  type EffortKey,
} from "../../copy/terms";
import { effortTimeRange, effortHistoryNote, type EffortHistory } from "../../copy/effort";
import { writeAltitude } from "../shell/altitude";
import { setPresence } from "../shell/presence";
import { readDraft, writeDraft, clearDraft, type CommissionDraft } from "./commissionDraft";

/**
 * Commissioning (SPEC-050).
 *
 * What this replaces: a disabled button reading "Framing…" that polled for up
 * to thirty minutes with nothing to look at, no case to open, and no recovery
 * from a reload. The user had committed to a decision and the product gave them
 * a spinner.
 *
 * Now the case is created and the user goes straight to it. SPEC-046 made
 * `POST /api/cases` return 202 as soon as the case is durable, and SPEC-047
 * gave the case surface a narrator, so intake and framing happen *in front of
 * the user* — which is the first and best demonstration of the method. The
 * clarification interview is not lost: the scope sheet asks for it, which is
 * where it belongs, because that is the screen about scope.
 *
 * Two questions route the whole experience and nothing else. Both are
 * preferences and neither is written into the case: what the case *is* must not
 * depend on how someone likes to read.
 */
export function NewDecision() {
  const navigate = useNavigate();
  const [draft, setDraft] = useState<CommissionDraft>(readDraft);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<EffortHistory | null>(null);

  useEffect(() => {
    // A missing history is the normal case on a fresh install, and the copy
    // says so — it is never an error worth showing.
    api.getEffortHistory().then(setHistory).catch(() => setHistory(null));
  }, []);

  function update(patch: Partial<CommissionDraft>) {
    const next = { ...draft, ...patch };
    setDraft(next);
    writeDraft(next);
  }

  const trimmed = draft.prompt.trim();

  async function handleCreate() {
    if (!trimmed || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const profile = EFFORT_PROFILES[draft.effort];
      const created = await api.createCase(trimmed, profile.backendValue);
      // Preferences, applied client-side. Neither reaches the case directory.
      writeAltitude(draft.shape);
      setPresence(draft.presence);
      clearDraft();
      navigate(`/cases/${created.case_id}`);
    } catch (e) {
      const err = e as ErrorResponse;
      setError(err.detail ?? err.error);
      setSubmitting(false);
    }
  }

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
        value={draft.prompt}
        onChange={(e) => update({ prompt: e.target.value })}
        rows={6}
        aria-describedby="prompt-help"
      />
      <p id="prompt-help" className="prompt-hint">
        Write the decision as a question. Include the options you are considering and any hard
        constraints.
      </p>

      <fieldset className="effort-selector">
        <legend>How deep should this go?</legend>
        <div className="effort-options">
          {(Object.keys(EFFORT_PROFILES) as EffortKey[]).map((key) => {
            const p = EFFORT_PROFILES[key];
            const selected = draft.effort === key;
            return (
              <button
                key={key}
                type="button"
                className={`effort-chip${selected ? " selected" : ""}`}
                aria-pressed={selected}
                onClick={() => update({ effort: key })}
              >
                <span className="effort-label">{p.label}</span>
                <span className="effort-time">{effortTimeRange(history, p.backendValue)}</span>
                <span className="effort-blurb">{p.blurb}</span>
              </button>
            );
          })}
        </div>
        <p className="effort-history-note">{effortHistoryNote(history)}</p>
      </fieldset>

      <fieldset className="commission-preferences">
        <legend>How should I hand this back?</legend>
        <div className="preference-row" role="group" aria-label="What to hand you">
          <PreferenceChip
            selected={draft.shape === "answer"}
            onClick={() => update({ shape: "answer" })}
            label="A one-page answer"
            blurb="The recommendation and what would change it. Everything else stays one click away."
          />
          <PreferenceChip
            selected={draft.shape === "reasoning"}
            onClick={() => update({ shape: "reasoning" })}
            label="The full advisory brief"
            blurb="The whole argument, with provenance, objections and citations."
          />
        </div>

        <div className="preference-row" role="group" aria-label="Watch or be notified">
          <PreferenceChip
            selected={draft.presence === "watch"}
            onClick={() => update({ presence: "watch" })}
            label="I'll watch"
            blurb="Sit with the deliberation as it runs."
          />
          <PreferenceChip
            selected={draft.presence === "notify"}
            onClick={() => update({ presence: "notify" })}
            label="Ping me"
            blurb="Tell me when it needs a decision from me."
          />
        </div>
      </fieldset>

      <div className="example-chips" role="group" aria-label="Example decisions">
        <p className="chips-label">Or start from an example:</p>
        {EXAMPLE_CHIPS.map((chip) => (
          <button
            key={chip.label}
            type="button"
            className="example-chip"
            onClick={() => update({ prompt: chip.prompt })}
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
        {submitting ? "Opening the case…" : "Start this case"}
      </button>
    </div>
  );
}

function PreferenceChip({
  selected,
  onClick,
  label,
  blurb,
}: {
  selected: boolean;
  onClick: () => void;
  label: string;
  blurb: string;
}) {
  return (
    <button
      type="button"
      className={`preference-chip${selected ? " selected" : ""}`}
      aria-pressed={selected}
      onClick={onClick}
    >
      <span className="preference-label">{label}</span>
      <span className="preference-blurb">{blurb}</span>
    </button>
  );
}
