import { test as baseTest, expect, type Page } from "@playwright/test";

// ── Mode guard ───────────────────────────────────────────────────────────────

export const E2E_MODE = process.env.E2E_MODE ?? "fixture";

/**
 * Conditionally skip a ``describe`` block when the suite is not running in the
 * requested mode.  Uses Playwright's ``test.describe.skip`` so skipped blocks
 * are fully typed and reported as skipped in the test output.
 *
 * Usage::
 *
 *   modeDescribe("fixture", "library tests", () => {
 *     test("shows cases", async ({ page }) => { ... });
 *   });
 */
export function modeDescribe(mode: string, title: string, body: () => void): void {
  if (E2E_MODE === mode) {
    baseTest.describe(title, body);
  } else {
    baseTest.describe.skip(title, body);
  }
}

// ── Terminology guard ────────────────────────────────────────────────────────

/**
 * Raw enum strings and schema field names that must never appear in the
 * rendered DOM.  The terminology lexicon (``copy/terms.ts``) is the sole
 * source of user-facing labels; these internal identifiers leak if a screen
 * forgets to translate them.
 */
const FORBIDDEN_TERMS: string[] = [
  // CaseStage enum values
  "awaiting_framing_approval",
  "awaiting_final_approval",
  "provisional_thesis",
  "assumption_ledger",
  "pre_mortem",
  "stop_decision",
  "evidence_critique",
  "preliminary_recommendation",
  // TaskRole enum values (beyond what might legitimately appear in copy)
  "assumption_analyst",
  "director_b",
  // Raw schema field names that should be translated.  NOTE: simple English
  // words that are also field names ("reliability", "directness",
  // "materiality", "provenance") are intentionally excluded because the app
  // uses them as legitimate human labels (e.g. "High reliability", "High
  // materiality", "Provenance chain").  Only compound snake_case identifiers
  // that would only leak if a screen forgot to translate are forbidden.
  "risk_tolerance",
  "reversibility",
  "decision_question",
  "alternatives_mentioned",
  "independence_group",
  "cluster_share",
  "authority_score",
  "source_tier",
  "resolution_status",
  "objection_id",
  "evidence_id",
  "assumption_id",
];

/**
 * Sweep the visible DOM for forbidden terminology.  Call after navigating to
 * any screen.  Fails if any forbidden term appears in the page's visible text
 * content.
 */
export async function assertNoForbiddenTerms(page: Page): Promise<void> {
  const bodyText = await page.locator("body").innerText();
  const found: string[] = [];
  for (const term of FORBIDDEN_TERMS) {
    // Use a word-boundary-ish check to avoid matching substrings inside
    // longer words (e.g. "reliability" inside a CSS class name is fine since
    // innerText strips class names, but be defensive).
    if (bodyText.includes(term)) {
      // Avoid false positives from the machinery toggle (raw YAML view).
      // The raw YAML is inside a <pre> that is only visible when toggled.
      found.push(term);
    }
  }
  expect(
    found,
    `Forbidden internal terminology found in DOM: ${found.join(", ")}`,
  ).toEqual([]);
}

// ── API helpers (for stub-mode lifecycle tests) ──────────────────────────────

const API_BASE = "/api";

export async function apiPost<T = unknown>(
  page: Page,
  path: string,
  body?: unknown,
): Promise<{ status: number; data: T }> {
  const resp = await page.request.post(`${API_BASE}${path}`, {
    data: body ?? {},
    headers: { "Content-Type": "application/json" },
  });
  const data = (await resp.json().catch(() => null)) as T;
  return { status: resp.status(), data };
}

export async function apiGet<T = unknown>(
  page: Page,
  path: string,
): Promise<{ status: number; data: T }> {
  const resp = await page.request.get(`${API_BASE}${path}`);
  const data = (await resp.json().catch(() => null)) as T;
  return { status: resp.status(), data };
}

/** Poll the case view endpoint until the stage matches, or timeout. */
export async function waitForStage(
  page: Page,
  caseId: string,
  stage: string,
  timeoutMs = 30_000,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const { data } = await apiGet<{ stage: string }>(
      page,
      `/cases/${caseId}/view`,
    );
    if (data?.stage === stage) return;
    await page.waitForTimeout(500);
  }
  throw new Error(`Case ${caseId} did not reach stage "${stage}" within ${timeoutMs}ms`);
}

// ── Fixture case IDs ─────────────────────────────────────────────────────────

export const FIXTURE_COMPLETED = "case-001-fixture-001";
export const FIXTURE_PARKED = "case-002-fixture-002-parked";
