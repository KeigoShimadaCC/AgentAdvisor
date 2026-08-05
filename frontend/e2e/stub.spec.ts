import { test, expect } from "@playwright/test";
import { modeDescribe, apiPost, apiGet, waitForStage } from "./helpers";

// Stub-mode specs run only when E2E_MODE=stub.

/**
 * Full lifecycle through the real orchestrator on the StubBackend:
 *
 *   POST /api/cases → poll to scope checkpoint → approve →
 *   SSE shows post-gate stages → wait for delivery checkpoint →
 *   accept → case done → disk assertions.
 *
 * The StubBackend runs the full pipeline without any live model calls,
 * so the entire flow is deterministic and token-free.
 */
modeDescribe("stub", "Stub mode — full lifecycle", () => {
  test("creates a case and runs through scope → delivery → done", async ({ page }) => {
    // Navigate to the app so the API proxy is available via page.request.
    await page.goto("/");

    // 1. Create a new case via the API.
    const { status, data } = await apiPost<{ case_id: string; stage: string }>(
      page,
      "/cases",
      {
        prompt:
          "Should I invest $50k in a single semiconductor stock or a broad ETF?",
        effort: "default",
      },
    );
    // SPEC-046: creation is accepted and runs in the background.
    expect(status).toBe(202);
    const caseId = data!.case_id;
    expect(caseId).toBeTruthy();

    // 2. Poll until the case reaches the scope checkpoint.
    await waitForStage(page, caseId, "awaiting_framing_approval", 30_000);

    // 3. Approve the scope checkpoint via the API.
    const scopeResp = await apiPost<{ stage: string }>(
      page,
      `/cases/${caseId}/checkpoints/scope`,
      { decision: "approve", approved_by: "user" },
    );
    expect(scopeResp.status).toBe(200);

    // 4. Wait for the pipeline to run through to the delivery checkpoint.
    await waitForStage(page, caseId, "awaiting_final_approval", 60_000);

    // 5. Accept the delivery checkpoint.
    const deliveryResp = await apiPost<{ stage: string }>(
      page,
      `/cases/${caseId}/checkpoints/delivery`,
      { decision: "accept", approved_by: "user" },
    );
    expect(deliveryResp.status).toBe(200);

    // 6. Assert the case is done.
    await waitForStage(page, caseId, "done", 30_000);
  });

  test("framing_approval.yaml exists on disk after scope sign", async ({ page }) => {
    await page.goto("/");

    // Create and advance to scope checkpoint
    const { data } = await apiPost<{ case_id: string }>(page, "/cases", {
      prompt: "Should I buy or rent my next home?",
      effort: "default",
    });
    const caseId = data!.case_id;
    await waitForStage(page, caseId, "awaiting_framing_approval", 30_000);

    // Approve scope
    await apiPost(page, `/cases/${caseId}/checkpoints/scope`, {
      decision: "approve",
      approved_by: "user",
    });

    // Assert framing_approval.yaml exists on disk via the test hook
    const diskResp = await apiGet<{ content: string }>(
      page,
      `/_test/case-file/${caseId}?path=shared/framing_approval.yaml`,
    );
    expect(diskResp.status).toBe(200);
    expect(diskResp.data!.content).toContain("approved_by");
  });

  test("final_approval.yaml exists on disk after delivery accept", async ({ page }) => {
    await page.goto("/");

    // Create, approve scope, wait for delivery
    const { data } = await apiPost<{ case_id: string }>(page, "/cases", {
      prompt: "Should I switch jobs for a 20% raise?",
      effort: "default",
    });
    const caseId = data!.case_id;
    await waitForStage(page, caseId, "awaiting_framing_approval", 30_000);

    await apiPost(page, `/cases/${caseId}/checkpoints/scope`, {
      decision: "approve",
      approved_by: "user",
    });
    await waitForStage(page, caseId, "awaiting_final_approval", 60_000);

    // Accept delivery
    await apiPost(page, `/cases/${caseId}/checkpoints/delivery`, {
      decision: "accept",
      approved_by: "user",
    });
    await waitForStage(page, caseId, "done", 30_000);

    // Assert final_approval.yaml exists on disk
    const diskResp = await apiGet<{ content: string }>(
      page,
      `/_test/case-file/${caseId}?path=outputs/final_approval.yaml`,
    );
    expect(diskResp.status).toBe(200);
    expect(diskResp.data!.content).toContain("approved_by");
  });
});

modeDescribe("stub", "Stub mode — wrong-stage protection", () => {
  test("replaying scope checkpoint after approval returns 409", async ({ page }) => {
    await page.goto("/");

    // Create and advance to scope checkpoint
    const { data } = await apiPost<{ case_id: string }>(page, "/cases", {
      prompt: "Should I adopt a microservices architecture?",
      effort: "default",
    });
    const caseId = data!.case_id;
    await waitForStage(page, caseId, "awaiting_framing_approval", 30_000);

    // Approve scope
    await apiPost(page, `/cases/${caseId}/checkpoints/scope`, {
      decision: "approve",
      approved_by: "user",
    });

    // Wait for the case to advance past the scope checkpoint
    await page.waitForTimeout(1000);

    // Replay the scope checkpoint — should get 409 (wrong stage)
    const replayResp = await apiPost(page, `/cases/${caseId}/checkpoints/scope`, {
      decision: "approve",
      approved_by: "user",
    });
    expect(replayResp.status).toBe(409);
  });

  test("delivery accept before the case is ready returns 409", async ({ page }) => {
    await page.goto("/");

    const { data } = await apiPost<{ case_id: string }>(page, "/cases", {
      prompt: "Should I learn Rust or Go?",
      effort: "default",
    });
    const caseId = data!.case_id;
    await waitForStage(page, caseId, "awaiting_framing_approval", 30_000);

    // Try to accept delivery while still at scope checkpoint
    const resp = await apiPost(page, `/cases/${caseId}/checkpoints/delivery`, {
      decision: "accept",
      approved_by: "user",
    });
    expect(resp.status).toBe(409);
  });
});
