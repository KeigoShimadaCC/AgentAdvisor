import { useState } from "react";
import { api } from "../../api/client";
import { useToast } from "../shared/Toast";

/**
 * "What actually happened?" (SPEC-051).
 *
 * `POST /api/cases/{id}/outcome` has existed since SPEC-042 and only
 * `scripts/record_outcome.py` ever called it — so the calibration record could
 * only ever be fed from a terminal. The loop that makes the whole Brier
 * machinery mean anything was closed to the person who made the decision.
 *
 * Deliberately asks two separate questions. "Did you follow it" and "did it work
 * out" are different facts, and a recommendation that was right but not followed
 * is not a failed forecast — collapsing them would poison the record.
 */
export function OutcomePrompt({ caseId }: { caseId: string }) {
  const [open, setOpen] = useState(false);
  const [summary, setSummary] = useState("");
  const [followed, setFollowed] = useState(true);
  const [realized, setRealized] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [recorded, setRecorded] = useState(false);
  const toast = useToast();

  async function submit() {
    if (!summary.trim() || submitting) return;
    setSubmitting(true);
    try {
      await api.recordOutcome(caseId, { summary: summary.trim(), followed, realized });
      setRecorded(true);
      toast.show("Outcome recorded — it counts towards the calibration score.", "success");
    } catch (e) {
      const detail = (e as { detail?: string }).detail ?? "Could not record that outcome.";
      toast.show(detail, "error");
    } finally {
      setSubmitting(false);
    }
  }

  if (recorded) {
    return (
      <section className="outcome-prompt" aria-label="Outcome recorded">
        <p>Recorded. This case now counts towards the system's calibration.</p>
      </section>
    );
  }

  if (!open) {
    return (
      <section className="outcome-prompt" aria-label="Record what happened">
        <p className="outcome-prompt-ask">
          Do you know how this turned out? Recording it is the only thing that makes the system's
          calibration score mean anything.
        </p>
        <button type="button" className="secondary-action" onClick={() => setOpen(true)}>
          Record what happened
        </button>
      </section>
    );
  }

  return (
    <section className="outcome-prompt outcome-prompt-open" aria-label="Record what happened">
      <label htmlFor="outcome-summary">What happened?</label>
      <textarea
        id="outcome-summary"
        rows={3}
        value={summary}
        onChange={(e) => setSummary(e.target.value)}
      />

      <label className="outcome-check">
        <input type="checkbox" checked={followed} onChange={(e) => setFollowed(e.target.checked)} />
        I followed the recommendation
      </label>
      <label className="outcome-check">
        <input type="checkbox" checked={realized} onChange={(e) => setRealized(e.target.checked)} />
        The forecast outcome actually happened
      </label>
      <p className="screen-help">
        These are separate on purpose: a recommendation that was right but not followed is not a
        failed forecast.
      </p>

      <button
        type="button"
        className="primary-action"
        onClick={submit}
        disabled={!summary.trim() || submitting}
      >
        {submitting ? "Recording…" : "Record this outcome"}
      </button>
    </section>
  );
}
