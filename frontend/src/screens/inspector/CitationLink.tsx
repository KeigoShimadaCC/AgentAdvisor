import { useInspector } from "./inspectorContext";

interface CitationLinkProps {
  /** Artifact id (E-1, A-2, etc.). */
  id: string;
  /** Optional display text; defaults to the id. */
  children?: React.ReactNode;
}

/**
 * Inline citation that opens the record inspector on click.
 *
 * Keyboard-accessible (a real button) so the chain is operable without a mouse.
 */
export function CitationLink({ id, children }: CitationLinkProps) {
  const inspector = useInspector();
  return (
    <button
      type="button"
      className="citation-link"
      onClick={() => inspector.open(id)}
      aria-label={`Inspect record ${id}`}
    >
      {children ?? id}
    </button>
  );
}
