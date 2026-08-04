import { type ReactNode } from "react";
import { CitationLink } from "./CitationLink";

/**
 * Matches bracketed citation groups like ``[E-015]``, ``[A-003, E-008]``,
 * ``[E-008] [E-017]``, or ``[O-001]`` anywhere in prose text.
 *
 * Capture group 1 is the full inner content (e.g. ``E-008, E-017``).
 * Individual IDs are extracted from the inner content separately.
 */
const CITATION_GROUP_RE = /\[((?:[EAO]-\d+\s*,?\s*)+)\]/g;
const SINGLE_ID_RE = /[EAO]-\d+/g;

/**
 * Render a prose string with inline ``[E-NNN]`` / ``[A-NNN]`` / ``[O-NNN]``
 * citation references turned into clickable {@link CitationLink} components.
 *
 * Each bracket group may contain one or more comma-separated IDs, e.g.
 * ``[A-003, E-008]``. Non-citation text is preserved verbatim.
 *
 * Must be rendered inside an ``<InspectorHost>`` so the links can open the
 * record inspector slide-over.
 */
export function CitationText({ children }: { children: string }): ReactNode {
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  // Reset the global regex state (it's module-level).
  CITATION_GROUP_RE.lastIndex = 0;

  while ((match = CITATION_GROUP_RE.exec(children)) !== null) {
    // Push the text before this citation group.
    if (match.index > lastIndex) {
      parts.push(children.slice(lastIndex, match.index));
    }

    // Extract individual IDs from the group content.
    const inner = match[1];
    const ids: string[] = [];
    SINGLE_ID_RE.lastIndex = 0;
    let idMatch: RegExpExecArray | null;
    while ((idMatch = SINGLE_ID_RE.exec(inner)) !== null) {
      ids.push(idMatch[0]);
    }

    // Render each ID as a citation link, comma-separated to match the source.
    for (let i = 0; i < ids.length; i++) {
      if (i > 0) parts.push(", ");
      parts.push(
        <CitationLink key={`cite-${key}-${ids[i]}`} id={ids[i]}>
          {ids[i]}
        </CitationLink>,
      );
    }

    lastIndex = CITATION_GROUP_RE.lastIndex;
    key++;
  }

  // Push any trailing text.
  if (lastIndex < children.length) {
    parts.push(children.slice(lastIndex));
  }

  // If no citations were found, return the original string untouched.
  if (parts.length === 0) return children;

  return parts;
}
