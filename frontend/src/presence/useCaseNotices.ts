import { useEffect, useRef } from "react";
import { noticeFor, notify, requestPermissionOnRun } from "./notify";
import type { CaseView } from "../generated/case_view";

/**
 * Turn case-state changes into notices (SPEC-051).
 *
 * Two properties keep this from becoming a nuisance:
 *
 *  - **Permission is requested the first time a case is actually running**, not
 *    on load. An unexplained dialog on first visit is the most common way this
 *    gets refused permanently, and a refusal cannot be undone from the page.
 *  - **Each notice fires once per state**, tracked by a ref. Without this, every
 *    projection refetch — and SPEC-047 refetches on every content event — would
 *    re-notify for the same gate.
 */
export function useCaseNotices(view: CaseView | null): void {
  const asked = useRef(false);
  const lastNotified = useRef<string | null>(null);

  useEffect(() => {
    if (!view) return;
    const running = !view.is_terminal && view.needs_you === "none";
    if (running && !asked.current) {
      asked.current = true;
      void requestPermissionOnRun();
    }
  }, [view]);

  useEffect(() => {
    if (!view) return;
    const notice = noticeFor(view);
    if (!notice) return;
    const key = `${view.case_id}:${notice.kind}`;
    if (lastNotified.current === key) return;
    lastNotified.current = key;
    notify(notice);
  }, [view]);
}
