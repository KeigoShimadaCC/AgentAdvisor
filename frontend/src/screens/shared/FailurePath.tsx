import { useState } from "react";
import { api } from "../../api/client";
import { useToast } from "./Toast";
import { FAILURE_COPY, stopReasonLabel, budgetDimensionLabel } from "../../copy/terms";
import type { CaseView } from "../../generated/case_view";

interface FailurePathProps {
  view: CaseView;
}

/**
 * Disclosed failure-path renderings for failed, interrupted, and early-stop
 * cases (SPEC-035).
 */
export function FailurePath({ view }: FailurePathProps) {
  const [resuming, setResuming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  async function resume() {
    setResuming(true);
    setError(null);
    try {
      await api.resumeCase(view.case_id);
      toast.show("Resuming this case.", "success");
    } catch (e) {
      const detail = (e as { detail?: string; error?: string }).detail ?? "Resume failed";
      setError(detail);
      toast.show(detail, "error");
    } finally {
      setResuming(false);
    }
  }

  // Accepting from the early-stop panel used to fire and say nothing at all,
  // so the click was indistinguishable from a dead button.
  async function acceptAsIs() {
    try {
      await api.approveDelivery(view.case_id, "user");
      toast.show("Recommendation accepted as it stands.", "success");
    } catch (e) {
      const detail = (e as { detail?: string; error?: string }).detail ?? "Accept failed";
      setError(detail);
      toast.show(detail, "error");
    }
  }

  if (view.stage === "failed") {
    return (
      <section className="failure-path" role="alert">
        <h3>{FAILURE_COPY.interruptedTitle}</h3>
        <p>{FAILURE_COPY.interruptedDetail}</p>
        <button
          type="button"
          className="primary-action"
          onClick={resume}
          disabled={resuming}
        >
          {FAILURE_COPY.resume}
        </button>
        {error && <p className="error">{error}</p>}
      </section>
    );
  }

  const disclosure = view.integrity?.disclosure;
  const stopReasons = (disclosure?.stop_reasons as string[] | undefined) ?? [];
  if (stopReasons.length > 0) {
    return (
      <section className="early-stop" role="alert">
        <h3>{FAILURE_COPY.earlyStopTitle}</h3>
        <p>{FAILURE_COPY.earlyStopDetail}</p>
        <p>Why it stopped: {stopReasons.map(stopReasonLabel).join("; ")}</p>
        <p>
          What ran out:{" "}
          {((disclosure?.exhausted_dimensions as string[] | undefined) ?? [])
            .map(budgetDimensionLabel)
            .join(", ")}
        </p>
        <div className="early-stop-actions">
          {view.stage === "awaiting_final_approval" && (
            <button
              type="button"
              className="primary-action"
              onClick={acceptAsIs}
            >
              {FAILURE_COPY.acceptAsIs}
            </button>
          )}
          <button
            type="button"
            className="secondary-action"
            onClick={resume}
            disabled={resuming}
          >
            {FAILURE_COPY.extendFraming}
          </button>
        </div>
        {error && <p className="error">{error}</p>}
      </section>
    );
  }

  return null;
}
