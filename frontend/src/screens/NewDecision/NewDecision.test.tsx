import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { NewDecision } from "./NewDecision";
import { readDraft } from "./commissionDraft";
import { readAltitude } from "../shell/altitude";
import { getPresence } from "../shell/presence";

const { mocks } = vi.hoisted(() => ({
  mocks: { createCase: vi.fn(), getEffortHistory: vi.fn() },
}));

vi.mock("../../api/client", () => ({
  api: { createCase: mocks.createCase, getEffortHistory: mocks.getEffortHistory },
}));

function renderCommission() {
  return render(
    <MemoryRouter initialEntries={["/new"]}>
      <Routes>
        <Route path="/new" element={<NewDecision />} />
        <Route path="/cases/:caseId" element={<p>Case surface</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  mocks.getEffortHistory.mockResolvedValue({
    profiles: { default: { samples: 7, p50_s: 4_200, p90_s: 12_000 } },
  });
  mocks.createCase.mockResolvedValue({ case_id: "case-9", stage: "intake" });
});

describe("starting a case", () => {
  it("goes straight to the case rather than holding the user on a spinner", async () => {
    // The old screen polled for up to thirty minutes behind a disabled button
    // reading "Framing…", with no case to open and nothing to watch.
    renderCommission();
    await userEvent.type(screen.getByLabelText("Decision prompt"), "Should we move the warehouse?");
    await userEvent.click(screen.getByRole("button", { name: "Start this case" }));

    await waitFor(() => expect(screen.getByText("Case surface")).toBeInTheDocument());
    expect(mocks.createCase).toHaveBeenCalledWith("Should we move the warehouse?", "default");
  });

  it("keeps the user on the form when creation fails, with what went wrong", async () => {
    mocks.createCase.mockRejectedValue({ error: "bad_request", detail: "That prompt is empty." });
    renderCommission();
    await userEvent.type(screen.getByLabelText("Decision prompt"), "A decision");
    await userEvent.click(screen.getByRole("button", { name: "Start this case" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("That prompt is empty.");
    expect(screen.queryByText("Case surface")).not.toBeInTheDocument();
    // And the button is usable again rather than stuck.
    expect(screen.getByRole("button", { name: "Start this case" })).toBeEnabled();
  });
});

describe("the draft", () => {
  it("survives a reload, because people spend real effort on this prompt", async () => {
    const first = renderCommission();
    await userEvent.type(screen.getByLabelText("Decision prompt"), "Half a thought");
    await userEvent.click(screen.getByRole("button", { name: /Deep dive/ }));
    first.unmount();

    renderCommission();
    expect(screen.getByLabelText("Decision prompt")).toHaveValue("Half a thought");
    expect(screen.getByRole("button", { name: /Deep dive/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("is cleared once the case exists", async () => {
    renderCommission();
    await userEvent.type(screen.getByLabelText("Decision prompt"), "A real decision");
    await userEvent.click(screen.getByRole("button", { name: "Start this case" }));
    await waitFor(() => expect(screen.getByText("Case surface")).toBeInTheDocument());
    expect(readDraft().prompt).toBe("");
  });

  it("survives corrupt storage instead of breaking the screen", () => {
    window.localStorage.setItem("agentadvisor:commission-draft", "{not json");
    renderCommission();
    expect(screen.getByLabelText("Decision prompt")).toHaveValue("");
  });
});

describe("the two routing preferences", () => {
  it("sets the reading altitude from the output shape, and writes nothing to the case", async () => {
    renderCommission();
    await userEvent.type(screen.getByLabelText("Decision prompt"), "A decision");
    await userEvent.click(screen.getByRole("button", { name: /A one-page answer/ }));
    await userEvent.click(screen.getByRole("button", { name: "Start this case" }));

    await waitFor(() => expect(readAltitude()).toBe("answer"));
    // The preference is client-side only: `createCase` takes prompt and effort.
    expect(mocks.createCase).toHaveBeenCalledWith("A decision", "default");
    expect(mocks.createCase.mock.calls[0]).toHaveLength(2);
  });

  it("lands the full-brief choice on Reasoning", async () => {
    renderCommission();
    await userEvent.type(screen.getByLabelText("Decision prompt"), "A decision");
    await userEvent.click(screen.getByRole("button", { name: /The full advisory brief/ }));
    await userEvent.click(screen.getByRole("button", { name: "Start this case" }));
    await waitFor(() => expect(readAltitude()).toBe("reasoning"));
  });

  it("records watch-or-notify for SPEC-051, per user rather than per case", async () => {
    renderCommission();
    await userEvent.type(screen.getByLabelText("Decision prompt"), "A decision");
    await userEvent.click(screen.getByRole("button", { name: /Ping me/ }));
    await userEvent.click(screen.getByRole("button", { name: "Start this case" }));
    await waitFor(() => expect(getPresence()).toBe("notify"));
  });
});

describe("effort times", () => {
  it("shows measured ranges, labelled as measured", async () => {
    renderCommission();
    expect(await screen.findByText("1h 10m–3h 20m (measured, 7 runs)")).toBeInTheDocument();
    expect(screen.getByText(/not an estimate/i)).toBeInTheDocument();
  });

  it("says nothing has been measured for a profile with no history", async () => {
    renderCommission();
    // Only `default` has history in this fixture.
    await screen.findByText(/measured, 7 runs/);
    expect(screen.getAllByText("not measured yet")).toHaveLength(2);
  });

  it("degrades honestly when the history endpoint is unreachable", async () => {
    mocks.getEffortHistory.mockRejectedValue(new Error("offline"));
    renderCommission();
    expect(await screen.findByText(/nothing honest to promise/i)).toBeInTheDocument();
    expect(screen.getAllByText("not measured yet")).toHaveLength(3);
  });
});
