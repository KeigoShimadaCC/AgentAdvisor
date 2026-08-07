import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Calibration } from "./Calibration";
import { OutcomePrompt } from "./OutcomePrompt";
import { ToastHost } from "../shared/Toast";

const { mocks } = vi.hoisted(() => ({
  mocks: { getCalibration: vi.fn(), recordOutcome: vi.fn() },
}));

vi.mock("../../api/client", () => ({
  api: { getCalibration: mocks.getCalibration, recordOutcome: mocks.recordOutcome },
}));

function renderScreen() {
  return render(
    <MemoryRouter>
      <Calibration />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.recordOutcome.mockResolvedValue({ case_id: "case-1", recorded: true });
});

describe("the calibration screen", () => {
  it("renders the module's interpretation verbatim", async () => {
    // The honesty is in the wording. Reformatting it is how a UI undoes the
    // property the module was written to protect.
    const interpretation =
      "Brier score 0.18 over 12 outcomes; mean forecast and mean realized rate are close.";
    mocks.getCalibration.mockResolvedValue({
      sample_size: 12,
      brier_score: 0.18,
      mean_forecast: 0.62,
      mean_realized: 0.58,
      interpretation,
    });
    renderScreen();
    expect(await screen.findByText(interpretation)).toBeInTheDocument();
  });

  it("shows the score once there are enough outcomes for it to mean something", async () => {
    mocks.getCalibration.mockResolvedValue({
      sample_size: 12,
      brier_score: 0.18,
      mean_forecast: 0.62,
      mean_realized: 0.58,
      interpretation: "Brier score 0.18 over 12 outcomes.",
    });
    renderScreen();
    expect(await screen.findByText("0.180")).toBeInTheDocument();
    expect(screen.getByText("62%")).toBeInTheDocument();
    expect(screen.getByText("58%")).toBeInTheDocument();
  });

  it("withholds the score under five outcomes, and says why", async () => {
    // The module calls this noise. A screen that rendered it as a headline
    // would be presenting noise as a measurement.
    mocks.getCalibration.mockResolvedValue({
      sample_size: 2,
      brier_score: 0.31,
      mean_forecast: 0.7,
      mean_realized: 0.5,
      interpretation: "Brier score 0.31 over only 2 outcome(s); this is noise, not a calibration estimate.",
    });
    renderScreen();
    expect(await screen.findByText(/this is noise, not a calibration estimate/)).toBeInTheDocument();
    expect(screen.queryByText("0.310")).not.toBeInTheDocument();
    expect(screen.getByText(/withheld until there are 5 recorded outcomes/i)).toBeInTheDocument();
    // The sample size itself is still shown: it is the reason, not the secret.
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("says the record is empty rather than showing a zero score", async () => {
    mocks.getCalibration.mockResolvedValue({
      sample_size: 0,
      brier_score: null,
      mean_forecast: null,
      mean_realized: null,
      interpretation: "No outcomes recorded yet, so the system's calibration is unknown.",
    });
    renderScreen();
    expect(await screen.findByText(/calibration is unknown/)).toBeInTheDocument();
    expect(screen.queryByText("0.000")).not.toBeInTheDocument();
  });

  it("reports a failed read instead of rendering an empty record as a good one", async () => {
    mocks.getCalibration.mockRejectedValue({ detail: "memory root unreadable" });
    renderScreen();
    expect(await screen.findByRole("alert")).toHaveTextContent("memory root unreadable");
  });
});

describe("recording what happened", () => {
  function renderPrompt() {
    return render(
      <ToastHost>
        <OutcomePrompt caseId="case-1" />
      </ToastHost>,
    );
  }

  it("asks two separate questions, because they are two separate facts", async () => {
    renderPrompt();
    await userEvent.click(screen.getByRole("button", { name: "Record what happened" }));
    // A recommendation that was right but not followed is not a failed forecast.
    expect(screen.getByLabelText(/I followed the recommendation/)).toBeInTheDocument();
    expect(screen.getByLabelText(/The forecast outcome actually happened/)).toBeInTheDocument();
  });

  it("posts both facts and confirms", async () => {
    renderPrompt();
    await userEvent.click(screen.getByRole("button", { name: "Record what happened" }));
    await userEvent.type(screen.getByLabelText("What happened?"), "Took the term sheet, it worked.");
    await userEvent.click(screen.getByLabelText(/The forecast outcome actually happened/));
    await userEvent.click(screen.getByRole("button", { name: "Record this outcome" }));

    await waitFor(() =>
      expect(mocks.recordOutcome).toHaveBeenCalledWith("case-1", {
        summary: "Took the term sheet, it worked.",
        followed: true,
        realized: false,
      }),
    );
    expect(await screen.findByText(/counts towards the system's calibration/i)).toBeInTheDocument();
  });

  it("will not post an empty outcome", async () => {
    renderPrompt();
    await userEvent.click(screen.getByRole("button", { name: "Record what happened" }));
    expect(screen.getByRole("button", { name: "Record this outcome" })).toBeDisabled();
  });

  it("says so when recording fails, rather than pretending it landed", async () => {
    mocks.recordOutcome.mockRejectedValue({ detail: "Case is not done." });
    renderPrompt();
    await userEvent.click(screen.getByRole("button", { name: "Record what happened" }));
    await userEvent.type(screen.getByLabelText("What happened?"), "Something");
    await userEvent.click(screen.getByRole("button", { name: "Record this outcome" }));

    expect(await screen.findByText("Case is not done.")).toBeInTheDocument();
    expect(screen.queryByText(/counts towards/i)).not.toBeInTheDocument();
  });
});
