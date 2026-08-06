import { useState } from "react";
import { exportMarkdown, exportFilename } from "./markdown";
import { useToast } from "../screens/shared/Toast";
import type { CaseView } from "../generated/case_view";

/**
 * Take the brief with you (SPEC-052).
 *
 * Three ways out, none of which need a server: a Markdown file, the system
 * print dialogue against a print stylesheet, and a read-only link. The link is
 * a local URL rather than a hosted document — the service binds to 127.0.0.1
 * and this spec does not change that, so "share" means "same machine, no
 * controls" and says so.
 */
export function ExportControls({ view }: { view: CaseView }) {
  const [copied, setCopied] = useState(false);
  const toast = useToast();

  function download() {
    const blob = new Blob([exportMarkdown(view)], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = exportFilename(view);
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    toast.show(`Downloaded ${exportFilename(view)}.`, "success");
  }

  async function copyShareLink() {
    const url = `${window.location.origin}/share/${view.case_id}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      toast.show("Read-only link copied.", "success");
      setTimeout(() => setCopied(false), 3000);
    } catch {
      // A blocked clipboard is not a failure worth a red banner; show the URL
      // so the user can copy it themselves.
      toast.show(url, "info");
    }
  }

  return (
    <div className="export-controls" role="group" aria-label="Take this with you">
      <button type="button" className="secondary-action" onClick={download}>
        Download as Markdown
      </button>
      <button type="button" className="secondary-action" onClick={() => window.print()}>
        Print or save as PDF
      </button>
      <button type="button" className="secondary-action" onClick={copyShareLink}>
        {copied ? "Link copied" : "Copy read-only link"}
      </button>
      <p className="export-note">
        The link works on this machine only — the service is local, and the shared view has no
        controls on it.
      </p>
    </div>
  );
}
