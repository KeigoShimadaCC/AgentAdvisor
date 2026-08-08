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
      /*
       * The narrator is hidden wholesale, not just its timer (SPEC-055).
       *
       * Its content is a function of stream arrival timing — the line, the
       * counters and the announcements all change as events replay — so it is
       * not a stable screenshot subject at all, and Playwright's own "two
       * consecutive stable screenshots" check said so. Freezing only
       * ".narrator-elapsed" was treating the symptom.
       *
       * Nothing is lost: the reducer and component tests cover what the
       * narrator renders, deterministically, from a fixed event list. A
       * screenshot could only ever assert that some sentence was on screen at
       * some moment.
       *
       * The old freeze list named ".live-activity-elapsed" and
       * ".method-elapsed", neither of which exists in the app any more — which
       * is why the one element that actually ticked every second was the one
       * not frozen, and why room-method passed alone and failed in the matrix.
       */
      await page.addStyleTag({
        // `display: none` for the narrator, not `visibility: hidden`:
        // visibility still reserves layout, and the narrator's *height* grows
        // as announcements accumulate, which shifted everything below it and
        // kept the page unstable even while the text was invisible. The spend
        // line has a fixed height, so hiding it is enough.
        content:
          ".narrator { display: none !important; }" +
          // Sticky positioning plus `fullPage` is a known source of a one-off
          // few-pixel height difference: the captured page was 5,022px on a
          // failing run and 5,017px on a passing one, with *identical content*
          // — the diff was a band at the bottom edge and nothing else. Pinning
          // the sticky regions makes the page height deterministic, and has the
          // side benefit that the baseline shows the whole panel rather than
          // whatever fitted in 80vh.
          ".app-shell-panel, .app-shell-rail { position: static !important;" +
          " max-height: none !important; }" +
          ".case-chrome-spend, .live-activity-elapsed, .method-elapsed" +
          " { visibility: hidden !important; }",
      });
      // NOT networkidle: every case route holds an SSE stream open, so the
      // network is never idle and the wait would time out on 9 of 13 routes.
      await page.locator("main.app-main").waitFor({ state: "visible" });

      // And NOT the app shell alone (SPEC-055). The shell paints before the
      // case loads, so under load — the full matrix, not a single spec — this
      // returned while a room panel was still a skeleton, and the screenshot
      // caught a half-rendered page. That is precisely the flake this suite
      // must not have: it passed alone and failed in the matrix, which is how a
      // visual gate gets muted rather than fixed.
      await page
        .locator(
          ".app-shell-panel .room-body, .brief-document, .library-cards, .scope-lead, " +
            ".delivery, .new-decision, .not-found",
        )
        .first()
        .waitFor({ state: "visible", timeout: 20_000 })
        .catch(() => {
          /* a route with none of these is settled once the shell is up */
        });
      // Longer than SPEC-047's refetch debounce, deliberately.
      //
      // `useCaseView` refetches the projection 250ms after the last content
      // event, and the old settle wait here was *also* 250ms — so under load
      // the screenshot and the refetch's re-render raced, and roughly one full
      // matrix run in five failed on a random route. Each individual route
      // passed twelve times in a row when run alone, which is exactly what a
      // load-sensitive race looks like and exactly how a visual gate earns a
      // reputation for being flaky and gets muted.
      await page.waitForTimeout(1_200);

      /*
       * One discarded capture before the one that counts (SPEC-056 follow-up).
       *
       * This is the fix for the 5017/5022px oscillation that kept one room
       * route failing per matrix run. The cause was not the capture path and
       * not DOM instability, both of which were eliminated: it is that the
       * *first* `fullPage` capture paints below-fold content for the first
       * time, and text line boxes settle by a pixel or two as it does —
       * `H3.brief-passage-label` 19→18, `P.screen-help` 63→65 — which
       * accumulates to a five-pixel page. Measured directly: the document is
       * 5022px before the first capture and 5017px after it, then constant.
       *
       * `toHaveScreenshot` already waits for `document.fonts.ready`, but that
       * resolves before glyphs below the fold have actually been rasterised,
       * so its own stability retry was racing a page still settling.
       *
       * Painting once and throwing the result away costs a few hundred
       * milliseconds and makes every subsequent capture measure a page that
       * has finished moving. The baselines already encode the settled height,
       * so nothing needed re-recording.
       */
      await page.screenshot({ fullPage: true, animations: "disabled", scale: "css" });

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
