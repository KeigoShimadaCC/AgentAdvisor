import type { CaseView } from "../generated/case_view";

export interface CaseSummary {
  case_id: string;
  stage: string;
  title: string;
  updated: string;
}

export interface ErrorResponse {
  error: string;
  detail: string;
  case_stage?: string | null;
}

const API_BASE = "/api";

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ error: "request_failed", detail: resp.statusText }));
    throw body as ErrorResponse;
  }
  return resp.json() as Promise<T>;
}

export const api = {
  listCases: () => fetchJSON<CaseSummary[]>("/cases"),

  getCaseView: (caseId: string) =>
    fetchJSON<CaseView>(`/cases/${encodeURIComponent(caseId)}/view`),

  getArtifact: (caseId: string, artifactId: string) =>
    fetchJSON<{ artifact_id: string; schema: string; data: unknown }>(
      `/cases/${encodeURIComponent(caseId)}/artifacts/${encodeURIComponent(artifactId)}`,
    ),

  getFile: async (caseId: string, filePath: string): Promise<string> => {
    const resp = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/files/${encodeURIComponent(filePath)}`);
    if (!resp.ok) throw await resp.json().catch(() => ({ error: "request_failed", detail: resp.statusText }));
    return resp.text();
  },

  createCase: (prompt: string, effort: string = "default", slug?: string) =>
    fetchJSON<{ case_id: string; stage: string }>("/cases", {
      method: "POST",
      body: JSON.stringify({ prompt, effort, slug }),
    }),

  approveScope: (caseId: string) =>
    fetchJSON<{ case_id: string; stage: string | null }>(
      `/cases/${encodeURIComponent(caseId)}/checkpoints/scope`,
      { method: "POST", body: JSON.stringify({ decision: "approve" }) },
    ),

  approveDelivery: (caseId: string) =>
    fetchJSON<{ case_id: string; stage: string | null }>(
      `/cases/${encodeURIComponent(caseId)}/checkpoints/delivery`,
      { method: "POST", body: JSON.stringify({ decision: "accept" }) },
    ),

  pauseCase: (caseId: string) =>
    fetchJSON<{ case_id: string; paused: boolean }>(
      `/cases/${encodeURIComponent(caseId)}/pause`,
      { method: "POST" },
    ),

  resumeCase: (caseId: string) =>
    fetchJSON<{ case_id: string; stage: string | null }>(
      `/cases/${encodeURIComponent(caseId)}/resume`,
      { method: "POST" },
    ),
};
