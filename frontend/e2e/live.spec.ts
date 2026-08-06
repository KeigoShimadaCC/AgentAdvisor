import { execFileSync } from "node:child_process";
import { test, expect } from "@playwright/test";
import { apiPost, apiGet, waitForStage } from "./helpers";

// ── Live mode ────────────────────────────────────────────────────────────────
//
// SPEC-037's opt-in live smoke: one small-budget decision through the REAL
// agent backend — commission → scope sheet with real intake output → sign →
// observe the run through `structuring` completing → pause → disk assertions.
//
// Deliberately excluded from every default run. It requires all of:
//
//   E2E_MODE=live                    (the live webServer stack, temp cases root)
//   E2E_LIVE=1                       (consent #1: spend real model usage)
//   AGENTADVISOR_E2E_BUDGET_ACK=1    (consent #2: budget acknowledged)
//
// plus an authenticated agent CLI. When any precondition is absent the spec
// reports skipped and the suite passes — it never fails closed.
//
// Cost expectation: a handful of invocations (intake, framing, structuring)
// against the SPEC-029 small profile; hard wall 20 minutes. The case directory
// lands in frontend/e2e/.tmp/cases-live/, never in cases/, and stays on disk
// for inspection afterwards.

const E2E_MODE = process.env.E2E_MODE ?? "fixture";
const CONSENTED =
  process.env.E2E_LIVE === "1" && process.env.AGENTADVISOR_E2E_BUDGET_ACK === "1";

const HARD_WALL_MS = 20 * 60 * 1000;

/**
 * Preflight: the configured backend's CLI is present and authenticated.
 * Mirrors scripts/smoke_cursor_cli.py::check_auth for cursor; for droid a
 * version probe is the available check (auth failures there surface as
 * invocation errors, which this smoke would then report honestly).
 */
function backendCliAuthenticated(): boolean {
  const backend = process.env.AGENTADVISOR_BACKEND ?? "cursor";
  try {
    if (backend === "droid") {
      execFileSync("droid", ["--version"], {
        encoding: "utf-8",
        timeout: 30_000,
        stdio: ["ignore", "pipe", "pipe"],
      });
      return true;
    }
    const output = execFileSync("cursor-agent", ["status"], {
      encoding: "utf-8",
      timeout: 30_000,
      stdio: ["ignore", "pipe", "pipe"],
    }).toLowerCase();
    const positive = ["logged in", "authenticated", "auth: yes", "auth yes", "signed in"].some(
      (s) => output.includes(s),
    );
    const negative = ["not logged", "logged out", "unauthenticated", "auth: no", "auth no"].some(
      (s) => output.includes(s),
    );
    return positive && !negative;
  } catch {
    return false;
  }
}

test.describe("Live mode — real backend smoke @live", () => {
  test.skip(
    E2E_MODE !== "live" || !CONSENTED,
    "live smoke requires E2E_MODE=live, E2E_LIVE=1 and AGENTADVISOR_E2E_BUDGET_ACK=1",
  );

  test.beforeEach(() => {
    test.skip(
      !backendCliAuthenticated(),
      "skipped: preconditions (agent CLI missing or not authenticated)",
    );
  });

  test("commissions a small-budget decision and observes it through structuring", async ({
    page,
  }) => {
    test.setTimeout(HARD_WALL_MS);
    await page.goto("/");

    // Commission through the real backend on the SPEC-029 small profile.
    const { status, data } = await apiPost<{ case_id: string }>(page, "/cases", {
      prompt:
        "Should I replace my three-year-old phone now for $900, or wait for " +
        "next year's model at a similar price?",
      effort: "small",
    });
    expect(status).toBe(201);
    const caseId = data!.case_id;
    expect(caseId).toBeTruthy();

    // The scope sheet renders real intake output (no fixture text exists in
    // live mode — this content came from the actual intake/framing roles).
    await waitForStage(page, caseId, "awaiting_framing_approval", 10 * 60 * 1000);
    await page.goto(`/cases/${caseId}/scope`);
    await expect(
      page.locator("h2", { hasText: "Here is what I understood" }),
    ).toBeVisible();

    // Sign the scope sheet.
    const scopeResp = await apiPost(page, `/cases/${caseId}/checkpoints/scope`, {
      decision: "approve",
      approved_by: "user",
    });
    expect(scopeResp.status).toBe(200);

    // Observe the run through `structuring` completing. The audit log is the
    // truth: poll it for the stage_completed event rather than racing the
    // stage field on the view endpoint.
    const deadline = Date.now() + 8 * 60 * 1000;
    let audit = "";
    while (Date.now() < deadline) {
      const resp = await apiGet<{ content: string }>(
        page,
        `/_test/case-file/${caseId}?path=audit.jsonl`,
      );
      if (resp.status === 200) {
        audit = resp.data!.content;
        const completedStructuring = audit
          .split("\n")
          .some(
            (line) =>
              line.includes('"stage_completed"') && line.includes('"structuring"'),
          );
        if (completedStructuring) break;
      }
      await page.waitForTimeout(5_000);
    }
    expect(
      audit.split("\n").some(
        (line) => line.includes('"stage_completed"') && line.includes('"structuring"'),
      ),
      "audit log shows structuring completed within the observation window",
    ).toBe(true);

    // Pause the case, then assert the early artifacts exist on disk.
    const pauseResp = await apiPost(page, `/cases/${caseId}/pause`);
    expect(pauseResp.status).toBe(200);

    const intake = await apiGet<{ content: string }>(
      page,
      `/_test/case-file/${caseId}?path=shared/intake_record.yaml`,
    );
    expect(intake.status).toBe(200);
    const spec = await apiGet<{ content: string }>(
      page,
      `/_test/case-file/${caseId}?path=shared/decision_spec.yaml`,
    );
    expect(spec.status).toBe(200);
  });
});
