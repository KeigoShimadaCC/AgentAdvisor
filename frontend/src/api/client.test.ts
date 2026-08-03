import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { api, type ScopeCheckpointPayload } from "./client";

/** A minimal stub-backed service: returns canned JSON for known routes. */
function stubFetch(): typeof fetch {
  const calls: { path: string; init?: RequestInit }[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    calls.push({ path: url, init });
    const path = url.replace(/^\/api/, "");

    let body: unknown;
    let status = 200;

    if (path === "/cases" && init?.method === "POST") {
      body = { case_id: "case-stub", stage: "awaiting_framing_approval" };
      status = 201;
    } else if (path === "/cases" && init?.method === undefined) {
      body = [{ case_id: "case-stub", stage: "awaiting_framing_approval", title: "Test", updated: "2026-01-01T00:00:00" }];
    } else if (path === "/cases/case-stub/view") {
      body = { case_id: "case-stub", phase: "framing", stage: "awaiting_framing_approval", is_terminal: false, needs_you: "scope_checkpoint" };
    } else if (path === "/cases/case-stub/artifacts/intake_record") {
      body = { artifact_id: "intake_record", schema: "intake_record", data: { raw_prompt: "test" } };
    } else if (path === "/cases/case-stub/artifacts/decision_spec") {
      body = { artifact_id: "decision_spec", schema: "decision_spec", data: { decision_id: "d", question: "q", alternatives: ["a"], objectives: ["o"], deadline: "none", depth: "standard", owner: "user", reversibility: "irreversible", risk_tolerance: "low" } };
    } else if (path === "/cases/case-stub/checkpoints/scope" && init?.method === "POST") {
      const sent = JSON.parse(init.body as string) as ScopeCheckpointPayload;
      body = { case_id: "case-stub", stage: "structuring", echo: sent };
    } else {
      body = { error: "not_found", detail: `No stub for ${path}` };
      status = 404;
    }

    return {
      ok: status < 400,
      status,
      json: async () => body,
      text: async () => JSON.stringify(body),
      statusText: "OK",
    } as Response;
  });

  // Attach the calls array so tests can inspect them.
  (fn as unknown as { __calls: typeof calls }).__calls = calls;
  return fn as unknown as typeof fetch;
}

describe("api client integration (stub-backed)", () => {
  let originalFetch: typeof fetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    globalThis.fetch = stubFetch();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("createCase sends prompt + effort and returns a case id", async () => {
    const result = await api.createCase("Should I move?", "default");
    expect(result.case_id).toBe("case-stub");
    const calls = (globalThis.fetch as unknown as { __calls: { path: string; init?: RequestInit }[] }).__calls;
    const post = calls.find((c) => c.path === "/api/cases");
    expect(post).toBeDefined();
    const body = JSON.parse(post!.init!.body as string);
    expect(body.prompt).toBe("Should I move?");
    expect(body.effort).toBe("default");
  });

  it("submitScopeCheckpoint serializes the full payload", async () => {
    const payload: ScopeCheckpointPayload = {
      decision: "approve",
      confirmations: ["deadline", "risk_tolerance", "reversibility"],
      summary_hash: "deadbeef",
      approved_by: "user",
    };
    const result = await api.submitScopeCheckpoint("case-stub", payload);
    expect(result.case_id).toBe("case-stub");
    const calls = (globalThis.fetch as unknown as { __calls: { path: string; init?: RequestInit }[] }).__calls;
    const post = calls.find((c) => c.path === "/api/cases/case-stub/checkpoints/scope");
    expect(post).toBeDefined();
    const sent = JSON.parse(post!.init!.body as string) as ScopeCheckpointPayload;
    expect(sent.decision).toBe("approve");
    expect(sent.confirmations).toEqual(["deadline", "risk_tolerance", "reversibility"]);
    expect(sent.summary_hash).toBe("deadbeef");
    expect(sent.approved_by).toBe("user");
  });

  it("requestFramingRevision uses decision edit when edits are present", async () => {
    await api.requestFramingRevision("case-stub", { question: "new wording" }, {});
    const calls = (globalThis.fetch as unknown as { __calls: { path: string; init?: RequestInit }[] }).__calls;
    const post = calls.find((c) => c.path === "/api/cases/case-stub/checkpoints/scope");
    const sent = JSON.parse(post!.init!.body as string) as ScopeCheckpointPayload;
    expect(sent.decision).toBe("edit");
    expect(sent.edits).toEqual({ question: "new wording" });
  });

  it("requestFramingRevision uses answer_clarifications when only answers are present", async () => {
    await api.requestFramingRevision("case-stub", {}, { risk_tolerance: "high" });
    const calls = (globalThis.fetch as unknown as { __calls: { path: string; init?: RequestInit }[] }).__calls;
    const post = calls.find((c) => c.path === "/api/cases/case-stub/checkpoints/scope");
    const sent = JSON.parse(post!.init!.body as string) as ScopeCheckpointPayload;
    expect(sent.decision).toBe("answer_clarifications");
    expect(sent.clarification_answers).toEqual({ risk_tolerance: "high" });
  });

  it("getTypedArtifact wraps the envelope and types the data", async () => {
    const env = await api.getIntakeRecord("case-stub");
    expect(env.artifact_id).toBe("intake_record");
    expect(env.data.raw_prompt).toBe("test");
  });
});
