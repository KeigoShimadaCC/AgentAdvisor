import { test, expect, type Page } from "@playwright/test";
import { modeDescribe, FIXTURE_COMPLETED, FIXTURE_PARKED } from "./helpers";

/**
 * No pipeline output is reachable only by reading YAML — SPEC-053.
 *
 * The precedent this exists to prevent is in the repo. `orchestrator/calibration.py`
 * computes a Brier score, is fully tested, is careful about small samples, and
 * for four phases had no endpoint and no screen, so no user ever saw it. Phase 8
 * shipped six more artifact groups and was positioned to repeat that six times:
 * when it merged, the independent review verdict and the diagnosticity matrix
 * were *projected into `CaseView`* and drawn by nothing at all.
 *
 * Each entry below names a thing the engine produces and something on a screen
 * that could only be there if it were consumed. The check is deliberately
 * end-to-end rather than a grep over source: a component that imports a field
 * and never renders it would pass a static check and fail a user.
 *
 * Written generically so phase 10's artifacts inherit it: add a row when you add
 * an artifact, and the suite tells you whether anyone can see it.
 */

interface Output {
  /** The engine artifact or projected field group. */
  produces: string;
  /** Where a user would find it. */
  url: string;
  /** Something on that page that can only exist if the output was consumed. */
  evidence: string;
  /** Opened behind a disclosure or a tab, if any. */
  reveal?: (page: Page) => Promise<void>;
}

const PHASE_8_OUTPUTS: Output[] = [
  {
    // SPEC-038: objective weights and the deterministic ranking.
    produces: "objective weights (SPEC-038)",
    url: `/cases/${FIXTURE_PARKED}/scope`,
    evidence: ".weight-list",
    reveal: async (page) => {
      await page.locator(".scope-adjust > summary").click();
    },
  },
  {
    // SPEC-039: the independent reviewer whose dissent blocks delivery.
    produces: "independent review verdict (SPEC-039)",
    url: `/cases/${FIXTURE_COMPLETED}`,
    evidence: ".dissent-blocking",
  },
  {
    // SPEC-040: the competing-hypotheses matrix.
    produces: "diagnosticity matrix (SPEC-040)",
    url: `/cases/${FIXTURE_COMPLETED}/rooms/options`,
    evidence: ".ach-matrix",
  },
  {
    // SPEC-041: the typed action plan.
    produces: "typed action plan (SPEC-041)",
    url: `/cases/${FIXTURE_COMPLETED}/delivery`,
    evidence: ".next-actions, .action-plan, .brief-passage[data-status]",
  },
  {
    // SPEC-042: the monitoring plan and its risk register.
    produces: "monitoring plan and risk register (SPEC-042)",
    url: `/cases/${FIXTURE_COMPLETED}/delivery`,
    evidence: ".monitoring-plan",
  },
  {
    // SPEC-043: the private evidence channel's distinct provenance.
    produces: "source-type voices incl. user_document (SPEC-043)",
    url: `/cases/${FIXTURE_COMPLETED}/rooms/sources`,
    evidence: ".source-type",
    reveal: async (page) => {
      // Source detail is behind the card's own toggle.
      const toggle = page.locator(".source-card-toggle").first();
      if (await toggle.count()) await toggle.click();
    },
  },
  {
    // SPEC-025, the original offender: the calibration record.
    produces: "calibration record (SPEC-025)",
    url: "/calibration",
    evidence: ".calibration-interpretation",
  },
];

modeDescribe("fixture", "Fixture mode — pipeline output coverage (SPEC-053)", () => {
  for (const output of PHASE_8_OUTPUTS) {
    test(`${output.produces} is on a screen`, async ({ page }) => {
      await page.goto(output.url);
      await page.locator("main.app-main").waitFor({ state: "visible" });
      if (output.reveal) await output.reveal(page);

      await expect(
        page.locator(output.evidence).first(),
        `${output.produces} is produced by the engine and reachable only by reading YAML — ` +
          `nothing at ${output.url} renders it`,
      ).toBeVisible({ timeout: 15_000 });
    });
  }

  test("the guard itself covers every phase 8 sheet", async () => {
    // A coverage guard that quietly stops listing an artifact is worse than no
    // guard, because it reports green about something it no longer checks.
    const covered = PHASE_8_OUTPUTS.map((o) => o.produces).join(" ");
    for (const sheet of ["SPEC-038", "SPEC-039", "SPEC-040", "SPEC-041", "SPEC-042", "SPEC-043"]) {
      expect(covered, `${sheet}'s output is not in the coverage list`).toContain(sheet);
    }
  });
});
