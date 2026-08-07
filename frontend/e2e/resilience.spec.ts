import { test, expect } from "@playwright/test";
import { modeDescribe, FIXTURE_COMPLETED } from "./helpers";

/**
 * What happens when the happy path does not hold — SPEC-055.
 *
 * Every sheet before this one specifies a working stream and a running service.
 * Silent failure matters more here than in most products, because a frozen
 * brief and a finished brief look identical: the screen still shows a plausible
 * recommendation, and only an explicit marker distinguishes one from the other.
 */

modeDescribe("fixture", "Fixture mode — degraded states (SPEC-055)", () => {
  test("a service that is not running renders as that, not as a red paragraph", async ({ page }) => {
    // Route-level failure rather than stopping the real server: the assertion is
    // about how the client classifies an unreachable service, and killing the
    // shared webServer would take the rest of the file with it.
    await page.route("**/api/cases", (route) => route.abort("connectionrefused"));
    await page.goto("/");

    const failure = page.locator(".failure-unavailable");
    await expect(failure).toBeVisible();
    await expect(failure).toContainText("The service is not running");
    // The reassurance is load-bearing: a user seeing a blank app assumes their
    // three-hour case is gone.
    await expect(failure).toContainText(/Nothing was lost/);
    await expect(page.locator("p.error")).toHaveCount(0);
  });

  test("retry recovers without a reload once the service is back", async ({ page }) => {
    let down = true;
    await page.route("**/api/cases", (route) => {
      if (down) return route.abort("connectionrefused");
      return route.continue();
    });
    await page.goto("/");
    await expect(page.locator(".failure-unavailable")).toBeVisible();

    down = false;
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.locator(".library-card").first()).toBeVisible();
    await expect(page.locator(".failure")).toHaveCount(0);
  });

  test("a missing case renders not-found, distinctly from a dead service", async ({ page }) => {
    await page.goto("/cases/case-999-no-such-case");
    const failure = page.locator(".failure-not_found");
    await expect(failure).toBeVisible();
    await expect(failure).toContainText("That case does not exist");
  });

  test("a brief with no live stream says so, while still showing the brief", async ({ page }) => {
    // The stream is refused from the first attempt, so the projection loads and
    // the stream does not — which is exactly the dangerous shape: a plausible
    // brief on screen with nothing keeping it current.
    await page.route("**/api/cases/*/events*", (route) => route.abort("connectionrefused"));
    await page.goto(`/cases/${FIXTURE_COMPLETED}`);

    // The brief is there, which is the point: the marker has to be explicit
    // because the page gives no other sign.
    await page.locator(".brief-document .brief-passage").first().waitFor({ state: "visible" });
    await expect(page.locator(".case-chrome-connection")).toBeVisible({ timeout: 30_000 });

    // `stale` itself arrives only after the full backoff ladder (~61s by
    // design); `sse.test.ts` covers that transition directly, and what matters
    // here is that the chrome stops claiming the brief is live.
    const text = await page.locator(".case-chrome-connection").innerText();
    expect(text).toMatch(/Reconnecting|out of date/i);
  });

  test("storage that throws does not break a single screen", async ({ page }) => {
    // Safari private mode, a policy, an exhausted quota — all look like this,
    // and a throw inside a lazy useState initialiser takes down the screen.
    await page.addInitScript(() => {
      const boom = () => {
        throw new DOMException("denied", "SecurityError");
      };
      Object.defineProperty(window, "localStorage", {
        configurable: true,
        get: () => ({ getItem: boom, setItem: boom, removeItem: boom, clear: boom, key: boom, length: 0 }),
      });
    });

    for (const url of ["/", "/new", "/settings", `/cases/${FIXTURE_COMPLETED}`]) {
      await page.goto(url);
      await page.locator("main.app-main").waitFor({ state: "visible" });
      await expect(page.locator(".failure"), `${url} failed with storage unavailable`).toHaveCount(0);
    }

    // And the app says so rather than letting a user discover it by losing a
    // setting twice.
    await page.goto("/settings");
    await expect(page.locator(".settings-not-persistent")).toBeVisible();

    // The controls still work for this tab.
    await page.getByRole("button", { name: /^Dark/ }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  });

  test("the narrator announces transitions and not the elapsed timer", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}`);
    await page.locator(".narrator").waitFor({ state: "visible" });

    // The trap: a live region on the narrator line reads the per-second counter
    // aloud forever. Asserted structurally, because a screen reader cannot be.
    const line = page.locator(".narrator-line");
    if (await line.count()) {
      await expect(line).toHaveAttribute("aria-live", "polite");
    }
    const elapsed = page.locator(".narrator-elapsed");
    if (await elapsed.count()) {
      await expect(elapsed).toHaveAttribute("aria-hidden", "true");
      // And it must not sit inside a live region either.
      const inLive = await elapsed.first().evaluate((el) => el.closest("[aria-live]") !== null);
      expect(inLive, "the elapsed timer is inside a live region").toBe(false);
    }
    await expect(page.locator(".case-chrome-spend")).not.toHaveAttribute("aria-live", /.+/);
  });
});

modeDescribe("replay", "Replay mode — the buffer stays bounded (SPEC-055)", () => {
  test("a long case does not accumulate an unbounded event list", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}`);
    await page.locator("main.app-main").waitFor({ state: "visible" });
    // Replay delivers the recorded stream against a clock; let it run.
    await page.waitForTimeout(3_000);

    // The transcript is the widest window onto the retained buffer.
    const entries = await page.locator(".narrator-entry").count();
    expect(entries).toBeLessThanOrEqual(600);

    // And the narration is still right: counters are folded from every event,
    // not from what happens to be retained.
    await expect(page.locator(".narrator")).toBeVisible();
  });
});
