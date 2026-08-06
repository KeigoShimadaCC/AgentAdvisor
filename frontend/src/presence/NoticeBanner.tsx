import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { onFallbackNotice, type PendingNotice } from "./notify";

/**
 * The in-app fallback for a notice that could not be a notification (SPEC-051).
 *
 * Permission denied is the common case, and it is permanent from inside the
 * page. A product that only ever notified through the OS would simply go silent
 * for those users, which is worse than never having offered.
 */
export function NoticeBanner() {
  const [notice, setNotice] = useState<PendingNotice | null>(null);

  useEffect(() => onFallbackNotice(setNotice), []);

  if (!notice) return null;

  return (
    <div className={`notice-banner notice-${notice.kind}`} role="status">
      <p className="notice-banner-text">
        <strong>{notice.title}</strong> {notice.body}
      </p>
      <Link to={notice.href} className="notice-banner-action" onClick={() => setNotice(null)}>
        Open it
      </Link>
      <button type="button" className="notice-banner-dismiss" onClick={() => setNotice(null)}>
        Dismiss
      </button>
    </div>
  );
}
