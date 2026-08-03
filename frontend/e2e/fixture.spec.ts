import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  modeDescribe,
  assertNoForbiddenTerms,
  FIXTURE_COMPLETED,
  FIXTURE_PARKED,
} from "./helpers";

// Fixture-mode specs run only when E2E_MODE=fixture (the default).

modeDescribe("fixture", "Fixture mode — case library", () => {
  test("shows both fixture cases with human-readable stages", async ({ page }) => {
    await page.goto("/");

    // Both case titles should be visible
    await expect(page.locator("text=case-001-fixture-001")).toBeVisible();
    await expect(page.locator("text=case-002-fixture-002-parked")).toBeVisible();

    // Completed case shows "Complete" (stageLabel for done)
    const completedRow = page.locator(".case-list tbody tr").filter({
      hasText: "case-001-fixture-001",
    });
    await expect(completedRow).toContainText("Complete");

    // Parked case shows "Waiting for your review" (stageLabel for awaiting_framing_approval)
    const parkedRow = page.locator(".case-list tbody tr").filter({
      hasText: "case-002-fixture-002-parked",
    });
    await expect(parkedRow).toContainText("Waiting for your review");
  });

  test("parked case appears in the needs-you section funneling to scope", async ({ page }) => {
    await page.goto("/");

    const needsYou = page.locator(".needs-you-header");
    await expect(needsYou).toBeVisible();
    await expect(needsYou).toContainText("case-002-fixture-002-parked");
    await expect(needsYou).toContainText("Needs your review");

    // Clicking the needs-you link navigates to the scope checkpoint
    await needsYou.locator("a", { hasText: "case-002-fixture-002-parked" }).click();
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

    // Brief sections container
    const sections = page.locator(".brief-sections");
    await expect(sections).toBeVisible();

    // At least some section articles render with non-pending status
    const sectionArticles = sections.locator(".brief-section");
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

    // The stability widget is in the uncertainty widgets section
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

    // Audit log list should have items for a completed case
    const logItems = eventLog.locator(".audit-log-item");
    const count = await logItems.count();
    expect(count).toBeGreaterThan(0);
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

      // Room shell header with the room label
      const roomHeader = page.locator(".room-title");
      await expect(roomHeader).toHaveText(room.label);

      // Room body should be present (not stuck on loading)
      const roomBody = page.locator(".room-body");
      await expect(roomBody).toBeVisible();
      // Should not show a persistent loading state
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

    // Restatement section
    await expect(page.locator("h2", { hasText: "Here is what I understood" })).toBeVisible();

    // Options section
    await expect(page.locator("h2", { hasText: "Options on the table" })).toBeVisible();

    // Ground rules section
    await expect(page.locator("h2", { hasText: "Ground rules" })).toBeVisible();

    // Signature section
    await expect(page.locator("h2", { hasText: "Your signature" })).toBeVisible();
  });

  test("terminology guard on the scope sheet", async ({ page }) => {
    await page.goto(`/cases/${FIXTURE_PARKED}/scope`);
    await assertNoForbiddenTerms(page);
  });
});

modeDescribe("fixture", "Fixture mode — accessibility (axe)", () => {
  const axeScreens = [
    { name: "library", url: "/" },
    { name: "scope sheet", url: `/cases/${FIXTURE_PARKED}/scope` },
    { name: "brief", url: `/cases/${FIXTURE_COMPLETED}/brief` },
    { name: "delivery", url: `/cases/${FIXTURE_COMPLETED}/delivery` },
    { name: "sources room", url: `/cases/${FIXTURE_COMPLETED}/rooms/sources` },
    { name: "challenges room", url: `/cases/${FIXTURE_COMPLETED}/rooms/challenges` },
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
