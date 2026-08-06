import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { InspectorHost } from "./InspectorHost";
import { CitationText } from "./CitationText";
import { makeEventsFixture } from "../rooms/fixtures";

const { mocks } = vi.hoisted(() => ({
  mocks: {
    getArtifact: vi.fn(),
    getFile: vi.fn(),
  },
}));

vi.mock("../../api/client", () => ({
  api: {
    getArtifact: mocks.getArtifact,
    getFile: mocks.getFile,
  },
}));

vi.mock("../../api/sse", () => ({
  readStoredCursor: () => 0,
  hasStoredCursor: () => false,
  SSEClient: class {
    connect() {}
    disconnect() {}
  },
}));

const EVIDENCE_DATA = {
  artifact_id: "E-015",
  schema: "evidence_record",
  data: {
    evidence_id: "E-015",
    claim: "H-1B is the dominant visa at Databricks.",
    excerpt: "260 of 267 sponsored workers held H-1B.",
    publisher: "USCIS data",
    source_tier: "primary",
    reliability: "high",
    directness: "high",
  },
};

function renderWithInspector(text: string) {
  return render(
    <MemoryRouter initialEntries={["/cases/case-1/brief"]}>
      <Routes>
        <Route
          path="/cases/:caseId/brief"
          element={
            <InspectorHost events={makeEventsFixture()}>
              <p>
                <CitationText>{text}</CitationText>
              </p>
            </InspectorHost>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("CitationText", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getArtifact.mockResolvedValue(EVIDENCE_DATA);
    mocks.getFile.mockResolvedValue("raw");
  });

  it("renders plain text without citations untouched", () => {
    renderWithInspector("No citations here, just prose.");
    expect(screen.getByText("No citations here, just prose.")).toBeInTheDocument();
  });

  it("turns a single [E-015] into a clickable citation link", () => {
    renderWithInspector("H-1B is dominant [E-015] at Databricks.");
    const link = screen.getByRole("button", { name: "Inspect record E-015" });
    expect(link).toBeInTheDocument();
    // Surrounding text is preserved.
    expect(screen.getByText(/H-1B is dominant/)).toBeInTheDocument();
    expect(screen.getByText(/at Databricks\./)).toBeInTheDocument();
  });

  it("handles multiple comma-separated IDs in one bracket group", () => {
    renderWithInspector("Lottery favors higher wages [E-008, E-017].");
    expect(screen.getByRole("button", { name: "Inspect record E-008" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Inspect record E-017" })).toBeInTheDocument();
  });

  it("handles multiple separate bracket groups in one string", () => {
    renderWithInspector("First [E-015] then [A-003] and again [E-008].");
    expect(screen.getByRole("button", { name: "Inspect record E-015" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Inspect record A-003" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Inspect record E-008" })).toBeInTheDocument();
  });

  it("opens the inspector when a citation link is clicked", async () => {
    renderWithInspector("H-1B is dominant [E-015] at Databricks.");
    fireEvent.click(screen.getByRole("button", { name: "Inspect record E-015" }));
    expect(await screen.findByText("H-1B is the dominant visa at Databricks.")).toBeInTheDocument();
  });
});
