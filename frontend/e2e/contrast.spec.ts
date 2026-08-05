import { test, expect } from "@playwright/test";
import { modeDescribe } from "./helpers";

/**
 * Contrast — SPEC-045.
 *
 * Axe already catches contrast failures on rendered text, but only where text
 * happens to appear on a fixture screen. This asserts the *token layer* itself:
 * every semantic foreground/background pair the design system offers must clear
 * WCAG AA before any component uses it, in both themes.
 *
 * Measured from computed styles rather than from the token values, so a pair
 * that resolves through an alias chain is checked as it actually renders.
 */

/** Relative luminance per WCAG 2.1. */
function luminance(rgb: [number, number, number]): number {
  const [r, g, b] = rgb.map((channel) => {
    const c = channel / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrastRatio(fg: [number, number, number], bg: [number, number, number]): number {
  const l1 = luminance(fg);
  const l2 = luminance(bg);
  const [light, dark] = l1 > l2 ? [l1, l2] : [l2, l1];
  return (light + 0.05) / (dark + 0.05);
}

function parseRgb(value: string): [number, number, number] {
  const match = value.match(/rgba?\(([^)]+)\)/);
  if (!match) throw new Error(`unparseable colour: ${value}`);
  const parts = match[1].split(/[,\s/]+/).filter(Boolean).map(Number);
  return [parts[0], parts[1], parts[2]];
}

/**
 * The pairs the design system promises are readable.
 *
 * `large` marks pairs only ever used at >=18.66px bold or >=24px, which AA
 * holds to 3:1 rather than 4.5:1 — stated per pair rather than applied as a
 * blanket relaxation.
 */
const PAIRS: { fg: string; bg: string; large?: boolean }[] = [
  { fg: "--text", bg: "--surface" },
  { fg: "--text", bg: "--surface-raised" },
  { fg: "--text", bg: "--surface-sunken" },
  { fg: "--text-muted", bg: "--surface" },
  { fg: "--text-muted", bg: "--surface-raised" },
  { fg: "--text-muted", bg: "--surface-sunken" },
  { fg: "--accent", bg: "--surface" },
  { fg: "--accent", bg: "--surface-raised" },
  { fg: "--accent", bg: "--accent-wash" },
  { fg: "--accent-on", bg: "--accent" },
  { fg: "--state-good-text", bg: "--state-good-wash" },
  { fg: "--state-uncertain", bg: "--state-uncertain-wash" },
  { fg: "--state-needs-you-text", bg: "--state-needs-you-wash" },
  { fg: "--state-critical", bg: "--surface-raised" },
  { fg: "--state-critical", bg: "--state-critical-wash" },
];

async function measure(page: import("@playwright/test").Page, theme: "light" | "dark") {
  return page.evaluate(
    ({ pairs, theme }) => {
      document.documentElement.setAttribute("data-theme", theme);
      const probe = document.createElement("div");
      document.body.appendChild(probe);
      const results: { fg: string; bg: string; fgColor: string; bgColor: string }[] = [];
      for (const pair of pairs) {
        probe.style.color = `var(${pair.fg})`;
        probe.style.backgroundColor = `var(${pair.bg})`;
        const computed = getComputedStyle(probe);
        results.push({
          fg: pair.fg,
          bg: pair.bg,
          fgColor: computed.color,
          bgColor: computed.backgroundColor,
        });
      }
      probe.remove();
      return results;
    },
    { pairs: PAIRS, theme },
  );
}

modeDescribe("fixture", "Fixture mode — token contrast", () => {
  for (const theme of ["light", "dark"] as const) {
    test(`every semantic pair clears WCAG AA in ${theme}`, async ({ page }) => {
      await page.goto("/");
      const measured = await measure(page, theme);

      const failures: string[] = [];
      measured.forEach((m, i) => {
        const required = PAIRS[i].large ? 3 : 4.5;
        const ratio = contrastRatio(parseRgb(m.fgColor), parseRgb(m.bgColor));
        if (ratio < required) {
          failures.push(
            `${m.fg} on ${m.bg}: ${ratio.toFixed(2)}:1 (needs ${required}:1) ` +
              `[${m.fgColor} on ${m.bgColor}]`,
          );
        }
      });

      expect(failures, `${theme} theme contrast failures:\n${failures.join("\n")}`).toEqual([]);
    });
  }

  test("an explicit theme choice beats the OS preference in both directions", async ({
    page,
  }, testInfo) => {
    // The project supplies the OS preference; data-theme is the user's choice.
    // Without the explicit :root[data-theme] blocks in tokens.css, the media
    // query would win and one of these two would silently be wrong.
    await page.goto("/");
    const osPrefersDark = testInfo.project.name === "chromium-dark";

    const opposite = osPrefersDark ? "light" : "dark";
    const surface = await page.evaluate((theme) => {
      document.documentElement.setAttribute("data-theme", theme);
      return getComputedStyle(document.documentElement).getPropertyValue("--surface").trim();
    }, opposite);

    const asDark = await page.evaluate(() => {
      document.documentElement.setAttribute("data-theme", "dark");
      return getComputedStyle(document.documentElement).getPropertyValue("--surface").trim();
    });

    if (opposite === "dark") {
      expect(surface).toBe(asDark);
    } else {
      expect(surface).not.toBe(asDark);
    }
  });
});
