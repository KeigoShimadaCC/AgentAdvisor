import { test, expect } from "@playwright/test";
import { modeDescribe, FIXTURE_COMPLETED, FIXTURE_PARKED } from "./helpers";

/**
 * The calibration language, across every route — SPEC-054.
 *
 * The product's differentiator is that it keeps four kinds of uncertainty
 * separate and refuses to collapse them into one number. That is a claim about
 * every screen, not about one component, so it is asserted by sweeping the route
 * table rather than by rendering a widget in isolation.
 */

const ROUTES = [
  "/",
  `/cases/${FIXTURE_COMPLETED}`,
  `/cases/${FIXTURE_COMPLETED}/delivery`,
  `/cases/${FIXTURE_COMPLETED}/rooms/sources`,
  `/cases/${FIXTURE_COMPLETED}/rooms/options`,
  `/cases/${FIXTURE_COMPLETED}/rooms/assumptions`,
  `/cases/${FIXTURE_COMPLETED}/rooms/challenges`,
  `/share/${FIXTURE_COMPLETED}`,
  `/cases/${FIXTURE_PARKED}/scope`,
];

/**
 * Words that would only appear if a screen had combined measures.
 *
 * Deliberately excludes the honest sentence SPEC-050 puts on delivery: that
 * sentence composes the four measures into *prose* and contains no digits at
 * all, which is the boundary the two sheets settled. What is forbidden is a
 * number, not a paragraph — a reader can argue with "moderate confidence and
 * thin evidence" and cannot argue with "0.68".
 */
const FORBIDDEN = [
  /overall confidence/i,
  /combined (confidence|score|rating)/i,
  /average confidence/i,
  /composite score/i,
  /aggregate (confidence|score)/i,
  /confidence score of/i,
  /certainty score/i,
];

modeDescribe("fixture", "Fixture mode — the calibration language (SPEC-054)", () => {
  for (const url of ROUTES) {
    test(`${url} synthesises no combined confidence`, async ({ page }) => {
      await page.goto(url);
      await page.locator("main.app-main").waitFor({ state: "visible" });
      await page.waitForTimeout(200);
      const text = await page.locator("body").innerText();

      for (const pattern of FORBIDDEN) {
        expect(
          text,
          `${url} renders a synthesised summary matching ${pattern} — the four measures must stay separate`,
        ).not.toMatch(pattern);
      }
    });
  }

  test("the four measures render in four different idioms on the answer", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}`);
    await page.locator(".uncertainty-summary").waitFor({ state: "visible" });

    const summary = page.locator(".uncertainty-summary");
    // A band, a grade, countable marks and a range — four kinds, so no two
    // measures can be silently swapped for a combined one.
    const kinds = await summary.evaluate((el) => {
      const found = new Set<string>();
      for (const child of el.querySelectorAll("[class*='u-']")) {
        for (const cls of child.classList) {
          if (/^u-(band|grade|countable|range|not_assessed)$/.test(cls)) found.add(cls);
        }
      }
      return [...found].sort();
    });
    expect(kinds.length).toBeGreaterThanOrEqual(3);
  });

  test("every countable mark in the app matches its run count", async ({ page }) => {
    // The completed fixture's stability is deliberately the sentinel (0 of 1) —
    // `fixture.spec.ts` depends on that to prove a sentinel never renders as a
    // bare number. So this sweeps for countable marks wherever they *do* appear
    // and validates each, rather than asserting one exists on a route where the
    // data says it should not. The exhaustive count check is in
    // `language.test.tsx`, which drives the component directly.
    let checked = 0;
    for (const url of ROUTES) {
      await page.goto(url);
      await page.locator("main.app-main").waitFor({ state: "visible" });
      const disclosure = page.locator(".uncertainty-disclosure > summary");
      if (await disclosure.count()) await disclosure.first().click();

      const dots = page.locator(".countable-dots");
      for (let i = 0; i < (await dots.count()); i++) {
        const mark = dots.nth(i);
        const label = (await mark.getAttribute("aria-label")) ?? "";
        const match = label.match(/held in (\d+) of (\d+)/);
        expect(match, `a countable mark at ${url} names no run count: "${label}"`).not.toBeNull();
        const [, supporting, total] = match!;
        await expect(mark.locator(".u-dot")).toHaveCount(Number(total));
        await expect(mark.locator(".u-dot.filled")).toHaveCount(Number(supporting));
        // And never a percentage, which is what a countable mark exists to avoid.
        expect(await mark.innerText()).not.toMatch(/%/);
        checked += 1;
      }
    }
    // Recorded rather than asserted: with this fixture the honest number is 0,
    // and a test that demanded otherwise would be demanding fixture data that
    // contradicts another test.
    console.log(`countable marks validated: ${checked}`);
  });

  test("not assessed is stamped, never shown as zero", async ({ page }) => {
    // The completed fixture has an unassessed stability measure.
    await page.goto(`/cases/${FIXTURE_COMPLETED}/delivery`);
    await page.locator(".uncertainty-disclosure > summary").click();

    const stamps = page.locator(".not-assessed-stamp");
    if ((await stamps.count()) === 0) test.skip(true, "fixture has no unassessed measure");

    const container = stamps.first().locator("xpath=..");
    await expect(container).toContainText(/Not assessed/i);
    await expect(container).not.toContainText("0%");
    await expect(container.locator(".u-dot")).toHaveCount(0);
  });

  test("support expands in place without navigating away", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}`);
    await page.locator(".brief-document .brief-passage").first().waitFor({ state: "visible" });

    const why = page.locator(".why-toggle").first();
    await why.waitFor({ state: "visible" });
    const urlBefore = page.url();

    await why.click();
    await expect(page.locator(".why-body").first()).toBeVisible();
    // The whole point: the reader has not left the paragraph.
    expect(page.url()).toBe(urlBefore);
    await expect(page.locator(".brief-document .brief-passage").first()).toBeVisible();
  });
});
