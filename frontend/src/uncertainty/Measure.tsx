import { encodingClass, type Encoding, type Scale } from "./language";
import { NOT_ASSESSED_MARK } from "../copy/uncertainty";

/**
 * One measure, in the one idiom its kind gets (SPEC-054).
 *
 * Three scales of the same encoding, never three encodings:
 *
 *  - **inline** — a chip beside a claim or a citation;
 *  - **summary** — the compact form on the answer and on library cards;
 *  - **full** — the labelled form with its basis, on delivery.
 *
 * A reader who learns what a band means on the answer knows what it means in a
 * room, which is the entire point of having a grammar rather than five
 * components that each solved their own corner.
 */
export function Measure({
  encoding,
  scale = "full",
  label,
}: {
  encoding: Encoding;
  scale?: Scale;
  label?: string;
}) {
  const className = `${encodingClass(encoding, scale)}${label ? " u-labelled" : ""}`;

  return (
    <div className={className}>
      {label && <span className="u-label">{label}</span>}
      <Body encoding={encoding} scale={scale} />
    </div>
  );
}

function Body({ encoding, scale }: { encoding: Encoding; scale: Scale }) {
  switch (encoding.kind) {
    case "not_assessed":
      // Explicit, always. Never a zero, never an empty state, never a low value:
      // "not assessed" and "assessed as low" are different facts and a reader
      // acts differently on each.
      return (
        <>
          <span className="not-assessed-stamp">{NOT_ASSESSED_MARK} Not assessed</span>
          {scale !== "inline" && <span className="not-assessed-reason">{encoding.reason}</span>}
        </>
      );

    case "band":
      return (
        <>
          <span className="confidence-band-label">{encoding.label}</span>
          {scale !== "inline" && (
            <span
              className="u-band-steps"
              role="img"
              aria-label={`${encoding.label}, step ${encoding.total - encoding.index} of ${encoding.total}`}
            >
              {Array.from({ length: encoding.total }, (_, i) => (
                <span
                  key={i}
                  className={`u-band-step${i === encoding.index ? " selected" : ""}`}
                  aria-hidden="true"
                />
              ))}
            </span>
          )}
          {scale === "full" && encoding.basis && (
            <span className="confidence-basis">{encoding.basis}</span>
          )}
        </>
      );

    case "grade":
      return (
        <>
          <span className="source-strength-grade">{encoding.letter}</span>
          {scale !== "inline" && <span className="u-grade-meaning">{encoding.meaning}</span>}
          {scale === "full" && encoding.basis && (
            <span className="source-strength-basis">{encoding.basis}</span>
          )}
        </>
      );

    case "countable":
      return (
        <>
          {/* Marks a reader can literally count. A percentage here would invite
              comparison with the other three measures, which is the collapse
              the four separate encodings exist to prevent. */}
          <span
            className="countable-dots"
            role="img"
            aria-label={encoding.caption}
          >
            {Array.from({ length: encoding.total }, (_, i) => (
              <span
                key={i}
                className={`u-dot${i < encoding.filled ? " filled" : ""}`}
                aria-hidden="true"
              />
            ))}
          </span>
          {scale !== "inline" && (
            <span className="stability-dots-caption">{encoding.caption}</span>
          )}
        </>
      );

    case "range": {
      const hasInterval = encoding.low != null || encoding.high != null;
      return (
        <>
          {/* Point and interval look different because they *are* different
              claims: an interval is the statement that the point is not known. */}
          {encoding.point != null && (
            <span className="u-point probability-band-phrase">
              {encoding.phrase}
              <span className="u-point-value">{Math.round(encoding.point * 100)}%</span>
            </span>
          )}
          {hasInterval && (
            <span className="u-interval probability-band-range">
              {encoding.low != null ? `${Math.round(encoding.low * 100)}%` : "—"}
              <span className="u-interval-bar" aria-hidden="true" />
              {encoding.high != null ? `${Math.round(encoding.high * 100)}%` : "—"}
            </span>
          )}
          {scale === "full" && encoding.method && (
            <span className="u-method">{encoding.method.replace(/_/g, " ")}</span>
          )}
        </>
      );
    }
  }
}
