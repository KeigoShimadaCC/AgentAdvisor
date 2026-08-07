import { test, expect, type Page } from "@playwright/test";
import { modeDescribe, FIXTURE_COMPLETED, FIXTURE_PARKED } from "./helpers";

/**
 * The density guard — SPEC-048.
 *
 * Hierarchy is the one part of a redesign that reliably rots, because every
 * later change adds and nothing removes. Two properties are cheap to read off
 * the DOM and hold the shape:
 *
 *  1. **Border budget.** A border is allowed to mean exactly two things — this
 *     needs your action, or this is uncertain. Before this phase the case
 *     surface rendered fifty-odd bordered containers, which means a border
 *     meant nothing at all. The budget is per route and deliberately tight.
 *
 *  2. **Answer dominance.** The recommendation must be set larger than every
 *     metric on the same screen. This is not a style preference: the delivery
 *     screen shipped the recommendation at 18 px while a source-strength letter
 *     grade rendered at 24 px in the accent colour, so the loudest thing on the
 *     page was a diagnostic about the answer rather than the answer.
 *
 * Setting the budget: every route below measures **0** after this spec's border
 * pass — the case surface was 6 and the method room 27 before it. The budgets
 * are 2 rather than 0 so a screen adding one deliberate container is not blocked
 * on a guard change, while a return to card-per-section (which is what
 * regression looks like here) trips immediately. Both guards were checked
 * against a deliberate regression before being trusted: re-bordering three
 * method-room sections fails the budget, and setting the source-strength grade
 * above the recommendation fails answer dominance.
 */

/**
 * Borders that carry one of the two permitted meanings, and so are exempt.
 * `SUBTREE` exempts what is inside as well — a bordered field inside an action
 * card is part of that action. `SELF` exempts only the element itself, so the
 * context panel's own edge is free but the room rendered inside it is not.
 */
const EXEMPT_SUBTREE = [
  ".action-card", // needs your action
  ".failure-path", // needs your action
  ".early-stop", // needs your action
  ".signature-block", // needs your action
  ".dissent-blocking", // needs your action — a signature is blocked until you resolve it
  ".uncertainty-widget", // is uncertain
  ".not-assessed", // is uncertain
  ".non-final-stamp", // is uncertain
  ".grade-chip", // is uncertain — a source-strength grade
  ".source-card-flag", // is uncertain — a limitation on a source
  ".corpus-concentration-warning", // is uncertain
  ".weakest-callout", // is uncertain
  ".load-bearing-callout", // is uncertain
];
const EXEMPT_SELF = [
  "th", // a table's ruling is a table's ruling, not a card
  "td",
  ".app-shell-panel", // a region edge, not a card
  ".app-shell-panel-head",
  ".altitude-control", // a control's own affordance
  "input",
  "textarea",
  "select",
  "button",
];

async function borderedCount(page: Page): Promise<number> {
  return page.evaluate(({ subtree, self }) => {
    const hasBorder = (style: CSSStyleDeclaration): boolean =>
      ["Top", "Right", "Bottom", "Left"].some((side) => {
        const width = parseFloat(style.getPropertyValue(`border-${side.toLowerCase()}-width`));
        const kind = style.getPropertyValue(`border-${side.toLowerCase()}-style`);
        return width > 0 && kind !== "none" && kind !== "hidden";
      });

    return [...document.querySelectorAll("body *")].filter((el) => {
      if (subtree.some((sel) => el.closest(sel) !== null)) return false;
      if (self.some((sel) => el.matches(sel))) return false;
      const style = getComputedStyle(el);
      if (style.display === "none" || style.visibility === "hidden") return false;
      // A single hairline rule separating two regions is a divider, not a box.
      // Boxes are what crowd a screen, so count only elements bordered on more
      // than one side.
      const sides = ["top", "right", "bottom", "left"].filter((side) => {
        const width = parseFloat(style.getPropertyValue(`border-${side}-width`));
        const kind = style.getPropertyValue(`border-${side}-style`);
        return width > 0 && kind !== "none" && kind !== "hidden";
      });
      return hasBorder(style) && sides.length > 1;
    }).length;
  }, { subtree: EXEMPT_SUBTREE, self: EXEMPT_SELF });
}

async function settle(page: Page): Promise<void> {
  // NOT networkidle: every case route holds an SSE stream open.
  await page.locator("main.app-main").waitFor({ state: "visible" });
  await page.waitForTimeout(250);
}

/** Per-route budget for bordered boxes that are neither action nor uncertainty. */
const BUDGETS: { name: string; url: string; budget: number }[] = [
  { name: "library", url: "/", budget: 2 },
  { name: "new decision", url: "/new", budget: 2 },
  { name: "case surface", url: `/cases/${FIXTURE_COMPLETED}`, budget: 2 },
  { name: "case surface (brief route)", url: `/cases/${FIXTURE_COMPLETED}/brief`, budget: 2 },
  { name: "sources room", url: `/cases/${FIXTURE_COMPLETED}/rooms/sources`, budget: 2 },
  { name: "assumptions room", url: `/cases/${FIXTURE_COMPLETED}/rooms/assumptions`, budget: 2 },
  { name: "options room", url: `/cases/${FIXTURE_COMPLETED}/rooms/options`, budget: 2 },
  { name: "challenges room", url: `/cases/${FIXTURE_COMPLETED}/rooms/challenges`, budget: 2 },
  { name: "plan room", url: `/cases/${FIXTURE_COMPLETED}/rooms/plan`, budget: 2 },
  { name: "method room", url: `/cases/${FIXTURE_COMPLETED}/rooms/method`, budget: 2 },
  { name: "delivery", url: `/cases/${FIXTURE_COMPLETED}/delivery`, budget: 2 },
  { name: "scope sheet", url: `/cases/${FIXTURE_PARKED}/scope`, budget: 2 },
];

modeDescribe("fixture", "Fixture mode — density guard", () => {
  for (const route of BUDGETS) {
    test(`${route.name} stays within its border budget`, async ({ page }) => {
      await page.goto(route.url);
      await settle(page);
      const count = await borderedCount(page);
      expect(
        count,
        `${route.name} renders ${count} bordered boxes that are neither an action ` +
          `nor an uncertainty; the budget is ${route.budget}`,
      ).toBeLessThanOrEqual(route.budget);
    });
  }

  test("the recommendation is larger than every metric on the same screen", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}/delivery`);
    await settle(page);

    const sizes = await page.evaluate(() => {
      const px = (el: Element) => parseFloat(getComputedStyle(el).fontSize);
      const recommendation = document.querySelector(".answer-recommendation");
      const metrics = [
        ".source-strength-grade",
        ".probability-band-phrase",
        ".probability-band-range",
        ".confidence-band-label",
        ".stability-dots-caption",
        ".not-assessed-stamp",
      ]
        .flatMap((sel) => [...document.querySelectorAll(sel)])
        .map((el) => ({ selector: el.className, size: px(el) }));
      return { recommendation: recommendation ? px(recommendation) : null, metrics };
    });

    expect(sizes.recommendation, "no .answer-recommendation on the delivery screen").not.toBeNull();
    // Without this the loop below can pass by finding nothing to compare, which
    // is the failure mode that lets a guard rot into decoration.
    expect(sizes.metrics.length, "no uncertainty metrics rendered to compare against").toBeGreaterThan(0);
    for (const metric of sizes.metrics) {
      expect(
        sizes.recommendation!,
        `${metric.selector} renders at ${metric.size}px, at or above the ` +
          `recommendation's ${sizes.recommendation}px — the metric outranks the answer`,
      ).toBeGreaterThan(metric.size);
    }
  });

  test("the case surface leads with the recommendation, not with apparatus", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}`);
    await settle(page);

    const largest = await page.evaluate(() => {
      const inContent = [...document.querySelectorAll(".app-shell-content *")];
      let best = { text: "", size: 0 };
      for (const el of inContent) {
        // Leaf text nodes only, so a container does not claim its child's size.
        if (el.children.length > 0) continue;
        const text = (el.textContent ?? "").trim();
        if (text.length < 3) continue;
        const size = parseFloat(getComputedStyle(el).fontSize);
        if (size > best.size) best = { text, size };
      }
      return best;
    });

    const recommendation = await page
      .locator(".answer-recommendation")
      .first()
      .evaluate((el) => parseFloat(getComputedStyle(el).fontSize))
      .catch(() => null);

    expect(recommendation, "the case surface renders no .answer-recommendation").not.toBeNull();
    expect(
      recommendation!,
      `the largest text in the content column is "${largest.text}" at ${largest.size}px`,
    ).toBeGreaterThanOrEqual(largest.size);
  });
});
