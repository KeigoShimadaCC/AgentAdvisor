import { useState } from "react";
import { api } from "../../api/client";
import { useToast } from "./Toast";
import { STALL_WINDOW_MS } from "./useCaseView";

/**
 * A case that was created and never started (SPEC-055).
 *
 * SPEC-046 made creation return as soon as the case is durable, which is right,
 * and it opened a gap: between "created" and "running" nothing was watching. A
 * worker that dies at startup leaves a case that looks like it is about to
 * begin, forever — and a case that is about to begin and a case that will never
 * begin look identical, which is the failure this whole spec is about.
 *
 * `POST /resume` already exists; all that was missing was anything that noticed.
 */
export function StalledCase({ caseId }: { caseId: string }) {
  const [resuming, setResuming] = useState(false);
  const toast = useToast();

  async function resume() {
    setResuming(true);
    try {
      await api.resumeCase(caseId);
      toast.show("Restarting this case.", "success");
    } catch (e) {
      toast.show((e as { detail?: string }).detail ?? "Could not restart it.", "error");
    } finally {
      setResuming(false);
    }
  }

  return (
    <section className="stalled-case" role="alert" aria-label="This case has not started">
      <p className="stalled-case-what">
        This case was created {Math.round(STALL_WINDOW_MS / 1000)} seconds ago and has not done
        anything yet. Usually that means the worker did not start.
      </p>
      <button type="button" className="primary-action" onClick={resume} disabled={resuming}>
        {resuming ? "Restarting…" : "Restart it"}
      </button>
      <p className="screen-help">
        Nothing is lost by restarting — the case is on disk and resumes from its last checkpoint.
      </p>
    </section>
  );
}
