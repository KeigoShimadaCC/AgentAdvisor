import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LiveActivity } from "./LiveActivity";
import type { TranslatedEvent } from "../../api/sse";

function makeEvent(
  event_type: string,
  payload: Record<string, unknown>,
  opts: { ts?: string; actor?: string; line_cursor?: number } = {},
): TranslatedEvent {
  return {
    event_type,
    message: "test",
    technical: false,
    raw_payload: payload,
    line_cursor: opts.line_cursor ?? 0,
    ts: opts.ts ?? null,
    actor: opts.actor ?? null,
  };
}

describe("LiveActivity", () => {
  it("renders nothing when there are no events", () => {
    const { container } = render(<LiveActivity events={[]} />);
    expect(container.querySelector(".live-activity")).toBeNull();
  });

  it("shows a running indicator when the latest attempt is not ok", () => {
    const events: TranslatedEvent[] = [
      makeEvent("role_invocation_attempt", { attempt: 1, status: "validation_failure" }, {
        actor: "synthesizer",
        ts: new Date().toISOString(),
        line_cursor: 5,
      }),
    ];
    render(<LiveActivity events={events} />);
    expect(screen.getByText("Synthesis")).toBeInTheDocument();
    expect(screen.getByText("attempt 1")).toBeInTheDocument();
    expect(screen.getByText(/running|retrying/)).toBeInTheDocument();
    // The card should have the "running" class (pulsing dot).
    const card = document.querySelector(".live-activity-card");
    expect(card?.classList.contains("running")).toBe(true);
  });

  it("shows completed status when the latest attempt succeeded", () => {
    const events: TranslatedEvent[] = [
      makeEvent("role_invocation_attempt", { attempt: 1, status: "ok" }, {
        actor: "researcher",
        ts: new Date().toISOString(),
        line_cursor: 5,
      }),
    ];
    render(<LiveActivity events={events} />);
    expect(screen.getByText("Research")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("shows idle when a stage_completed event came after the attempt", () => {
    const events: TranslatedEvent[] = [
      makeEvent("role_invocation_attempt", { attempt: 1, status: "ok" }, {
        actor: "researcher",
        line_cursor: 3,
      }),
      makeEvent("stage_completed", { stage: "investigation" }, { line_cursor: 5 }),
    ];
    render(<LiveActivity events={events} />);
    // The card should not be in "running" state.
    const card = document.querySelector(".live-activity-card");
    expect(card?.classList.contains("running")).toBe(false);
  });
});
