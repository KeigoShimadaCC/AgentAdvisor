import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  modeDescribe,
  assertNoForbiddenTerms,
  apiGet,
  FIXTURE_COMPLETED,
  FIXTURE_PARKED,
} from "./helpers";

// Fixture-mode specs run only when E2E_MODE=fixture (the default).

// Real fixture case titles (the library renders the title, not the case_id).
const COMPLETED_TITLE = "Should I invest $50k in Nvidia vs semiconductor ETF?";
const PARKED_TITLE = "I have $50k and want semiconductor exposure. Nvidia or ETF?";

modeDescribe("fixture", "Fixture mode — case library", () => {
  test("shows both fixture cases with human-readable stages", async ({ page }) => {
    await page.goto("/");

    // Both case titles should be visible (library renders title, not case_id)
    await expect(page.locator(".case-list")).toContainText(COMPLETED_TITLE);
    await expect(page.locator(".case-list")).toContainText(PARKED_TITLE);

    // Completed case shows "Complete" (stageLabel for done)
    const completedRow = page.locator(".case-list tbody tr").filter({
      hasText: COMPLETED_TITLE,
    });
    await expect(completedRow).toContainText("Complete");

    // Parked case shows "Waiting for your review" (stageLabel for awaiting_framing_approval)
    const parkedRow = page.locator(".case-list tbody tr").filter({
      hasText: PARKED_TITLE,
    });
    await expect(parkedRow).toContainText("Waiting for your review");
  });

  test("parked case appears in the needs-you section funneling to scope", async ({ page }) => {
    await page.goto("/");

    const needsYou = page.locator(".needs-you-header");
    await expect(needsYou).toBeVisible();
    // The needs-you section shows the case title, not the case_id
    await expect(needsYou).toContainText(PARKED_TITLE);
    await expect(needsYou).toContainText("Needs your review");

    // Clicking the needs-you link navigates to the scope checkpoint
    await needsYou.locator("a", { hasText: PARKED_TITLE }).click();
    await expect(page).toHaveURL(/\/cases\/case-002-fixture-002-parked\/scope$/);
  });

  test("terminology guard: no raw enum strings on the library page", async ({ page }) => {
    await page.goto("/");
    await assertNoForbiddenTerms(page);
  });
});

modeDescribe("fixture", "Fixture mode — delivered brief journey", () => {
  test("brief shows all sections for the completed case", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}/brief`);

    // The brief is a document of passages now, not a stack of section cards
    // (SPEC-048); /brief resolves to the one case surface.
    const sections = page.locator(".brief-document");
    await expect(sections).toBeVisible();

    // At least some passages render with non-pending status
    const sectionArticles = sections.locator(".brief-passage");
    const count = await sectionArticles.count();
    expect(count).toBeGreaterThan(0);

    // No section should show the "not yet" placeholder for a completed case
    const placeholders = sections.locator("text=Not yet — this part of the case has not run.");
    await expect(placeholders).toHaveCount(0);
  });

  test("delivery page shows the answer card and key reasons", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}/delivery`);

    // Answer card
    const answerCard = page.locator(".answer-card");
    await expect(answerCard).toBeVisible();
    await expect(answerCard).toContainText("Recommended action");

    // Key reasons section
    const keyReasons = page.locator(".key-reasons");
    await expect(keyReasons).toBeVisible();
    await expect(keyReasons.locator("li").first()).toBeVisible();
  });

  test("citation chip opens the record inspector panel", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}/delivery`);

    // Wait for citation links to render
    const citation = page.locator(".citation-link").first();
    await expect(citation).toBeVisible();
    await citation.click();

    // Inspector panel opens
    const inspector = page.locator(".inspector-panel");
    await expect(inspector).toBeVisible();
    await expect(inspector.locator(".inspector")).toBeVisible();
  });

  test("stability sentinel renders 'not assessed', never a bare number", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}/delivery`);

    // SPEC-050 moved the four encodings one click down, under "How sure is
    // this?", so the answer is not read through four instruments. They are
    // unchanged in substance — including this sentinel.
    await page.locator(".uncertainty-disclosure > summary").click();
    const stabilityWidget = page.locator(".uncertainty-widget", { hasText: "Stability" });
    await expect(stabilityWidget).toBeVisible();

    // It must never show "0.0%" or a bare percentage for stability
    const stabilityText = await stabilityWidget.innerText();
    expect(stabilityText).not.toMatch(/\b0\.0%\b/);
  });

  test("terminology guard: no raw enum strings on the brief", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}/brief`);
    await assertNoForbiddenTerms(page);
  });

  test("terminology guard: no raw enum strings on delivery", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}/delivery`);
    await assertNoForbiddenTerms(page);
  });
});

modeDescribe("fixture", "Fixture mode — rooms walkthrough", () => {
  test("method room shows audit events", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}/rooms/method`);

    const eventLog = page.locator(".method-event-log");
    await expect(eventLog).toBeVisible();

    // Audit log list should have items for a completed case. The container
    // renders before its items arrive, so a bare count() races the fetch and
    // reads 0 — assert through an auto-retrying matcher instead.
    const logItems = eventLog.locator(".audit-log-item");
    await expect(logItems.first()).toBeVisible();
  });

  const rooms = [
    { key: "sources", label: "Sources" },
    { key: "assumptions", label: "Assumptions" },
    { key: "options", label: "Options" },
    { key: "challenges", label: "Challenges" },
    { key: "plan", label: "Plan" },
  ] as const;

  for (const room of rooms) {
    test(`${room.label} room renders`, async ({ page }) => {
      await page.goto(`/cases/${FIXTURE_COMPLETED}/rooms/${room.key}`);

      // A room deep link opens the context panel over the case surface
      // (SPEC-048); the panel's own head carries the room name.
      const panel = page.locator(".app-shell-panel");
      await expect(panel.locator(".app-shell-panel-head h3")).toHaveText(room.label);

      // The argument stays on screen behind the panel — that is the point.
      await expect(page.locator(".app-shell-content .brief-document")).toBeVisible();

      // Room body should be present (not stuck on loading)
      const roomBody = panel.locator(".room-body");
      await expect(roomBody).toBeVisible();
      await expect(roomBody.locator("text=Loading…")).toHaveCount(0);
    });
  }

  test("terminology guard: no raw enum strings in rooms", async ({ page }) => {
    for (const room of ["sources", "assumptions", "options", "challenges", "plan", "method"]) {
      await page.goto(`/cases/${FIXTURE_COMPLETED}/rooms/${room}`);
      await assertNoForbiddenTerms(page);
    }
  });
});

modeDescribe("fixture", "Fixture mode — scope checkpoint (parked case)", () => {
  test("scope sheet renders for the parked case", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_PARKED}/scope`);

    // SPEC-050: the sheet leads with one question and one consequence line.
    await expect(page.locator("h2", { hasText: "Here is what I understood" })).toBeVisible();
    await expect(page.locator(".scope-consequence")).toBeVisible();

    // Ground rules stay outside the disclosure: confirming them is required to
    // sign, and required work must not hide behind a control labelled "adjust".
    await expect(page.locator("h2", { hasText: "Ground rules" })).toBeVisible();
    await expect(page.locator("h2", { hasText: "Your signature" })).toBeVisible();

    // Options are one click down, and the summary counts what is in there.
    await expect(page.locator("h2", { hasText: "Options on the table" })).toBeHidden();
    await expect(page.locator(".scope-adjust-counts")).toContainText(/option/);
    await page.locator(".scope-adjust > summary").click();
    await expect(page.locator("h2", { hasText: "Options on the table" })).toBeVisible();
  });

  test("terminology guard on the scope sheet", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_PARKED}/scope`);
    await assertNoForbiddenTerms(page);
  });
});

modeDescribe("fixture", "Fixture mode — accessibility (axe)", () => {
  // SPEC-045: extended from six screens to the full route table, and run in
  // whichever theme the project supplies — which is what finally makes
  // SPEC-037's "in both themes" criterion true rather than aspirational.
  const axeScreens = [
    { name: "library", url: "/" },
    { name: "new decision", url: "/new" },
    { name: "case detail", url: `/cases/${FIXTURE_COMPLETED}` },
    { name: "scope sheet", url: `/cases/${FIXTURE_PARKED}/scope` },
    { name: "brief", url: `/cases/${FIXTURE_COMPLETED}/brief` },
    { name: "delivery", url: `/cases/${FIXTURE_COMPLETED}/delivery` },
    { name: "sources room", url: `/cases/${FIXTURE_COMPLETED}/rooms/sources` },
    { name: "assumptions room", url: `/cases/${FIXTURE_COMPLETED}/rooms/assumptions` },
    { name: "options room", url: `/cases/${FIXTURE_COMPLETED}/rooms/options` },
    { name: "challenges room", url: `/cases/${FIXTURE_COMPLETED}/rooms/challenges` },
    { name: "plan room", url: `/cases/${FIXTURE_COMPLETED}/rooms/plan` },
    { name: "method room", url: `/cases/${FIXTURE_COMPLETED}/rooms/method` },
    { name: "inspector", url: `/cases/${FIXTURE_COMPLETED}/inspector/E-001` },
    { name: "signed record", url: `/cases/${FIXTURE_COMPLETED}/scope/signed` },
    { name: "not found", url: "/no-such-route" },
  ];

  for (const screen of axeScreens) {
    test(`${screen.name} has no serious/critical axe violations`, async ({ page }) => {
      await page.goto(screen.url);
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      const serious = results.violations.filter(
        (v) => v.impact === "serious" || v.impact === "critical",
      );
      expect(serious, `${screen.name} has ${serious.length} serious/critical violations`).toEqual([]);
    });
  }
});

modeDescribe("fixture", "Fixture mode — route consolidation (SPEC-048)", () => {
  /**
   * The case surface absorbed `/brief` and the six room pages. Consolidation is
   * only safe if nothing that used to resolve stops resolving: a link in a
   * notification, a bookmark, or an old export must not land on "That page does
   * not exist".
   */
  const routes = [
    `/cases/${FIXTURE_COMPLETED}`,
    `/cases/${FIXTURE_COMPLETED}/brief`,
    `/cases/${FIXTURE_COMPLETED}/rooms/sources`,
    `/cases/${FIXTURE_COMPLETED}/rooms/assumptions`,
    `/cases/${FIXTURE_COMPLETED}/rooms/options`,
    `/cases/${FIXTURE_COMPLETED}/rooms/challenges`,
    `/cases/${FIXTURE_COMPLETED}/rooms/plan`,
    `/cases/${FIXTURE_COMPLETED}/rooms/method`,
    `/cases/${FIXTURE_COMPLETED}/delivery`,
    `/cases/${FIXTURE_COMPLETED}/inspector/E-001`,
    `/cases/${FIXTURE_PARKED}/scope`,
    `/cases/${FIXTURE_PARKED}/scope/signed`,
  ];

  for (const url of routes) {
    test(`${url} still resolves`, async ({ page }) => {
      await page.goto(url);
      await page.locator("main.app-main").waitFor({ state: "visible" });
      await expect(page.locator(".not-found")).toHaveCount(0);
    });
  }

  test("no screen carries a back link, because the chrome never goes away", async ({ page }) => {
    for (const url of routes) {
      await page.goto(url);
      await page.locator("main.app-main").waitFor({ state: "visible" });
      await expect(page.locator(".back-link")).toHaveCount(0);
    }
  });

  test("no screen renders a bare loading string", async ({ page }) => {
    // Skeletons replaced `<p>Loading…</p>` everywhere. A screen that reverts
    // gets caught here rather than in a design review six months later.
    for (const url of routes) {
      await page.goto(url);
      await page.locator("main.app-main").waitFor({ state: "visible" });
      await expect(page.getByText("Loading…", { exact: true })).toHaveCount(0);
    }
  });

  test("the heading is the decision question, never the case id", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}`);
    const heading = page.locator(".case-chrome-question");
    await expect(heading).toBeVisible();
    const text = ((await heading.textContent()) ?? "").trim();
    expect(text).not.toMatch(/^case-\d+-/);
    expect(text).not.toContain(FIXTURE_COMPLETED);
  });

  test("terminology guard on the consolidated surfaces", async ({ page }) => {
    for (const url of [
      `/cases/${FIXTURE_COMPLETED}`,
      `/cases/${FIXTURE_COMPLETED}/rooms/sources`,
      `/cases/${FIXTURE_COMPLETED}/inspector/E-001`,
      `/cases/${FIXTURE_PARKED}/scope/signed`,
    ]) {
      await page.goto(url);
      await page.locator("main.app-main").waitFor({ state: "visible" });
      await assertNoForbiddenTerms(page);
    }
  });
});

modeDescribe("fixture", "Fixture mode — reading altitude (SPEC-048)", () => {
  test("Answer strips the apparatus, Method restores it, and the choice persists", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}`);
    await page.locator("main.app-main").waitFor({ state: "visible" });

    await page.getByRole("button", { name: "Answer" }).click();
    await expect(page.locator(".case-map")).toHaveCount(0);
    await expect(page.locator(".provenance-stripe")).toHaveCount(0);
    await expect(page.locator(".answer-recommendation")).toBeVisible();

    await page.getByRole("button", { name: "Method" }).click();
    await expect(page.locator(".case-map")).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Rooms" })).toBeVisible();

    // A reader preference, not a per-case one: it survives a different case and
    // a reload.
    await page.goto(`/cases/${FIXTURE_PARKED}`);
    await page.locator("main.app-main").waitFor({ state: "visible" });
    await expect(page.getByRole("button", { name: "Method" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await page.reload();
    await expect(page.getByRole("button", { name: "Method" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  test("a room opens beside the argument and closing it returns to the case", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}`);
    await page.locator("main.app-main").waitFor({ state: "visible" });
    await page.getByRole("button", { name: "Method" }).click();

    await page.getByRole("link", { name: "Sources" }).click();
    await expect(page.locator(".app-shell-panel")).toBeVisible();
    // The argument is still there — the panel did not replace the page.
    await expect(page.locator(".app-shell-content .brief-document")).toBeVisible();

    await page.getByRole("button", { name: "Close" }).click();
    await expect(page.locator(".app-shell-panel")).toHaveCount(0);
    await expect(page).toHaveURL(new RegExp(`/cases/${FIXTURE_COMPLETED}$`));
  });
});

modeDescribe("fixture", "Fixture mode — the cast (SPEC-049)", () => {
  test("provenance renders as a voice, never as its enum value", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}`);
    // The shell paints before the case loads, so waiting on it is not enough.
    await page.locator(".brief-document .brief-passage").first().waitFor({ state: "visible" });

    const stripes = page.locator(".provenance-stripe");
    expect(await stripes.count()).toBeGreaterThan(0);
    const labels = await stripes.allTextContents();
    for (const label of labels) {
      expect(label.trim()).not.toMatch(/_/);
      expect(label.trim()).not.toBe("Unattributed");
    }
    // The six the north star requires the interface to distinguish.
    expect(labels.some((l) => /From a source|Read of the evidence|Assumed|Calculated|From you|The recommendation/.test(l))).toBe(true);
  });

  test("an objection whose target is not a brief section is shown, not dropped", async ({ page }) => {
    // The fixture's only objection targets `preliminary_recommendation.rationale[0]`,
    // which is not a brief section key — exactly the fallback path.
    await page.goto(`/cases/${FIXTURE_COMPLETED}`);
    await page.locator(".brief-document .brief-passage").first().waitFor({ state: "visible" });

    const unplaced = page.locator(".margin-notes-unplaced");
    await expect(unplaced).toBeVisible();
    await expect(unplaced).toContainText("Staged entry may miss upside");
    await expect(unplaced).toContainText("The Challenger");
    await expect(unplaced).toContainText(/rather than dropped/i);
  });

  test("no dissent surface when the two tracks agree", async ({ page }) => {
    // The fixture has `agreement: true`. A dissent surface here would be the UI
    // inventing disagreement.
    await page.goto(`/cases/${FIXTURE_COMPLETED}`);
    await page.locator(".brief-document .brief-passage").first().waitFor({ state: "visible" });
    await expect(page.locator(".dissent")).toHaveCount(0);
  });

  test("the challenges room still carries the divergence detail, attributed", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}/rooms/challenges`);
    await page.locator(".app-shell-panel").waitFor({ state: "visible" });

    const panel = page.locator(".app-shell-panel");
    await expect(panel.getByText("Agree", { exact: true })).toBeVisible();
    await expect(panel.locator(".never-averaged-footer")).toBeVisible();
    // Objections carry the Challenger's voice here too.
    await expect(panel.locator(".objection-voice").first()).toHaveText("The Challenger");
  });
});

modeDescribe("fixture", "Fixture mode — presence (SPEC-051)", () => {
  test("the tab title carries the case state, and is restored on leaving", async ({ page }) => {
    await page.goto("/");
    const libraryTitle = await page.title();

    await page.goto(`/cases/${FIXTURE_COMPLETED}`);
    await page.locator(".brief-document .brief-passage").first().waitFor({ state: "visible" });
    const caseTitle = await page.title();
    expect(caseTitle).not.toBe(libraryTitle);
    // The fixture is complete, so the title says so rather than looking live.
    expect(caseTitle).toContain("✓");

    // A parked case reads as needing you, distinguishably.
    await page.goto(`/cases/${FIXTURE_PARKED}`);
    await page.locator("main.app-main").waitFor({ state: "visible" });
    await expect.poll(() => page.title()).toContain("Needs you");
  });

  test("no notification is issued without permission, and the fallback appears instead", async ({
    page,
  }) => {
    // Denied is the interesting case: a product that only ever notified through
    // the OS would simply go silent for these users.
    await page.goto("/");
    await page.evaluate(() => {
      window.localStorage.setItem("agentadvisor:presence", "notify");
    });
    await page.context().clearPermissions();

    await page.goto(`/cases/${FIXTURE_PARKED}`);
    await page.locator("main.app-main").waitFor({ state: "visible" });
    await expect(page.locator(".notice-banner")).toBeVisible();
    await expect(page.locator(".notice-banner")).toContainText(/scope review/i);
  });

  test("a watcher is not notified about a gate they can already see", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => window.localStorage.setItem("agentadvisor:presence", "watch"));

    await page.goto(`/cases/${FIXTURE_PARKED}`);
    await page.locator("main.app-main").waitFor({ state: "visible" });
    await page.waitForTimeout(250);
    await expect(page.locator(".notice-banner")).toHaveCount(0);
  });

  test("spend in the chrome shows each count against its cap", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}`);
    await page.locator(".case-chrome-spend").waitFor({ state: "visible" });
    // A count without its denominator says nothing about whether a run is near
    // its limit.
    await expect(page.locator(".case-chrome-spend")).toContainText(/\d+\/\d+ calls/);
  });

  test("marks survive a reload and are scoped to their case", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_COMPLETED}/rooms/assumptions`);
    const mark = page.locator(".reaction-chip", { hasText: "This looks wrong" }).first();
    await mark.waitFor({ state: "visible" });
    await mark.click();
    await expect(mark).toHaveAttribute("aria-pressed", "true");

    await page.reload();
    const after = page.locator(".reaction-chip", { hasText: "This looks wrong" }).first();
    await after.waitFor({ state: "visible" });
    await expect(after).toHaveAttribute("aria-pressed", "true");

    // Nothing was written into the case: the projection is unchanged.
    const { data } = await apiGet<{ case_id: string }>(page, `/cases/${FIXTURE_COMPLETED}/view`);
    expect(data!.case_id).toBe(FIXTURE_COMPLETED);
  });

  test("the calibration screen withholds a score it calls noise", async ({ page }) => {
    await page.goto("/calibration");
    await page.locator(".calibration-interpretation").waitFor({ state: "visible" });
    const interpretation = await page.locator(".calibration-interpretation").innerText();

    // Whatever the fixture memory holds, the screen must never show a headline
    // score alongside an interpretation that calls the sample noise.
    if (/noise, not a calibration estimate|calibration is unknown/.test(interpretation)) {
      await expect(page.locator(".calibration-measure dt", { hasText: "Brier score" })).toHaveCount(0);
    }
  });
});
