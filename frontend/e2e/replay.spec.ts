import { test, expect } from "@playwright/test";
import { modeDescribe, apiPost, FIXTURE_COMPLETED } from "./helpers";

// Replay-mode specs run only when E2E_MODE=replay.

/**
 * Replay-mode specs exercise the progress experience against recorded audit
 * timing.  The server replays the fixture case's audit events at scaled
 * timing (--speed 1000) and all POSTs return 409 in replay mode.
 */
modeDescribe("replay", "Replay mode — SSE event ordering", () => {
  test("replays every audit event from since=0 in order", async ({ page }) => {
    // Connect to the SSE endpoint and collect events.
    // We use page.evaluate to open a fetch-based SSE reader in the browser
    // context so the /api proxy is used.
    const events = await page.evaluate(async (caseId: string) => {
      const resp = await fetch(`/api/cases/${caseId}/events?since=0`, {
        headers: { Accept: "text/event-stream" },
      });
      if (!resp.body) return [];

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      const collected: { line_cursor: number; event_type: string }[] = [];
      const deadline = Date.now() + 15_000;

      while (Date.now() < deadline) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const line = frame.trim();
          if (!line || line.startsWith(":")) continue;
          if (line.startsWith("data: ")) {
            try {
              const evt = JSON.parse(line.slice(6));
              collected.push({
                line_cursor: evt.line_cursor,
                event_type: evt.event_type,
              });
            } catch {
              // skip unparseable
            }
          }
        }
        if (collected.length >= 20) break;
      }
      return collected;
    }, FIXTURE_COMPLETED);

    // At least some events should have been replayed.
    expect(events.length).toBeGreaterThan(0);

    // Line cursors must be strictly increasing (events arrive in order).
    for (let i = 1; i < events.length; i++) {
      expect(events[i].line_cursor).toBeGreaterThan(events[i - 1].line_cursor);
    }
  });

  test("brief sections appear after their artifact events", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}/brief`);

    // The brief should eventually show sections (replay mode serves the
    // completed fixture, so sections should be present immediately).
    const sections = page.locator(".brief-sections .brief-section");
    await expect(sections.first()).toBeVisible();

    // No section should show the "not yet" placeholder for the completed fixture.
    const placeholders = page.locator("text=Not yet — this part of the case has not run.");
    await expect(placeholders).toHaveCount(0);
  });
});

modeDescribe("replay", "Replay mode — read-only enforcement", () => {
  test("checkpoint POST returns 409 in replay mode", async ({ page }) => {
    await page.goto("/");

    // Any checkpoint POST should be rejected with 409 in replay mode.
    const resp = await apiPost(page, `/cases/${FIXTURE_COMPLETED}/checkpoints/scope`, {
      decision: "approve",
      approved_by: "user",
    });
    expect(resp.status).toBe(409);
  });

  test("new case POST returns 409 in replay mode", async ({ page }) => {
    await page.goto("/");

    const resp = await apiPost(page, "/cases", {
      prompt: "Should I do anything?",
      effort: "default",
    });
    expect(resp.status).toBe(409);
  });
});

modeDescribe("replay", "Replay mode — sealed answer card", () => {
  test("sealed answer card is absent for a done case in replay", async ({ page }) => {
    // In replay mode, the fixture case is "done", so the sealed card is not
    // shown (it only shows during synthesis/review/awaiting_final_approval).
    await page.goto(`/cases/${FIXTURE_COMPLETED}/brief`);

    const sealedCard = page.locator(".sealed-answer-card");
    await expect(sealedCard).toHaveCount(0);
  });

  test("no element displays a percent-complete for the run", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}/brief`);

    const bodyText = await page.locator("body").innerText();
    // No "XX% complete" style progress indicators
    expect(bodyText).not.toMatch(/\d+%\s*complete/i);
    expect(bodyText).not.toMatch(/percent\s*complete/i);
  });
});
