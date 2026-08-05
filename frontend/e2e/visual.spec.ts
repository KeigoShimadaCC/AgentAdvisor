import { test, expect } from "@playwright/test";
import { modeDescribe } from "./helpers";

/**
 * Visual regression — SPEC-045.
 *
 * Until this file existed, nothing in the repo could detect an unintended
 * layout or colour change. That is a strange gap in a codebase with 86 unit
 * tests and an axe sweep, and an untenable one for a phase whose whole subject
 * is visual hierarchy: SPEC-048 rewrites the shell, SPEC-051 the brief, and a
 * text assertion cannot tell you whether either quietly broke a third screen.
 *
 * Baselines are captured from the *current* UI on purpose. That makes every
 * later phase-9 diff legible as an intentional change rather than a surprise,
 * and it is what makes the token migration in this spec provable: a pure
 * substitution must move no pixels at all.
 *
 * Baseline churn is expected as the phase proceeds. The rule is that it is
 * reviewed in the diff, never blind-accepted with `--update-snapshots` on a
 * red run.
 */

const FIXTURE_DONE = "case-001-fixture-001";
const FIXTURE_PARKED = "case-002-fixture-002-parked";

/** Every route the fixture data can reach, which is the full route table. */
const ROUTES: { name: string; url: string }[] = [
  { name: "library", url: "/" },
  { name: "new-decision", url: "/new" },
  { name: "case-detail", url: `/cases/${FIXTURE_DONE}` },
  { name: "scope-sheet", url: `/cases/${FIXTURE_PARKED}/scope` },
  { name: "brief", url: `/cases/${FIXTURE_DONE}/brief` },
  { name: "delivery", url: `/cases/${FIXTURE_DONE}/delivery` },
  { name: "room-sources", url: `/cases/${FIXTURE_DONE}/rooms/sources` },
  { name: "room-assumptions", url: `/cases/${FIXTURE_DONE}/rooms/assumptions` },
  { name: "room-options", url: `/cases/${FIXTURE_DONE}/rooms/options` },
  { name: "room-challenges", url: `/cases/${FIXTURE_DONE}/rooms/challenges` },
  { name: "room-plan", url: `/cases/${FIXTURE_DONE}/rooms/plan` },
  { name: "room-method", url: `/cases/${FIXTURE_DONE}/rooms/method` },
  { name: "not-found", url: "/no-such-route" },
];

modeDescribe("fixture", "Fixture mode — visual baselines", () => {
  for (const route of ROUTES) {
    test(`${route.name} matches its baseline`, async ({ page }) => {
      await page.goto(route.url);
      // The elapsed timer in LiveActivity ticks every second, so a screenshot
      // taken mid-tick would differ from its baseline for reasons that have
      // nothing to do with styling. Freeze anything that renders a duration.
      await page.addStyleTag({
        content: `
          .live-activity-elapsed,
          .method-elapsed { visibility: hidden !important; }
        `,
      });
      // NOT networkidle: every case route holds an SSE stream open, so the
      // network is never idle and the wait would time out on 9 of 13 routes.
      // Wait for the app shell plus a paint instead.
      await page.locator("main.app-main").waitFor({ state: "visible" });
      await page.waitForTimeout(250);
      await expect(page).toHaveScreenshot(`${route.name}.png`, { fullPage: true });
    });
  }
});

modeDescribe("fixture", "Fixture mode — reduced motion", () => {
  test("honours prefers-reduced-motion", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_DONE}/brief`);
    await page.locator("main.app-main").waitFor({ state: "visible" });

    // styles.css disables the brief's settle animation under the preference,
    // and Brief.tsx reads the same media query to skip its settle class. The
    // media query is what both hang off, so assert the browser reports it and
    // that nothing on the page is left running an animation.
    const reduced = await page.evaluate(
      () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    );
    expect(reduced, "project did not apply the reduced-motion preference").toBe(true);

    const animated = await page.evaluate(() =>
      [...document.querySelectorAll("*")].filter((el) => {
        const style = getComputedStyle(el);
        return style.animationName !== "none" && style.animationDuration !== "0s";
      }).length,
    );
    expect(animated, "an element still animates under reduced motion").toBe(0);
  });
});
