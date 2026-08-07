import { useId, useRef, useState, type ReactNode } from "react";
import { CitationLink } from "../screens/inspector/CitationLink";

interface WhyProps {
  /** What this supports, for the accessible name: "why 62%", "why this assumption". */
  subject: string;
  citations?: string[];
  /** `ProbabilityView.adjustments` — how an estimate moved and why. */
  adjustments?: Record<string, unknown>[];
  /** Anything else worth showing inline: an assumption's claim, an option's rationale. */
  children?: ReactNode;
}

/**
 * Expand in place (SPEC-054).
 *
 * The review's finding was that depth by navigation costs the reader their
 * place in the argument. The inspector proved the panel pattern for whole
 * records; this is the same gesture at the granularity of a sentence — the
 * support for one claim, one number, one assumption, revealed without leaving
 * the paragraph it sits in.
 *
 * Focus returns to the trigger on collapse, because a reader who opens support
 * for a mid-paragraph claim and is then dropped at the top of the document has
 * lost exactly the place this exists to keep.
 */
export function Why({ subject, citations = [], adjustments = [], children }: WhyProps) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const panelId = useId();

  const hasSomething = citations.length > 0 || adjustments.length > 0 || children != null;
  // Nothing to show is not a disclosure with an empty body — it is no control.
  if (!hasSomething) return null;

  function toggle() {
    setOpen((wasOpen) => {
      if (wasOpen) trigger.current?.focus();
      return !wasOpen;
    });
  }

  return (
    <span className="why">
      <button
        type="button"
        ref={trigger}
        className="why-toggle"
        aria-expanded={open}
        aria-controls={panelId}
        // An explicit label rather than visible text plus an sr-only span:
        // composing the name from two nodes produced "Why?for this claim",
        // which a screen reader says as one word.
        aria-label={open ? `Hide support for ${subject}` : `Why? for ${subject}`}
        onClick={toggle}
      >
        {open ? "Hide support" : "Why?"}
      </button>

      {open && (
        <span className="why-body" id={panelId}>
          {children && <span className="why-detail">{children}</span>}

          {citations.length > 0 && (
            <span className="why-citations">
              <span className="why-label">Rests on</span>
              {citations.map((id) => (
                <CitationLink key={id} id={id} />
              ))}
            </span>
          )}

          {adjustments.length > 0 && (
            <span className="why-adjustments">
              <span className="why-label">Adjusted</span>
              <ul>
                {adjustments.map((adjustment, i) => (
                  <li key={i}>
                    {String(adjustment["reason"] ?? adjustment["note"] ?? "adjustment")}
                    {adjustment["delta"] != null && (
                      <span className="why-delta">
                        {" "}
                        ({Number(adjustment["delta"]) > 0 ? "+" : ""}
                        {Math.round(Number(adjustment["delta"]) * 100)} points)
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </span>
          )}
        </span>
      )}
    </span>
  );
}
