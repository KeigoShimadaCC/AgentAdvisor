import type { CaseView } from "../generated/case_view";
import type { IntakeRecord } from "../generated/intake_record";
import type { DecisionSpec } from "../generated/decision_spec";
import type { FramingApproval } from "../generated/framing_approval";
import type { FinalRecommendation } from "../generated/final_recommendation";

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

/** Payload for the scope-checkpoint POST (SPEC-034). */
export interface ScopeCheckpointPayload {
  decision: "approve" | "edit" | "answer_clarifications";
  edits?: Record<string, unknown>;
  clarification_answers?: Record<string, string>;
  confirmations?: string[];
  summary_hash?: string;
  approved_by?: string;
}

export interface ScopeCheckpointResponse {
  case_id: string;
  stage: string | null;
}

/** Typed wrapper around the generic artifact endpoint. */
export interface ArtifactEnvelope<T> {
  artifact_id: string;
  schema: string;
  data: T;
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

  /** Fetch and type a known artifact (e.g. intake_record, decision_spec). */
  getTypedArtifact: async <T>(caseId: string, artifactId: string): Promise<ArtifactEnvelope<T>> => {
    const raw = await api.getArtifact(caseId, artifactId);
    return raw as ArtifactEnvelope<T>;
  },

  /** Convenience: load the IntakeRecord for a case. */
  getIntakeRecord: (caseId: string) =>
    api.getTypedArtifact<IntakeRecord>(caseId, "intake_record"),

  /** Convenience: load the DecisionSpec (framing output) for a case. */
  getDecisionSpec: (caseId: string) =>
    api.getTypedArtifact<DecisionSpec>(caseId, "decision_spec"),

  /** Convenience: load the most recent FramingApproval for a case. */
  getFramingApproval: (caseId: string) =>
    api.getTypedArtifact<FramingApproval>(caseId, "framing_approval"),

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

  /** Submit the full scope-checkpoint payload (SPEC-034). */
  submitScopeCheckpoint: (caseId: string, payload: ScopeCheckpointPayload) =>
    fetchJSON<ScopeCheckpointResponse>(
      `/cases/${encodeURIComponent(caseId)}/checkpoints/scope`,
      { method: "POST", body: JSON.stringify(payload) },
    ),

  approveScope: (caseId: string) =>
    api.submitScopeCheckpoint(caseId, { decision: "approve" }),

  /** Request a framing revision with edits / clarification answers. */
  requestFramingRevision: (
    caseId: string,
    edits: Record<string, unknown>,
    clarificationAnswers: Record<string, string>,
  ) => {
    const decision = Object.keys(edits).length > 0 ? "edit" : "answer_clarifications";
    return api.submitScopeCheckpoint(caseId, {
      decision,
      edits,
      clarification_answers: clarificationAnswers,
    });
  },

  /** Approve the final recommendation and write a FinalApproval artifact. */
  approveDelivery: (caseId: string, approvedBy: string = "user") =>
    fetchJSON<{ case_id: string; stage: string | null }>(
      `/cases/${encodeURIComponent(caseId)}/checkpoints/delivery`,
      { method: "POST", body: JSON.stringify({ decision: "accept", approved_by: approvedBy }) },
    ),

  /** Request a final delivery revision with a note (SPEC-035). */
  requestFinalRevision: (caseId: string, note: string) =>
    fetchJSON<{ case_id: string; stage: string | null }>(
      `/cases/${encodeURIComponent(caseId)}/checkpoints/delivery`,
      { method: "POST", body: JSON.stringify({ decision: "revise", note, approved_by: "user" }) },
    ),

  /** Convenience: load the FinalRecommendation for a case. */
  getFinalRecommendation: (caseId: string) =>
    api.getTypedArtifact<FinalRecommendation>(caseId, "final_recommendation"),

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
