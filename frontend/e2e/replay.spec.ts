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
    // Navigate to the app first so fetch() has a base URL to resolve the
    // relative /api/... path against.
    await page.goto("/");

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
    const sections = page.locator(".brief-document .brief-passage");
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

// ── SPEC-047: the narrator and the live projection ───────────────────────────

modeDescribe("replay", "Replay mode — narrator", () => {
  test("names what is happening, without leaking cursors or enums", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}/brief`);
    const narrator = page.locator(".narrator");
    await narrator.waitFor({ state: "visible" });

    // The narration line must be prose. The old event log rendered
    // `[47] researcher — attempt 1: ok`, which is a debug view: a raw audit
    // cursor and a raw status enum, neither of which means anything to a reader.
    const text = (await narrator.innerText()).trim();
    expect(text.length).toBeGreaterThan(0);
    expect(text).not.toMatch(/\[\d+\]/);
    expect(text).not.toMatch(/role_invocation_|stage_completed|_batch_unpacked/);
  });

  test("narration is driven by the stream, and settles when the case does", async ({ page }) => {
    // Deliberately not "the line changed": replay runs at 60x, so a completed
    // fixture can flush its whole history between two reads. Racing the stream
    // makes a flaky test, and a flaky visual/narration gate gets muted rather
    // than fixed. Assert the end state instead, which is deterministic.
    await page.goto(`/cases/${FIXTURE_COMPLETED}/brief`);
    const narrator = page.locator(".narrator");
    await narrator.waitFor({ state: "visible" });

    await expect
      .poll(async () => (await narrator.innerText()).includes("complete"), { timeout: 20_000 })
      .toBe(true);

    // And it got there by folding the stream, not by reading the projection:
    // the counters only exist if events were reduced.
    const counters = page.locator(".narrator-counters");
    if (await counters.count()) {
      await expect(counters).toContainText(/evidence|assumptions|objections/);
    }
  });

  test("the case map shows the cycles and never claims a phase that is not current", async ({
    page,
  }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}/brief`);
    const map = page.locator(".case-map");
    await map.waitFor({ state: "visible" });

    // All three cycles are drawn before any of them runs: a loop the user has
    // been shown is a plan, not a malfunction.
    await expect(page.getByTestId("cycle-rescope")).toBeVisible();
    await expect(page.getByTestId("cycle-repair")).toBeVisible();
    await expect(page.getByTestId("cycle-re-review")).toBeVisible();

    await expect(page.locator(".case-map-phase-current")).toHaveCount(1);
  });
});

modeDescribe("replay", "Replay mode — the away digest over a real cursor gap (SPEC-051)", () => {
  /**
   * The digest's whole claim is that it summarises the gap between where a
   * reader was and where the case is. Replay mode is the only place that gap is
   * real: the audit stream is delivered against a clock, so a cursor written
   * before the run and read after it spans genuine events.
   */
  test("summarises what happened between a stored cursor and the head", async ({ page }) => {
    await page.goto("/");
    // Arrive as a reader who had seen nothing.
    await page.evaluate((caseId) => {
      window.localStorage.setItem(`agentadvisor:cursor:${caseId}`, "0");
    }, FIXTURE_COMPLETED);

    await page.goto(`/cases/${FIXTURE_COMPLETED}`);
    const digest = page.locator(".away-digest");
    await digest.waitFor({ state: "visible" });

    const text = await digest.innerText();
    // Counts come from the reducer, so assert on the shape rather than on
    // fixture-specific totals that would make this a change-detector.
    expect(text).toMatch(/evidence|objection|assumption|stage/i);
    expect(text).not.toMatch(/\b0 (pieces|objections|assumptions|stages)\b/);

    await page.getByRole("button", { name: "Dismiss" }).click();
    await expect(digest).toHaveCount(0);
  });

  test("shows no digest to a reader already at the head", async ({ page }) => {
    await page.goto("/");
    await page.evaluate((caseId) => {
      // A cursor past every event: there is nothing to catch up on.
      window.localStorage.setItem(`agentadvisor:cursor:${caseId}`, "999999");
    }, FIXTURE_COMPLETED);

    await page.goto(`/cases/${FIXTURE_COMPLETED}`);
    await page.locator("main.app-main").waitFor({ state: "visible" });
    await page.waitForTimeout(500);
    // "Nothing happened while you were away" is a line that trains people to
    // ignore the component.
    await expect(page.locator(".away-digest")).toHaveCount(0);
  });
});
