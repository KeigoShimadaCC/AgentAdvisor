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

modeDescribe("stub", "Stub mode — disclosure must not change the record (SPEC-050)", () => {
  /**
   * The load-bearing property of the scope sheet's progressive disclosure.
   *
   * If signing immediately and signing after expanding "Adjust scope" produced
   * different artifacts, the UI would have quietly introduced two classes of
   * approval, and the audit trail would stop meaning one thing. Nobody would
   * notice from reading the code — the two paths run the same handler — which
   * is exactly why it is asserted against what lands on disk.
   */
  async function signScope(page: import("@playwright/test").Page, prompt: string, expand: boolean) {
    const { data } = await apiPost<{ case_id: string }>(page, "/cases", {
      prompt,
      effort: "default",
    });
    const caseId = data!.case_id;
    await waitForStage(page, caseId, "awaiting_framing_approval", 30_000);

    await page.goto(`/cases/${caseId}/scope`);
    await page.locator(".scope-lead").waitFor({ state: "visible" });

    if (expand) {
      await page.locator(".scope-adjust > summary").click();
      await expect(page.locator(".scope-adjust")).toHaveAttribute("open", "");
      // Every collapsed section is now on screen and has been read.
      await expect(page.locator(".options-list")).toBeVisible();
      await expect(page.locator(".outline-list")).toBeVisible();
    } else {
      await expect(page.locator(".scope-adjust")).not.toHaveAttribute("open", "");
    }

    // Ground rules are outside the disclosure precisely because confirming them
    // is required, so both paths do exactly this and nothing more.
    const boxes = page.locator(".ground-rule-confirm input[type=checkbox]");
    const count = await boxes.count();
    for (let i = 0; i < count; i++) await boxes.nth(i).check();

    await page.getByRole("button", { name: /Sign|Approve/ }).first().click();

    // Poll for the artifact rather than for a stage: the stub pipeline runs
    // fast enough that it can pass through several stages before the first
    // poll, and waiting on one that has already gone by costs a full timeout
    // for no signal.
    const deadline = Date.now() + 30_000;
    let resp = await apiGet<{ content: string }>(
      page,
      `/_test/case-file/${caseId}?path=shared/framing_approval.yaml`,
    );
    while (resp.status !== 200 && Date.now() < deadline) {
      await page.waitForTimeout(250);
      resp = await apiGet<{ content: string }>(
        page,
        `/_test/case-file/${caseId}?path=shared/framing_approval.yaml`,
      );
    }
    expect(resp.status, "framing_approval.yaml was not written").toBe(200);
    return { caseId, content: resp.data!.content };
  }

  /** Strip what legitimately differs between two runs: identity and clock. */
  function normalise(content: string, caseId: string): string {
    return content
      .split("\n")
      .filter((line) => !/^(approved_at|case_id|artifact_id|schema_version):/.test(line))
      .join("\n")
      .replaceAll(caseId, "<case>")
      .replace(/\d{4}-\d{2}-\d{2}T[\d:.]+Z?/g, "<ts>");
  }

  test("signing fast and signing after expanding write the same approval", async ({ page }) => {
    test.setTimeout(180_000);
    await page.goto("/");

    const prompt = "Should I invest $50k in a single semiconductor stock or a broad ETF?";
    const fast = await signScope(page, prompt, false);
    const full = await signScope(page, prompt, true);

    const normalised = normalise(fast.content, fast.caseId);

    // Guard against a vacuous pass. `framing_approval.yaml` is a short record —
    // decision, who, edits, clarification answers — so a length check alone is
    // weak. Name the three fields that would actually move if opening a
    // disclosure leaked into the signed record, and assert they are present
    // before comparing them.
    for (const field of ["decision:", "approved_by:", "edits:", "clarification_answers:"]) {
      expect(normalised, `normalise() removed ${field} — the comparison would be vacuous`).toContain(
        field,
      );
    }
    // A clean sign records no edits by either path; an expanded sign that
    // silently captured field state would show them here.
    expect(normalised).toContain("edits: {}");
    expect(normalised).toContain("clarification_answers: {}");

    expect(
      normalised,
      "expanding the disclosure changed the signed record",
    ).toBe(normalise(full.content, full.caseId));
  });
});
