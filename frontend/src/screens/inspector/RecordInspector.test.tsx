import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { InspectorHost } from "./InspectorHost";
import { RecordInspector } from "./RecordInspector";
import { CitationLink } from "./CitationLink";
import { makeEventsFixture } from "../rooms/fixtures";
import type { TranslatedEvent } from "../../api/sse";

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
  SSEClient: class {
    connect() {}
    disconnect() {}
  },
}));

const EVIDENCE_DATA = {
  artifact_id: "E-1",
  schema: "evidence_record",
  data: {
    evidence_id: "E-1",
    claim: "Revenue grew 12% YoY in Q2.",
    excerpt: "Total revenue was $1.12B, up 12% year over year.",
    publisher: "SEC filing",
    source_url: "https://example.com/filing",
    source_type: "regulatory_filing",
    reliability: "high",
    directness: "high",
    source_tier: "primary",
    limitations: "Single-quarter figure; not annualized.",
    flags: ["incentive_conflict"],
  },
};

function renderInspector(events: TranslatedEvent[] = makeEventsFixture()) {
  return render(
    <MemoryRouter initialEntries={["/cases/case-1/rooms/sources"]}>
      <InspectorHost events={events}>
        <RecordInspector
          caseId="case-1"
          artifactId="E-1"
          events={events}
          onClose={() => {}}
        />
      </InspectorHost>
    </MemoryRouter>,
  );
}

describe("RecordInspector chain view", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getArtifact.mockResolvedValue(EVIDENCE_DATA);
    mocks.getFile.mockResolvedValue("evidence_id: E-1\nclaim: Revenue grew 12% YoY in Q2.");
  });

  it("shows the claim, excerpt, grades, and limitations verbatim", async () => {
    renderInspector();
    expect(await screen.findByText("Revenue grew 12% YoY in Q2.")).toBeInTheDocument();
    expect(screen.getByText("Total revenue was $1.12B, up 12% year over year.")).toBeInTheDocument();
    // grades: Primary source × High reliability · High directness
    expect(screen.getByText("Primary source")).toBeInTheDocument();
    expect(screen.getByText("High reliability")).toBeInTheDocument();
    // limitations line.
    expect(screen.getByText("Single-quarter figure; not annualized.")).toBeInTheDocument();
  });

  it("links the source URL, which is the point of a provenance chain", async () => {
    renderInspector();
    await screen.findByText("Revenue grew 12% YoY in Q2.");

    const link = screen.getByRole("link", { name: "https://example.com/filing" });
    expect(link).toHaveAttribute("href", "https://example.com/filing");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("omits the separator when there is no source URL", async () => {
    mocks.getArtifact.mockResolvedValue({
      ...EVIDENCE_DATA,
      data: { ...EVIDENCE_DATA.data, source_url: undefined },
    });
    renderInspector();
    await screen.findByText("Revenue grew 12% YoY in Q2.");

    expect(screen.queryByRole("link", { name: /example\.com/ })).not.toBeInTheDocument();
    expect(screen.getByText("SEC filing").textContent?.trim()).toBe("SEC filing");
  });

  it("shows the raw YAML and audit slice when the machinery toggle is opened", async () => {
    renderInspector();
    await screen.findByText("Revenue grew 12% YoY in Q2.");
    fireEvent.click(screen.getByRole("button", { name: "Show the machinery" }));
    expect(await screen.findByText(/Raw artifact/)).toBeInTheDocument();
    // audit slice: events mentioning E-1 (the evidence_batch_unpacked one).
    expect(screen.getByText(/1 evidence record\(s\) gathered/)).toBeInTheDocument();
  });
});

describe("CitationLink opens the inspector", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getArtifact.mockResolvedValue(EVIDENCE_DATA);
    mocks.getFile.mockResolvedValue("raw");
  });

  it("opens the slide-over on click", async () => {
    render(
      <MemoryRouter initialEntries={["/cases/case-1/rooms/sources"]}>
        <Routes>
          <Route path="/cases/:caseId/rooms/sources" element={
            <InspectorHost events={makeEventsFixture()}>
              <CitationLink id="E-1">E-1</CitationLink>
            </InspectorHost>
          } />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Inspect record E-1" }));
    expect(await screen.findByText("Revenue grew 12% YoY in Q2.")).toBeInTheDocument();
  });
});
